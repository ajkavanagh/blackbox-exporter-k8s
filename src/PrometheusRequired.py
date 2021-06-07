import json
import logging
from ops.charm import CharmEvents, CharmBase
from ops.framework import Object, StoredState, EventSource, EventBase
logger = logging.getLogger(__name__)


class MonitoringUpdated(EventBase):
    """Event emitted when Monitoring relation to Prometheus is updated."""
    def __init__(self, handle, data=None):
        super().__init__(handle)
        self.data = data

    def snapshot(self):
        """Save scrape target information."""
        return {"data": self.data}

    def restore(self, snapshot):
        """Restore scrape target information."""
        self.data = snapshot["data"]


class MonitoringEvents(CharmEvents):
    """Event descriptor for events raised by :class:`MonitoringRequired`."""
    monitoring_updated = EventSource(MonitoringUpdated)


class MonitoringRequired(Object):
    on = MonitoringEvents()
    _stored = StoredState()

    def __init__(
            self, charm: 'CharmBase',
            name: str,
    ):
        """A Prometheus based Monitoring service provider.

        Args:
            charm: a :class:`CharmBase` instance that manages this
                instance of the Prometheus service.
            name: string name of the relation that is provides the
                Prometheus monitoring service.
        """
        super().__init__(charm, name)
        self._charm = charm
        self.name = name
        self._stored.set_default(local={})
        events = self._charm.on[name]
        self.framework.observe(events.relation_changed,
                               self._on_scrape_target_relation_joined)

    def _on_scrape_target_relation_joined(self, event):
        # Get the bind address from the juju model
        ip = str(self.model.get_binding(event.relation).network.bind_address)
        event.relation.data[self.model.unit].update({
            'targets': json.dumps([
                "{}:{}".format(ip, 9115),
            ]),
        })
        logging.info("Provided %s:%s on %s", ip, 9115, event.relation)
        self.on.monitoring_updated.emit()

    def update_endpoint(self, port: str):
        """TODO: if we wanted to update the endpoint..."""
        pass
