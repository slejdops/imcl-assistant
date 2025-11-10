# Netcool Docker Builder

A robust, modular Docker image building pipeline for packaging IBM Netcool/OMNIbus system components into Docker images.

## Overview

The Netcool Docker Builder is an enterprise-grade tool for creating optimized Docker images containing IBM Netcool/OMNIbus components such as ObjectServer, Probes, WebGUI, Gateways, and more. It provides a configuration-driven approach to building consistent, reproducible container images with support for multi-stage builds, comprehensive logging, and failure recovery.

## Features

- **Configuration-Driven**: Define builds using YAML or JSON configuration files
- **Multi-Stage Builds**: Minimize image size by separating build and runtime stages
- **Component Support**: ObjectServer, Probes, WebGUI, Gateway, Impact, Process, and custom components
- **Flexible Source Management**: Support for local repositories and remote artifact sources
- **Comprehensive Validation**: Validates configurations before building
- **Progress Monitoring**: Real-time build progress with detailed logging
- **Failure Recovery**: Save build state for resuming partial builds
- **Registry Integration**: Push images to Docker registries
- **Best Practices**: Follows Docker security and optimization best practices
- **Dual Build Methods**: Docker SDK (Python) or Docker CLI execution
- **Extensive Testing**: Unit tests for all modules

## Architecture

```
netcool_builder/
├── config_parser.py          # Configuration parsing and validation
├── dockerfile_generator.py   # Dynamic Dockerfile generation
├── build_executor.py         # Docker build execution and monitoring
└── __init__.py

builder.py                    # Main CLI tool
check_repo.py                # IBM Installation Manager repository checker
examples/                     # Example configurations
tests/                        # Unit tests
```

## Installation

### Prerequisites

- Python 3.7 or higher
- Docker installed and running
- IBM Installation Manager (IMCL) for component installation
- IBM Netcool/OMNIbus installation repositories

### Install Dependencies

```bash
# Install basic dependencies
pip install -r requirements.txt

# For development (includes testing tools)
pip install -r requirements-dev.txt
```

### Required Python Packages

- **PyYAML**: For YAML configuration file support
- **docker**: Docker SDK for Python (optional but recommended)

```bash
pip install PyYAML docker
```

## Quick Start

### 1. Validate Configuration

```bash
./builder.py --config examples/objectserver.yaml --validate
```

### 2. Generate Dockerfile

```bash
./builder.py --config examples/objectserver.yaml --generate-only --output ./build
```

### 3. Build Docker Image

```bash
./builder.py --config examples/objectserver.yaml --build --output ./build
```

### 4. Build and Push to Registry

```bash
./builder.py --config examples/objectserver.yaml --build --push
```

## Configuration

### Configuration File Structure

Configuration files can be in YAML or JSON format and must include:

#### Required Fields

- `build_name`: Name for the Docker build
- `base_image`: Base Docker image (e.g., `redhat/ubi8:latest`)
- `components`: List of Netcool components to install

#### Optional Fields

- `source_repos`: List of IBM installation repositories
- `build_options`: Docker build options (tags, registry, build args, etc.)
- `metadata`: Image metadata and labels
- `imcl_path`: Path to IBM Installation Manager CLI

### Minimal Configuration Example

```yaml
build_name: netcool-objectserver
base_image: redhat/ubi8:latest

components:
  - name: objectserver
    type: objectserver
    install_dir: /opt/IBM/netcool/omnibus
```

### Complete Configuration Example

See `examples/complete.yaml` for a comprehensive example showing all available options.

### Component Types

Supported component types:
- `objectserver` - Netcool ObjectServer
- `probe` - Event probes (syslog, SNMP, etc.)
- `webgui` - Web GUI interface
- `gateway` - Integration gateways
- `impact` - Impact automation
- `process` - Process agents
- `custom` - Custom components

## Usage Examples

### Example 1: Build ObjectServer Image

```bash
./builder.py \
  --config examples/objectserver.yaml \
  --build \
  --output ./build/objectserver
```

### Example 2: Build Without Cache

```bash
./builder.py \
  --config examples/objectserver.yaml \
  --build \
  --no-cache
```

### Example 3: Build Using Docker CLI

```bash
./builder.py \
  --config examples/objectserver.yaml \
  --build \
  --use-cli
```

### Example 4: Validate and Build

```bash
# First validate
./builder.py --config examples/probe.yaml --validate

# Then build
./builder.py --config examples/probe.yaml --build
```

### Example 5: Build Multiple Components

```yaml
# webgui.yaml - Multi-component configuration
build_name: netcool-complete
base_image: redhat/ubi8:latest

components:
  - name: objectserver
    type: objectserver
    install_dir: /opt/IBM/netcool/omnibus

  - name: probe-syslog
    type: probe
    install_dir: /opt/IBM/netcool/omnibus

  - name: webgui
    type: webgui
    install_dir: /opt/IBM/netcool/gui
```

## Configuration Reference

### Build Options

```yaml
build_options:
  # Enable multi-stage builds (default: true)
  multi_stage: true

  # Build arguments
  build_args:
    VERSION: "8.1.0"
    JAVA_VERSION: "8"

  # Image tags
  tags:
    - latest
    - "8.1.0"
    - production

  # Registry configuration
  registry:
    url: registry.example.com/netcool
    username: admin

  # Expose ports
  expose_ports:
    - 4100
    - 4101

  # Container entrypoint
  entrypoint:
    - /opt/IBM/netcool/omnibus/bin/nco_objserv

  # Default command
  cmd:
    - -name
    - AGG_P
```

### Source Repositories

```yaml
source_repos:
  - path: ./repos/netcool
    type: local
    description: Local Netcool repository

  - url: https://artifactory.example.com/netcool/8.1.0
    type: artifactory
    description: Remote Artifactory repository
```

### Component Configuration

```yaml
components:
  - name: objectserver
    type: objectserver
    package_id: com.ibm.tivoli.netcool.omnibus.objectserver
    version: 8.1.0
    install_dir: /opt/IBM/netcool/omnibus
    env_vars:
      NCHOME: /opt/IBM/netcool/omnibus
      OMNIHOME: /opt/IBM/netcool/omnibus
      PATH: /opt/IBM/netcool/omnibus/bin:$PATH
```

### Metadata and Labels

```yaml
metadata:
  version: "8.1.0"
  maintainer: "netcool-team@example.com"

  labels:
    com.ibm.netcool.component: objectserver
    com.ibm.netcool.version: "8.1.0"
    com.example.team: platform
    com.example.environment: production
```

## CLI Reference

```
usage: builder.py [-h] -c CONFIG [--validate | --generate-only | --build]
                  [--push] [--no-cache] [--no-pull] [-o OUTPUT]
                  [--log-dir LOG_DIR] [--use-cli] [-v] [--version]

Options:
  -c, --config CONFIG    Path to configuration file (YAML or JSON)
  --validate             Validate configuration only (no build)
  --generate-only        Generate Dockerfile only (no build)
  --build                Build Docker image
  --push                 Push image to registry after build
  --no-cache             Build without using cache
  --no-pull              Do not pull base image before building
  -o, --output OUTPUT    Output directory (default: ./build)
  --log-dir LOG_DIR      Directory for build logs
  --use-cli              Use Docker CLI instead of Docker SDK
  -v, --verbose          Enable verbose output
  --version              Show version information
```

## Repository Checker

The included `check_repo.py` tool validates IBM Installation Manager repositories:

```bash
# List all offerings in a repository
./check_repo.py --repo /path/to/repo --list-offerings

# Check for specific offerings
./check_repo.py --repo /path/to/repo --software com.ibm.tivoli.netcool.omnibus.objectserver

# Dry-run installation
./check_repo.py --repo /path/to/repo --dry-run com.ibm.tivoli.netcool.omnibus.objectserver --install-dir /tmp/test
```

## Testing

### Run Unit Tests

```bash
# Run all tests
./run_tests.py

# Verbose output
./run_tests.py --verbose

# Quiet output
./run_tests.py --quiet
```

### Individual Test Modules

```bash
# Test config parser
python -m unittest tests.test_config_parser

# Test Dockerfile generator
python -m unittest tests.test_dockerfile_generator

# Test build executor
python -m unittest tests.test_build_executor
```

### Integration Tests

Integration tests require Docker to be running:

```bash
RUN_INTEGRATION_TESTS=1 ./run_tests.py
```

## Best Practices

### Security

1. **Never embed credentials** in configuration files or Dockerfiles
2. **Use secrets management** for sensitive data (passwords, API keys)
3. **Run as non-root user** in containers (automatically configured)
4. **Scan images** for vulnerabilities before deployment
5. **Keep base images updated** with security patches

### Image Optimization

1. **Use multi-stage builds** to minimize final image size
2. **Clean up** package caches and temporary files
3. **Combine RUN commands** to reduce layers
4. **Order layers** from least to most frequently changing

### Configuration Management

1. **Use version control** for configuration files
2. **Document** custom configurations
3. **Validate** configurations before building
4. **Test builds** in non-production environments first

### Build Process

1. **Use build cache** during development for faster builds
2. **Disable cache** (`--no-cache`) for production builds
3. **Tag appropriately** with version numbers
4. **Push to registry** only after successful testing

## Troubleshooting

### Common Issues

#### Configuration Validation Errors

```
✗ Configuration validation failed: Missing required field: 'components'
```

**Solution**: Ensure all required fields are present in your configuration file.

#### Docker Build Failures

```
✗ Build failed: Docker command not found
```

**Solution**: Ensure Docker is installed and the Docker daemon is running.

#### Missing Dependencies

```
PyYAML is not installed
```

**Solution**: Install required dependencies:
```bash
pip install -r requirements.txt
```

#### Permission Errors

```
ERROR: 'imcl' command not found
```

**Solution**: Verify IBM Installation Manager is installed and the path is correct:
```yaml
imcl_path: /opt/IBM/InstallationManager/eclipse/tools/imcl
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
./builder.py --config examples/objectserver.yaml --build --verbose
```

Check build logs in the `build_logs/` directory:

```bash
ls -la build_logs/
cat build_logs/build_*.log
```

## Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd imcl-assistant

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
./run_tests.py
```

### Code Style

- Follow PEP 8 guidelines
- Use type hints where applicable
- Add docstrings to all functions and classes
- Write unit tests for new features

## License

Copyright © IBM Corporation. All rights reserved.

## Support

For issues and questions:
- Check existing documentation
- Review example configurations
- Run with `--verbose` flag for detailed logging
- Check build logs in `build_logs/` directory

## Version History

### Version 1.0.0
- Initial release
- Configuration-driven Docker image building
- Multi-stage build support
- Comprehensive validation and logging
- Support for multiple Netcool components
- Docker SDK and CLI execution modes
- Unit test coverage
- Example configurations

## Related Tools

- **check_repo.py**: IBM Installation Manager repository checker
- **IBM Installation Manager (IMCL)**: Component installation tool
- **Docker**: Container platform

## Acknowledgments

Built for enterprise deployment of IBM Netcool/OMNIbus in containerized environments.
