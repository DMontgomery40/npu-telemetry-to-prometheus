# Dockerfile for the Intel NPU Prometheus exporter
#
# This container builds a minimal Python environment, installs the
# prometheus_client library and runs the exporter.  The exporter exposes
# metrics on port 8000 by default; this can be changed at run time by
# setting the NPU_EXPORTER_PORT environment variable on the container.

FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Create working directory inside container
WORKDIR /app

# Copy the exporter script into the container
COPY intel_npu_exporter.py /app/intel_npu_exporter.py

# Install only the required Python dependency.  Using --no-cache-dir
# reduces the image size by omitting the pip cache.
RUN pip install --no-cache-dir prometheus_client

# Expose the metrics port.  Change this if using a custom port.
EXPOSE 8000

# Set the default command.  The NPU_EXPORTER_PORT environment
# variable can be overridden at runtime to change the port.
CMD ["python3", "intel_npu_exporter.py"]
