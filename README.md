# Prometheus Blackbox exporter charm

## Description

This charm (blackbox-exporter-k8s) provides the
[Prometheus Blackbox exporter](https://github.com/prometheus/blackbox_exporter),
part of the [Prometheus](https://prometheus.io/) monitoring system.

The blackbox exporter allows blackbox probing of endpoints over HTTP, HTTPS,
DNS, TCP and ICMP.

## Usage

To configure the blackbox exporter `modules` use the charm's `modules` config
option.

As an example, if you store your exporter config in a local file called
`modules.yaml` you can update the charm's configuration using:

    juju config prometheus-blackbox-exporter modules=@modules.yaml

To confirm configuration was set:

    juju config prometheus-blackbox-exporter

The charm should be related to the prometheus charm to allow the collection
(scraping) of metrics from the probes.

It may optionally be related to the grafana charm, and the associated
`dashboards` resource will be provided to grafana.

## Developing

Create and activate a virtualenv with the development requirements:

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests
