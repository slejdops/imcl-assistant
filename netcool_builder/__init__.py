"""
Netcool Docker Builder

A robust, modular pipeline for building Docker images containing
IBM Netcool/OMNIbus system components.
"""

__version__ = '1.0.0'
__author__ = 'IBM Netcool Builder Team'

from .config_parser import ConfigParser, ConfigValidationError, load_and_validate_config

__all__ = [
    'ConfigParser',
    'ConfigValidationError',
    'load_and_validate_config',
]
