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
import typing
from ops._private import yaml

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus

logger = logging.getLogger(__name__)


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

    def _on_blackbox_exporter_pebble_ready(self, event):
        """Define and start blackbox exporter using the Pebble API.
        """
        logging.error("pebble ready: doing the blackbox exporter layer.")
        # Get a reference the container attribute on the PebbleReadyEvent
        container = event.workload
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
        container.add_layer("blackbox_exporter", pebble_layer, combine=True)
        self._on_config_changed(None)

    def _on_config_changed(self, _):
        """Just an example to show how to deal with changed configuration.

        Note: (ajkavanagh) - this may run before the pebble layer ready event.
        """
        container = self.unit.get_container(self.CONTAINER_NAME)
        logging.error(
            "services: {}".format(", ".join(container.get_services())))
        if self.BB_SERVICE_NAME not in container.get_services():
            # bail as the container may not be started yet.
            return
        try:
            container.stop(self.BB_SERVICE_NAME)
        except Exception as e:
            logging.error("Container service %s raised error on .stop(): %s",
                          self.BB_SERVICE_NAME, str(e))
        bb_modules = self._render_config()
        if bb_modules is None:
            # stop the container and go into a blocked state
            self.unit.status = BlockedStatus(
                "config 'modules' is invalid YAML. See logs. STOPPED.")
            return
        try:
            container.push("/etc/blackbox_exporter/config.yaml", bb_modules)
        except Exception as e:
            msg = ("Container service {} raised error on .start(): {}"
                   .format(self.BB_SERVICE_NAME, str(e)))
            logging.error(msg)
            self.unit.status = BlockedStatus(msg)
            return
        try:
            container.start(self.CONTAINER_NAME)
        except Exception as e:
            msg = ("Container service {} raised error on config: {}"
                   .format(self.BB_SERVICE_NAME, str(e)))
            logging.error(msg)
            self.unit.status = BlockedStatus(msg)
            return
        self.unit.status = ActiveStatus()

    def _render_config(self) -> typing.Optional[str]:
        """Render the modules config to a str ready for setting on the
        container.
        """
        modules_str = self.config["modules"]
        try:
            modules = yaml.safe_load(modules_str)
        except yaml.YAMLError as e:
            logging.error("Failed to load modules config, error: {}"
                          .format(e))
            return None

        # if the operator/user has supplied 'modules' as a top level key then
        # return that, othewise, prepend 'modules' as a dictionay key and then
        # dump that.
        if "modules" in modules:
            return yaml.safe_dump(modules, default_flow_style=False)
        else:
            return yaml.safe_dump({"modules": modules},
                                  default_flow_style=False)


if __name__ == "__main__":
    main(BlackboxExporterK8SCharm)
