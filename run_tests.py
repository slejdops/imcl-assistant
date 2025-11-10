#!/usr/bin/env python3
"""
Test runner for Netcool Docker Builder

Runs all unit tests and generates a coverage report.
"""

import sys
import unittest
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def run_tests(verbosity=2):
    """
    Run all unit tests.

    Args:
        verbosity: Test output verbosity level

    Returns:
        True if all tests passed
    """
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent / 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')

    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == '__main__':
    verbosity = 2
    if '-v' in sys.argv or '--verbose' in sys.argv:
        verbosity = 3
    elif '-q' in sys.argv or '--quiet' in sys.argv:
        verbosity = 1

    print("=" * 70)
    print("  Netcool Docker Builder - Test Suite")
    print("=" * 70)
    print()

    success = run_tests(verbosity)

    print()
    print("=" * 70)
    if success:
        print("  ✓ All tests passed!")
    else:
        print("  ✗ Some tests failed")
    print("=" * 70)

    sys.exit(0 if success else 1)
