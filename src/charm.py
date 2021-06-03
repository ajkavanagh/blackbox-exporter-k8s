#!/usr/bin/env python3
# Copyright 2021 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
from contextlib import contextmanager

from ops._private import yaml
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, ModelError, Container
from ops.pebble import ServiceStatus

logger = logging.getLogger(__name__)


class GuardException(Exception):
    pass


class BlockedException(Exception):
    pass


class BlackboxExporterK8SCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    # Some #defs so we don't make str spelling mistakes
    CONTAINER_NAME = 'blackbox-exporter'
    BB_SERVICE_NAME = 'blackbox-exporter'

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.blackbox_exporter_pebble_ready,
                               self._on_blackbox_exporter_pebble_ready)
        self.framework.observe(self.on.config_changed, self._on_config_changed)

    # ########################################################################
    #
    # Operator framework event handlers
    #
    # ########################################################################

    def _on_blackbox_exporter_pebble_ready(self, event):
        """Define and start blackbox exporter using the Pebble API."""
        container = event.workload
        self._do_add_pebble_layer(container)
        self._do_config_changed()

    def _on_config_changed(self, _):
        """Deal with changed configuration.

        Note: (ajkavanagh) - this may run before the pebble layer ready event.
        """
        self._do_config_changed()

    # ########################################################################
    #
    # Event helper functions
    #
    # ########################################################################

    def _do_add_pebble_layer(self, container: 'Container'):
        """Add the pebble layer.

        TODO: note, it would be better if this was 'ensure' as that could be
        run whenever and it would make sure that this specific layer was added.
        """
        # Define an initial Pebble layer configuration
        pebble_layer = {
            "summary": "blackbox exporter layer",
            "description": "pebble config layer for blackbox exporter",
            "services": {
                self.BB_SERVICE_NAME: {
                    "override": "replace",
                    "summary": "blackbox exporter for prometheus",
                    "command": ("/bin/blackbox_exporter "
                                "--config.file="
                                "/etc/blackbox_exporter/config.yml"),
                    "startup": "disabled",
                }
            },
        }
        # Add intial Pebble config layer using the Pebble API
        logging.info("Adding blackbox_exporter layer")
        container.add_layer("blackbox_exporter", pebble_layer, combine=True)
        self.unit.status = ActiveStatus()

    def _do_config_changed(self):
        """Do the actions for config changed using a guard.

        Only handles the 'modules' config at present.
        """
        with guard(self, "update modules config"):
            container = self._get_container(self.CONTAINER_NAME)
            self._ensure_service_stopped(container, self.BB_SERVICE_NAME)
            self._update_bb_config(container)
            self._ensure_service_started(container, self.BB_SERVICE_NAME)
            self.unit.status = ActiveStatus()

    # ########################################################################
    #
    # Utility functions
    #
    # ########################################################################

    def _get_container(self, container_name: str) -> 'Container':
        """Ensure that the container is available, and return it.

        :param container_name: the container to guard and get.
        :raises: GuardException if the container is not running yet
        """
        try:
            return self.unit.get_container(container_name)
        except ModelError:
            raise GuardException("Container {} not available."
                                 .format(container_name))

    def _ensure_service_stopped(
            self, container: 'Container', service_name: str):
        """Ensure that the service on the container is stopped.

        :param container: the container to get.
        :param service_name: the service in the container (by name)
        """
        services = container.get_services()
        if service_name not in container.get_services():
            # bail as the service may not exist yet.
            return
        service = services[service_name]
        if service.current != ServiceStatus.ACTIVE:
            return
        container.stop(service_name)

    def _ensure_service_started(
            self, container: 'Container', service_name: str):
        """Ensure that the service on the container is started.

        :param container: the container name
        :param service_name: the service in the container (by name)
        :raises: GuardException if service is not available.
        """
        services = container.get_services()
        if service_name in services:
            service = services[service_name]
            if service.current == ServiceStatus.ACTIVE:
                return
        else:
            raise GuardException(
                "Service {} in container {} is not available to start."
                .format(service_name, container.name))
        try:
            container.start(service_name)
        except Exception as e:
            logging.error("Service %s on container %s didn't start: %s",
                          service_name, container.name, str(e))
            raise

    def _update_bb_config(self, container: 'Container'):
        """Update the blackbox-exporter config file from the config option.

        :raises: BlockedException if the config is invalid or the container
            won't start with it.
        """
        bb_modules = self._render_modules_config()
        try:
            container.push("/etc/blackbox_exporter/config.yaml", bb_modules)
        except Exception as e:
            msg = ("Container service {} raised error on .start(): {}"
                   .format(self.BB_SERVICE_NAME, str(e)))
            raise BlockedException(msg)

    def _render_modules_config(self) -> str:
        """Render the modules config to a str ready for setting on the
        container.

        :raises: BlockedException if invalid yaml
        """
        modules_str = self.config["modules"]
        try:
            modules = yaml.safe_load(modules_str)
        except yaml.YAMLError as e:
            raise BlockedException(
                "Failed to load modules config, invalid YAML?: {}" .format(e))

        # if the operator/user has supplied 'modules' as a top level key then
        # return that, othewise, prepend 'modules' as a dictionay key and then
        # dump that.
        if "modules" in modules:
            return yaml.safe_dump(modules, default_flow_style=False)
        else:
            return yaml.safe_dump({"modules": modules},
                                  default_flow_style=False)


# ############################################################################
#
# "Library" functions
#
# ############################################################################


@contextmanager
def guard(charm: 'CharmBase',
          section: str,
          handle_exception=True,
          log_traceback=True,
          **__):
    """Context manager to handle errors and bailing out of an event/hook.

    The nature of Juju is that all the information may not be available to run
    a set of actions.  This context manager allows a section of code to be
    'guarded' so that it can be bailed at any time.

    It also handles errors which can be interpreted as a Block rather than the
    charm going into error.

    :param charm: the charm class (so that unit status can be set)
    :param section: the name of the section (for debugging/info purposes)
    :handle_exception: whether to handle the exceptio to a BlockedStatus()
    :log_traceback: whether to log the traceback for debugging purposes.
    :raises: Exception if handle_exception is False
    """
    logger.info("Entering guarded section: '%s'", section)
    try:
        yield
        logging.info("Completed guarded section fully: '%s'", section)
    except GuardException as e:
        logger.info("Guarded Section: Early exit from '%s' due to '%s'.",
                    section, str(e))
    except BlockedException as e:
        logger.warning(
            "Charm is blocked in section '%s' due to '%s'", section, str(e))
        charm.unit.status = BlockedStatus(e.msg)
    except Exception as e:
        # something else went wrong
        if handle_exception:
            logging.error("Exception raised in secion '%s': %s",
                          section, str(e))
            if log_traceback:
                import traceback
                logging.error(traceback.format_exc())
                charm.unit.status = BlockedStatus(
                    "Error in charm (see logs): {}".format(str(e)))
                return
        raise


# ############################################################################
#
# And finally, main.
#
# ############################################################################


if __name__ == "__main__":
    main(BlackboxExporterK8SCharm)
