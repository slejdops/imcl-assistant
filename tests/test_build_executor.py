#!/usr/bin/env python3
"""
Unit tests for build_executor module
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from netcool_builder.build_executor import BuildExecutor, BuildExecutionError


class TestBuildExecutor(unittest.TestCase):
    """Test cases for BuildExecutor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = os.path.join(self.temp_dir, 'logs')

        # Minimal config
        self.config = {
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

        # Create a dummy Dockerfile
        self.dockerfile_path = os.path.join(self.temp_dir, 'Dockerfile')
        with open(self.dockerfile_path, 'w') as f:
            f.write('FROM ubi8:latest\n')

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test BuildExecutor initialization."""
        executor = BuildExecutor(
            config=self.config,
            dockerfile_path=self.dockerfile_path,
            build_context=self.temp_dir,
            use_sdk=False,
            log_dir=self.log_dir
        )

        self.assertIsNotNone(executor.logger)
        self.assertEqual(executor.config, self.config)
        self.assertTrue(os.path.exists(self.log_dir))

    def test_get_image_tags(self):
        """Test image tag generation."""
        config = self.config.copy()
        config['build_options'] = {
            'tags': ['latest', '8.1.0']
        }

        executor = BuildExecutor(
            config=config,
            dockerfile_path=self.dockerfile_path,
            build_context=self.temp_dir,
            use_sdk=False,
            log_dir=self.log_dir
        )

        tags = executor._get_image_tags()
        self.assertIn('test-build', tags)
        self.assertIn('test-build:latest', tags)
        self.assertIn('test-build:8.1.0', tags)

    def test_get_image_tags_with_registry(self):
        """Test image tag generation with registry."""
        config = self.config.copy()
        config['build_options'] = {
            'tags': ['latest'],
            'registry': {
                'url': 'registry.example.com/netcool'
            }
        }

        executor = BuildExecutor(
            config=config,
            dockerfile_path=self.dockerfile_path,
            build_context=self.temp_dir,
            use_sdk=False,
            log_dir=self.log_dir
        )

        tags = executor._get_image_tags()
        self.assertTrue(any('registry.example.com' in tag for tag in tags))

    def test_get_build_args(self):
        """Test build arguments extraction."""
        config = self.config.copy()
        config['build_options'] = {
            'build_args': {
                'VERSION': '8.1.0',
                'JAVA_VERSION': '8'
            }
        }

        executor = BuildExecutor(
            config=config,
            dockerfile_path=self.dockerfile_path,
            build_context=self.temp_dir,
            use_sdk=False,
            log_dir=self.log_dir
        )

        build_args = executor._get_build_args()
        self.assertEqual(build_args['VERSION'], '8.1.0')
        self.assertEqual(build_args['JAVA_VERSION'], '8')

    def test_build_state_management(self):
        """Test build state save and load."""
        executor = BuildExecutor(
            config=self.config,
            dockerfile_path=self.dockerfile_path,
            build_context=self.temp_dir,
            use_sdk=False,
            log_dir=self.log_dir
        )

        # Save state
        state = {
            'status': 'success',
            'image_id': 'sha256:12345',
            'timestamp': '2024-01-01T00:00:00'
        }
        executor._save_build_state(state)

        # Verify file exists
        self.assertTrue(executor.build_state_file.exists())

        # Load state
        loaded_state = executor._load_build_state()
        self.assertEqual(loaded_state['status'], 'success')
        self.assertEqual(loaded_state['image_id'], 'sha256:12345')

    @patch('subprocess.Popen')
    def test_build_with_cli_mock(self, mock_popen):
        """Test building with Docker CLI (mocked)."""
        # Mock successful build
        mock_process = Mock()
        mock_process.stdout = ['Step 1/5 : FROM ubi8:latest\n']
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        executor = BuildExecutor(
            config=self.config,
            dockerfile_path=self.dockerfile_path,
            build_context=self.temp_dir,
            use_sdk=False,
            log_dir=self.log_dir
        )

        # Mock the _get_image_id_cli method
        with patch.object(executor, '_get_image_id_cli', return_value='sha256:12345'):
            success, image_id = executor._build_with_cli(no_cache=False, pull=True)

        self.assertTrue(success)

    def test_logging_setup(self):
        """Test that logging is properly configured."""
        executor = BuildExecutor(
            config=self.config,
            dockerfile_path=self.dockerfile_path,
            build_context=self.temp_dir,
            use_sdk=False,
            log_dir=self.log_dir
        )

        # Verify logger exists and has handlers
        self.assertIsNotNone(executor.logger)
        self.assertTrue(len(executor.logger.handlers) > 0)

        # Verify log directory exists
        self.assertTrue(os.path.exists(self.log_dir))

        # Verify at least one log file was created
        log_files = list(Path(self.log_dir).glob('*.log'))
        self.assertTrue(len(log_files) > 0)


class TestBuildExecutorIntegration(unittest.TestCase):
    """Integration tests for BuildExecutor (requires Docker)."""

    @unittest.skipUnless(
        os.getenv('RUN_INTEGRATION_TESTS') == '1',
        "Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable."
    )
    def test_actual_docker_build(self):
        """Test actual Docker build (requires Docker)."""
        temp_dir = tempfile.mkdtemp()

        try:
            # Create simple Dockerfile
            dockerfile_path = os.path.join(temp_dir, 'Dockerfile')
            with open(dockerfile_path, 'w') as f:
                f.write('FROM alpine:latest\n')
                f.write('RUN echo "test"\n')

            config = {
                'build_name': 'test-integration',
                'base_image': 'alpine:latest',
                'components': []
            }

            executor = BuildExecutor(
                config=config,
                dockerfile_path=dockerfile_path,
                build_context=temp_dir,
                use_sdk=False
            )

            success, image_id = executor.build(no_cache=True, pull=False)
            self.assertTrue(success)
            self.assertIsNotNone(image_id)

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
