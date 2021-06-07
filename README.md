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

## Getting at the metrics

By default, blackbox-exporter exports its metrics on port 9115.  Any scraper
can access it, and it also provides a simple 'http' relation (called
'blackbox-exporter') which simple informs the requires side of the IP address
and port (9115).

However, blackbox-exporter is really designed to be scraped by Prometheus, and
so it supports the 'prometheus' relation type to the prometheus-k8s charm.
This will automatically configure it to be scraped.

    juju add-relation prometheus-k8s blackbox-exporter-k8s

## Developing

Create and activate a virtualenv with the development requirements:

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests
