#!/usr/bin/env python3
"""
Unit tests for dockerfile_generator module
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from netcool_builder.dockerfile_generator import DockerfileGenerator


class TestDockerfileGenerator(unittest.TestCase):
    """Test cases for DockerfileGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Minimal config
        self.minimal_config = {
            'build_name': 'test-build',
            'base_image': 'ubi8:latest',
            'components': [
                {
                    'name': 'objectserver',
                    'type': 'objectserver',
                    'install_dir': '/opt/IBM/netcool'
                }
            ]
        }

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_single_stage(self):
        """Test generating a single-stage Dockerfile."""
        config = self.minimal_config.copy()
        config['build_options'] = {'multi_stage': False}

        generator = DockerfileGenerator(config, self.temp_dir)
        dockerfile_path = generator.generate()

        self.assertTrue(os.path.exists(dockerfile_path))

        with open(dockerfile_path, 'r') as f:
            content = f.read()

        # Verify basic structure
        self.assertIn('FROM ubi8:latest', content)
        self.assertIn('# Dockerfile for test-build', content)
        self.assertNotIn('AS builder', content)  # Single stage

    def test_generate_multi_stage(self):
        """Test generating a multi-stage Dockerfile."""
        config = self.minimal_config.copy()
        config['build_options'] = {'multi_stage': True}

        generator = DockerfileGenerator(config, self.temp_dir)
        dockerfile_path = generator.generate()

        self.assertTrue(os.path.exists(dockerfile_path))

        with open(dockerfile_path, 'r') as f:
            content = f.read()

        # Verify multi-stage structure
        self.assertIn('AS builder', content)
        self.assertIn('AS runtime', content)
        self.assertIn('COPY --from=builder', content)

    def test_build_args(self):
        """Test that build args are included."""
        config = self.minimal_config.copy()
        config['build_options'] = {
            'build_args': {
                'VERSION': '8.1.0',
                'JAVA_VERSION': '8'
            }
        }

        generator = DockerfileGenerator(config, self.temp_dir)
        dockerfile_path = generator.generate()

        with open(dockerfile_path, 'r') as f:
            content = f.read()

        self.assertIn('ARG VERSION=8.1.0', content)
        self.assertIn('ARG JAVA_VERSION=8', content)

    def test_metadata_labels(self):
        """Test that metadata labels are included."""
        config = self.minimal_config.copy()
        config['metadata'] = {
            'version': '1.0.0',
            'maintainer': 'test@example.com',
            'labels': {
                'app': 'netcool',
                'team': 'platform'
            }
        }

        generator = DockerfileGenerator(config, self.temp_dir)
        dockerfile_path = generator.generate()

        with open(dockerfile_path, 'r') as f:
            content = f.read()

        self.assertIn('LABEL', content)
        self.assertIn('app="netcool"', content)
        self.assertIn('team="platform"', content)

    def test_environment_variables(self):
        """Test that component environment variables are included."""
        config = self.minimal_config.copy()
        config['components'][0]['env_vars'] = {
            'NCHOME': '/opt/IBM/netcool',
            'PATH': '/opt/IBM/netcool/bin:$PATH'
        }

        generator = DockerfileGenerator(config, self.temp_dir)
        dockerfile_path = generator.generate()

        with open(dockerfile_path, 'r') as f:
            content = f.read()

        self.assertIn('ENV NCHOME=/opt/IBM/netcool', content)

    def test_expose_ports(self):
        """Test that ports are exposed."""
        config = self.minimal_config.copy()
        config['build_options'] = {
            'expose_ports': [4100, 4101]
        }

        generator = DockerfileGenerator(config, self.temp_dir)
        dockerfile_path = generator.generate()

        with open(dockerfile_path, 'r') as f:
            content = f.read()

        self.assertIn('EXPOSE 4100', content)
        self.assertIn('EXPOSE 4101', content)

    def test_entrypoint_and_cmd(self):
        """Test that ENTRYPOINT and CMD are set."""
        config = self.minimal_config.copy()
        config['build_options'] = {
            'entrypoint': ['/bin/sh', '-c'],
            'cmd': ['echo', 'hello']
        }

        generator = DockerfileGenerator(config, self.temp_dir)
        dockerfile_path = generator.generate()

        with open(dockerfile_path, 'r') as f:
            content = f.read()

        self.assertIn('ENTRYPOINT', content)
        self.assertIn('CMD', content)

    def test_generate_dockerignore(self):
        """Test generating .dockerignore file."""
        generator = DockerfileGenerator(self.minimal_config, self.temp_dir)
        dockerignore_path = generator.generate_dockerignore()

        self.assertTrue(os.path.exists(dockerignore_path))

        with open(dockerignore_path, 'r') as f:
            content = f.read()

        # Verify common patterns
        self.assertIn('.git/', content)
        self.assertIn('__pycache__/', content)
        self.assertIn('*.pyc', content)

    def test_multiple_components(self):
        """Test Dockerfile with multiple components."""
        config = self.minimal_config.copy()
        config['components'] = [
            {
                'name': 'objectserver',
                'type': 'objectserver',
                'install_dir': '/opt/IBM/netcool/omnibus'
            },
            {
                'name': 'probe',
                'type': 'probe',
                'install_dir': '/opt/IBM/netcool/probes'
            }
        ]

        generator = DockerfileGenerator(config, self.temp_dir)
        dockerfile_path = generator.generate()

        with open(dockerfile_path, 'r') as f:
            content = f.read()

        self.assertIn('objectserver', content.lower())
        self.assertIn('probe', content.lower())


if __name__ == '__main__':
    unittest.main()
