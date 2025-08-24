#!/usr/bin/env python3
"""
Prometheus exporter for Intel NPU usage metrics.

This module exposes basic telemetry about the Intel Neural Processing
Unit (NPU)
found on certain Intel platforms.  It reads the cumulative runtime from the
kernel's sysfs, calculates a utilisation percentage and exposes both the
cumulative runtime and the instantaneous utilisation via a Prometheus HTTP
endpoint.

The exporter uses the ``prometheus_client`` library to define metrics and
publish them.  According to Prometheus best‑practices, counters are used for
values that only ever increase (such as the cumulative runtime) while gauges
are used for values that can increase and decrease (such as utilisation
percentage).  A simple infinite loop periodically updates these metrics.

To run this exporter:

1. Install the Prometheus client library if it's not already installed:

   ``pip install prometheus_client``

2. Execute the script.  By default it listens on port 8000 and exposes
   metrics under the ``/metrics`` path.  You can change the port by
   setting the ``NPU_EXPORTER_PORT`` environment variable.

   ``python3 intel_npu_exporter.py``

3. Point your Prometheus instance at ``http://<host>:8000/metrics`` to scrape
   the metrics.

The calculation of utilisation is based on the difference in the cumulative
runtime between two successive reads divided by the elapsed time between
those reads.  The runtime values provided by sysfs are in milliseconds,
so the elapsed wall‑clock time is also converted to milliseconds.  If either
the runtime or the elapsed time is zero the utilisation falls back to 0 %.
"""

import os
import time
from typing import Optional

from prometheus_client import Counter, Gauge, start_http_server


# Configuration: paths into sysfs and device files.  These values mirror
# those used by the interactive curses program.  Adjust NPU_DEVICE_DIR
# if your NPU is located at a different PCI address.
NPU_DEVICE_DIR = "/sys/devices/pci0000:00/0000:00:0b.0"
NPU_RUNTIME_PATH = f"{NPU_DEVICE_DIR}/power/runtime_active_time"


def read_sysfs_value(path: str) -> Optional[str]:
    """Read a sysfs entry and return its value stripped of whitespace.

    If the file does not exist or isn't readable, ``None`` is returned.

    Args:
        path: Filesystem path to read.

    Returns:
        The contents of the file with whitespace removed, or ``None``.
    """
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError):
        return None


def read_runtime() -> float:
    """Read the cumulative runtime of the NPU in milliseconds.

    Returns 0.0 if the runtime cannot be read.
    """
    val = read_sysfs_value(NPU_RUNTIME_PATH)
    return float(val) if val is not None else 0.0


def main() -> None:
    """Entry point for the exporter.

    This function defines Prometheus metrics, starts the HTTP server and
    continually updates the metrics in a loop.
    """
    # Define a Counter for the cumulative runtime.  This value only ever
    # increases while the NPU is in use, making Counter an appropriate metric
    # type.  The units are milliseconds.
    runtime_counter = Counter(
        'intel_npu_runtime_milliseconds',
        'Cumulative active runtime of the Intel NPU in milliseconds'
    )

    # Define a Gauge for utilisation percentage.  Gauges can go up or down
    # depending on current load.
    utilisation_gauge = Gauge(
        'intel_npu_usage_percent',
        'Instantaneous utilisation of the Intel NPU as a percentage'
    )

    # Expose metrics on the configured port.  Prometheus scrapes metrics
    # from this HTTP server.  The default port is 8000, but it can be
    # overridden via an environment variable.
    port_env = os.getenv("NPU_EXPORTER_PORT")
    try:
        port = int(port_env) if port_env is not None else 8000
    except ValueError:
        port = 8000
    start_http_server(port)

    # Initialise state for utilisation calculation
    previous_runtime = read_runtime()
    previous_time = time.time()

    while True:
        current_runtime = read_runtime()
        current_time = time.time()

        # Update the runtime counter.  Prometheus counters expect monotonically
        # increasing values, so use ``inc`` rather than ``set``.
        runtime_diff = max(0.0, current_runtime - previous_runtime)
        if runtime_diff > 0:
            runtime_counter.inc(runtime_diff)

        # Calculate utilisation percentage.  The runtime is reported in
        # milliseconds, so the elapsed time is converted to milliseconds to
        # match units.  Protect against division by zero and negative
        # differences (which could occur if the sysfs value resets).
        elapsed_ms = (current_time - previous_time) * 1000.0
        utilisation = 0.0
        if elapsed_ms > 0 and runtime_diff >= 0.0:
            utilisation = (runtime_diff / elapsed_ms) * 100.0
            # Cap utilisation at 100 % to avoid unrealistic values
            utilisation = max(0.0, min(utilisation, 100.0))
        utilisation_gauge.set(utilisation)

        # Prepare for next iteration
        previous_runtime = current_runtime
        previous_time = current_time

        # Sleep before next update.  A one‑second interval aligns with the
        # original interactive tool and keeps overhead low.
        time.sleep(1)


if __name__ == '__main__':
    main()
