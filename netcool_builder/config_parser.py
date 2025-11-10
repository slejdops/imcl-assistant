#!/usr/bin/env python3
"""
Configuration Parser for Netcool Docker Builder

Handles parsing and validation of YAML/JSON configuration files
for building Netcool/OMNIbus Docker images.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigParser:
    """
    Parses and validates configuration files for Docker image builds.

    Supports both YAML and JSON formats with comprehensive validation
    for all required and optional fields.
    """

    REQUIRED_FIELDS = ['build_name', 'components', 'base_image']
    COMPONENT_REQUIRED_FIELDS = ['name', 'type']
    VALID_COMPONENT_TYPES = [
        'objectserver', 'probe', 'webgui', 'gateway',
        'impact', 'process', 'custom'
    ]

    def __init__(self, config_path: str):
        """
        Initialize the configuration parser.

        Args:
            config_path: Path to the configuration file (YAML or JSON)

        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            ConfigValidationError: If the file format is unsupported
        """
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        self.config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """
        Load configuration from file based on extension.

        Raises:
            ConfigValidationError: If the file cannot be parsed or format is invalid
        """
        suffix = self.config_path.suffix.lower()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if suffix in ['.yaml', '.yml']:
                    if not YAML_AVAILABLE:
                        raise ConfigValidationError(
                            "PyYAML is not installed. Install it with: pip install pyyaml"
                        )
                    self.config = yaml.safe_load(f)
                elif suffix == '.json':
                    self.config = json.load(f)
                else:
                    raise ConfigValidationError(
                        f"Unsupported file format: {suffix}. Use .yaml, .yml, or .json"
                    )
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"YAML parsing error: {e}")
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"JSON parsing error: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Error loading configuration: {e}")

        if not isinstance(self.config, dict):
            raise ConfigValidationError("Configuration must be a dictionary/object")

    def validate(self) -> bool:
        """
        Validate the loaded configuration.

        Returns:
            True if validation succeeds

        Raises:
            ConfigValidationError: If validation fails with detailed error message
        """
        # Check required top-level fields
        for field in self.REQUIRED_FIELDS:
            if field not in self.config:
                raise ConfigValidationError(
                    f"Missing required field: '{field}'"
                )

        # Validate build_name
        if not isinstance(self.config['build_name'], str) or not self.config['build_name']:
            raise ConfigValidationError("'build_name' must be a non-empty string")

        # Validate base_image
        if not isinstance(self.config['base_image'], str) or not self.config['base_image']:
            raise ConfigValidationError("'base_image' must be a non-empty string")

        # Validate components
        if not isinstance(self.config['components'], list) or not self.config['components']:
            raise ConfigValidationError("'components' must be a non-empty list")

        self._validate_components()
        self._validate_source_repos()
        self._validate_build_options()
        self._validate_metadata()

        return True

    def _validate_components(self) -> None:
        """
        Validate component configurations.

        Raises:
            ConfigValidationError: If component validation fails
        """
        for idx, component in enumerate(self.config['components']):
            if not isinstance(component, dict):
                raise ConfigValidationError(
                    f"Component {idx} must be a dictionary/object"
                )

            # Check required fields
            for field in self.COMPONENT_REQUIRED_FIELDS:
                if field not in component:
                    raise ConfigValidationError(
                        f"Component {idx}: Missing required field '{field}'"
                    )

            # Validate component type
            comp_type = component['type']
            if comp_type not in self.VALID_COMPONENT_TYPES:
                raise ConfigValidationError(
                    f"Component {idx}: Invalid type '{comp_type}'. "
                    f"Valid types: {', '.join(self.VALID_COMPONENT_TYPES)}"
                )

            # Validate component name
            if not isinstance(component['name'], str) or not component['name']:
                raise ConfigValidationError(
                    f"Component {idx}: 'name' must be a non-empty string"
                )

            # Validate version if present
            if 'version' in component and not isinstance(component['version'], str):
                raise ConfigValidationError(
                    f"Component {idx} ('{component['name']}'): 'version' must be a string"
                )

            # Validate package_id if present
            if 'package_id' in component and not isinstance(component['package_id'], str):
                raise ConfigValidationError(
                    f"Component {idx} ('{component['name']}'): 'package_id' must be a string"
                )

            # Validate install_dir if present
            if 'install_dir' in component:
                if not isinstance(component['install_dir'], str) or not component['install_dir']:
                    raise ConfigValidationError(
                        f"Component {idx} ('{component['name']}'): "
                        "'install_dir' must be a non-empty string"
                    )

            # Validate environment variables if present
            if 'env_vars' in component:
                if not isinstance(component['env_vars'], dict):
                    raise ConfigValidationError(
                        f"Component {idx} ('{component['name']}'): "
                        "'env_vars' must be a dictionary/object"
                    )

    def _validate_source_repos(self) -> None:
        """
        Validate source repository configurations.

        Raises:
            ConfigValidationError: If source repo validation fails
        """
        if 'source_repos' not in self.config:
            return

        source_repos = self.config['source_repos']
        if not isinstance(source_repos, list):
            raise ConfigValidationError("'source_repos' must be a list")

        for idx, repo in enumerate(source_repos):
            if not isinstance(repo, dict):
                raise ConfigValidationError(
                    f"Source repo {idx} must be a dictionary/object"
                )

            if 'path' not in repo and 'url' not in repo:
                raise ConfigValidationError(
                    f"Source repo {idx}: Must specify either 'path' or 'url'"
                )

            # Validate path if present
            if 'path' in repo:
                if not isinstance(repo['path'], str) or not repo['path']:
                    raise ConfigValidationError(
                        f"Source repo {idx}: 'path' must be a non-empty string"
                    )

            # Validate type if present
            if 'type' in repo:
                valid_types = ['local', 'remote', 'http', 'artifactory']
                if repo['type'] not in valid_types:
                    raise ConfigValidationError(
                        f"Source repo {idx}: Invalid type '{repo['type']}'. "
                        f"Valid types: {', '.join(valid_types)}"
                    )

    def _validate_build_options(self) -> None:
        """
        Validate build options.

        Raises:
            ConfigValidationError: If build options validation fails
        """
        if 'build_options' not in self.config:
            return

        build_opts = self.config['build_options']
        if not isinstance(build_opts, dict):
            raise ConfigValidationError("'build_options' must be a dictionary/object")

        # Validate multi_stage
        if 'multi_stage' in build_opts:
            if not isinstance(build_opts['multi_stage'], bool):
                raise ConfigValidationError(
                    "'build_options.multi_stage' must be a boolean"
                )

        # Validate build_args
        if 'build_args' in build_opts:
            if not isinstance(build_opts['build_args'], dict):
                raise ConfigValidationError(
                    "'build_options.build_args' must be a dictionary/object"
                )

        # Validate registry
        if 'registry' in build_opts:
            registry = build_opts['registry']
            if not isinstance(registry, dict):
                raise ConfigValidationError(
                    "'build_options.registry' must be a dictionary/object"
                )

            if 'url' in registry and not isinstance(registry['url'], str):
                raise ConfigValidationError(
                    "'build_options.registry.url' must be a string"
                )

        # Validate tags
        if 'tags' in build_opts:
            if not isinstance(build_opts['tags'], list):
                raise ConfigValidationError(
                    "'build_options.tags' must be a list"
                )

    def _validate_metadata(self) -> None:
        """
        Validate image metadata.

        Raises:
            ConfigValidationError: If metadata validation fails
        """
        if 'metadata' not in self.config:
            return

        metadata = self.config['metadata']
        if not isinstance(metadata, dict):
            raise ConfigValidationError("'metadata' must be a dictionary/object")

        # Validate labels if present
        if 'labels' in metadata:
            if not isinstance(metadata['labels'], dict):
                raise ConfigValidationError(
                    "'metadata.labels' must be a dictionary/object"
                )

    def get_config(self) -> Dict[str, Any]:
        """
        Get the validated configuration.

        Returns:
            The configuration dictionary
        """
        return self.config

    def get_build_name(self) -> str:
        """Get the build name."""
        return self.config['build_name']

    def get_base_image(self) -> str:
        """Get the base Docker image."""
        return self.config['base_image']

    def get_components(self) -> List[Dict[str, Any]]:
        """Get the list of components to install."""
        return self.config['components']

    def get_source_repos(self) -> List[Dict[str, Any]]:
        """Get the list of source repositories."""
        return self.config.get('source_repos', [])

    def get_build_options(self) -> Dict[str, Any]:
        """Get build options."""
        return self.config.get('build_options', {})

    def get_metadata(self) -> Dict[str, Any]:
        """Get image metadata."""
        return self.config.get('metadata', {})

    def is_multi_stage(self) -> bool:
        """Check if multi-stage build is enabled."""
        return self.get_build_options().get('multi_stage', True)

    def get_imcl_path(self) -> str:
        """Get the IBM Installation Manager CLI path."""
        return self.config.get('imcl_path', 'imcl')


def load_and_validate_config(config_path: str) -> ConfigParser:
    """
    Convenience function to load and validate a configuration file.

    Args:
        config_path: Path to the configuration file

    Returns:
        Validated ConfigParser instance

    Raises:
        ConfigValidationError: If loading or validation fails
    """
    parser = ConfigParser(config_path)
    parser.validate()
    return parser


if __name__ == '__main__':
    # Simple CLI for testing configuration validation
    import sys

    if len(sys.argv) != 2:
        print("Usage: python config_parser.py <config_file>")
        sys.exit(1)

    try:
        parser = load_and_validate_config(sys.argv[1])
        print(f"✓ Configuration validated successfully: {parser.get_build_name()}")
        print(f"  Base image: {parser.get_base_image()}")
        print(f"  Components: {len(parser.get_components())}")
        print(f"  Multi-stage build: {parser.is_multi_stage()}")
        sys.exit(0)
    except (FileNotFoundError, ConfigValidationError) as e:
        print(f"✗ Configuration validation failed: {e}", file=sys.stderr)
        sys.exit(1)
