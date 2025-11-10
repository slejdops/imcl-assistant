#!/usr/bin/env python3
"""
Unit tests for config_parser module
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from netcool_builder.config_parser import (
    ConfigParser, ConfigValidationError, load_and_validate_config
)


class TestConfigParser(unittest.TestCase):
    """Test cases for ConfigParser class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_config_file(self, content, filename='test.json'):
        """Helper to create a config file."""
        filepath = os.path.join(self.temp_dir, filename)
        with open(filepath, 'w') as f:
            if filename.endswith('.json'):
                json.dump(content, f)
            else:
                # For YAML files
                import yaml
                yaml.dump(content, f)
        return filepath

    def test_valid_minimal_config(self):
        """Test parsing a valid minimal configuration."""
        config = {
            'build_name': 'test-build',
            'base_image': 'ubi8:latest',
            'components': [
                {'name': 'objectserver', 'type': 'objectserver'}
            ]
        }

        filepath = self.create_config_file(config)
        parser = ConfigParser(filepath)
        self.assertTrue(parser.validate())
        self.assertEqual(parser.get_build_name(), 'test-build')
        self.assertEqual(parser.get_base_image(), 'ubi8:latest')

    def test_missing_required_field(self):
        """Test that missing required fields raise errors."""
        config = {
            'build_name': 'test-build',
            # Missing base_image and components
        }

        filepath = self.create_config_file(config)
        parser = ConfigParser(filepath)

        with self.assertRaises(ConfigValidationError) as ctx:
            parser.validate()
        self.assertIn('required', str(ctx.exception).lower())

    def test_invalid_component_type(self):
        """Test that invalid component types are rejected."""
        config = {
            'build_name': 'test-build',
            'base_image': 'ubi8:latest',
            'components': [
                {'name': 'test', 'type': 'invalid_type'}
            ]
        }

        filepath = self.create_config_file(config)
        parser = ConfigParser(filepath)

        with self.assertRaises(ConfigValidationError) as ctx:
            parser.validate()
        self.assertIn('invalid type', str(ctx.exception).lower())

    def test_empty_components_list(self):
        """Test that empty components list is rejected."""
        config = {
            'build_name': 'test-build',
            'base_image': 'ubi8:latest',
            'components': []
        }

        filepath = self.create_config_file(config)
        parser = ConfigParser(filepath)

        with self.assertRaises(ConfigValidationError) as ctx:
            parser.validate()
        self.assertIn('non-empty', str(ctx.exception).lower())

    def test_complete_config(self):
        """Test parsing a complete configuration with all options."""
        config = {
            'build_name': 'complete-build',
            'base_image': 'ubi8:latest',
            'components': [
                {
                    'name': 'objectserver',
                    'type': 'objectserver',
                    'version': '8.1.0',
                    'package_id': 'com.ibm.netcool.objectserver',
                    'install_dir': '/opt/IBM/netcool',
                    'env_vars': {'NCHOME': '/opt/IBM/netcool'}
                }
            ],
            'source_repos': [
                {'path': '/tmp/repo', 'type': 'local'}
            ],
            'build_options': {
                'multi_stage': True,
                'build_args': {'VERSION': '8.1.0'},
                'tags': ['latest', '8.1'],
                'registry': {'url': 'registry.example.com'}
            },
            'metadata': {
                'version': '8.1.0',
                'maintainer': 'test@example.com',
                'labels': {'app': 'netcool'}
            }
        }

        filepath = self.create_config_file(config)
        parser = ConfigParser(filepath)
        self.assertTrue(parser.validate())

        # Verify accessors
        self.assertEqual(parser.get_build_name(), 'complete-build')
        self.assertEqual(len(parser.get_components()), 1)
        self.assertTrue(parser.is_multi_stage())
        self.assertEqual(parser.get_metadata()['version'], '8.1.0')

    def test_file_not_found(self):
        """Test that non-existent file raises error."""
        with self.assertRaises(FileNotFoundError):
            ConfigParser('/non/existent/file.json')

    def test_invalid_json(self):
        """Test that invalid JSON raises error."""
        filepath = os.path.join(self.temp_dir, 'invalid.json')
        with open(filepath, 'w') as f:
            f.write('{ invalid json }')

        with self.assertRaises(ConfigValidationError):
            ConfigParser(filepath)

    def test_load_and_validate_helper(self):
        """Test the load_and_validate_config helper function."""
        config = {
            'build_name': 'test-build',
            'base_image': 'ubi8:latest',
            'components': [
                {'name': 'objectserver', 'type': 'objectserver'}
            ]
        }

        filepath = self.create_config_file(config)
        parser = load_and_validate_config(filepath)
        self.assertEqual(parser.get_build_name(), 'test-build')


class TestConfigValidation(unittest.TestCase):
    """Test specific validation rules."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_config_file(self, content):
        """Helper to create a config file."""
        filepath = os.path.join(self.temp_dir, 'test.json')
        with open(filepath, 'w') as f:
            json.dump(content, f)
        return filepath

    def test_invalid_build_args_type(self):
        """Test that build_args must be a dictionary."""
        config = {
            'build_name': 'test',
            'base_image': 'ubi8:latest',
            'components': [{'name': 'test', 'type': 'objectserver'}],
            'build_options': {
                'build_args': 'invalid'  # Should be dict
            }
        }

        filepath = self.create_config_file(config)
        parser = ConfigParser(filepath)

        with self.assertRaises(ConfigValidationError):
            parser.validate()

    def test_source_repo_validation(self):
        """Test source repository validation."""
        config = {
            'build_name': 'test',
            'base_image': 'ubi8:latest',
            'components': [{'name': 'test', 'type': 'objectserver'}],
            'source_repos': [
                {}  # Missing path or url
            ]
        }

        filepath = self.create_config_file(config)
        parser = ConfigParser(filepath)

        with self.assertRaises(ConfigValidationError) as ctx:
            parser.validate()
        self.assertIn('path', str(ctx.exception).lower())


if __name__ == '__main__':
    unittest.main()
