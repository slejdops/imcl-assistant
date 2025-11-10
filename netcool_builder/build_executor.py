#!/usr/bin/env python3
"""
Build Executor for Netcool Docker Builder

Executes and monitors Docker builds with support for logging,
progress reporting, and failure recovery.
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import docker
    from docker.errors import BuildError, APIError, DockerException
    DOCKER_SDK_AVAILABLE = True
except ImportError:
    DOCKER_SDK_AVAILABLE = False


class BuildExecutionError(Exception):
    """Raised when a build execution fails."""
    pass


class BuildExecutor:
    """
    Executes Docker builds and manages build lifecycle.

    Supports both Docker SDK and command-line execution with
    comprehensive logging and error handling.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        dockerfile_path: str,
        build_context: str = '.',
        use_sdk: bool = True,
        log_dir: Optional[str] = None
    ):
        """
        Initialize the build executor.

        Args:
            config: Build configuration dictionary
            dockerfile_path: Path to the Dockerfile
            build_context: Docker build context directory
            use_sdk: Use Docker SDK if available (otherwise use CLI)
            log_dir: Directory for build logs (default: ./build_logs)
        """
        self.config = config
        self.dockerfile_path = Path(dockerfile_path)
        self.build_context = Path(build_context)
        self.use_sdk = use_sdk and DOCKER_SDK_AVAILABLE

        # Setup logging
        if log_dir is None:
            log_dir = Path('./build_logs')
        else:
            log_dir = Path(log_dir)

        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir = log_dir

        # Setup logger
        self.logger = self._setup_logger()

        # Initialize Docker client if using SDK
        self.docker_client = None
        if self.use_sdk:
            try:
                self.docker_client = docker.from_env()
                self.logger.info("Docker SDK initialized successfully")
            except DockerException as e:
                self.logger.warning(f"Failed to initialize Docker SDK: {e}")
                self.logger.info("Falling back to Docker CLI")
                self.use_sdk = False

        # Build state for resume functionality
        self.build_state_file = log_dir / 'build_state.json'
        self.build_state = self._load_build_state()

    def _setup_logger(self) -> logging.Logger:
        """Setup logging for build execution."""
        logger = logging.getLogger('netcool_builder')
        logger.setLevel(logging.DEBUG)

        # File handler
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.log_dir / f'build_{timestamp}.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        self.logger = logger
        self.logger.info(f"Logging to: {log_file}")

        return logger

    def _load_build_state(self) -> Dict[str, Any]:
        """Load previous build state for resume functionality."""
        if self.build_state_file.exists():
            try:
                with open(self.build_state_file, 'r') as f:
                    state = json.load(f)
                    self.logger.info(f"Loaded previous build state from {self.build_state_file}")
                    return state
            except Exception as e:
                self.logger.warning(f"Failed to load build state: {e}")

        return {}

    def _save_build_state(self, state: Dict[str, Any]) -> None:
        """Save current build state."""
        try:
            with open(self.build_state_file, 'w') as f:
                json.dump(state, f, indent=2)
            self.logger.debug(f"Saved build state to {self.build_state_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save build state: {e}")

    def _get_image_tags(self) -> List[str]:
        """Get list of tags for the image."""
        build_name = self.config['build_name']
        build_options = self.config.get('build_options', {})

        # Default tag
        tags = [build_name]

        # Add configured tags
        configured_tags = build_options.get('tags', [])
        for tag in configured_tags:
            if ':' not in tag:
                # Add build name prefix if not fully qualified
                tags.append(f"{build_name}:{tag}")
            else:
                tags.append(tag)

        # Add registry prefix if specified
        registry_config = build_options.get('registry', {})
        if 'url' in registry_config:
            registry_url = registry_config['url'].rstrip('/')
            tags = [f"{registry_url}/{tag}" for tag in tags]

        return tags

    def _get_build_args(self) -> Dict[str, str]:
        """Get build arguments."""
        return self.config.get('build_options', {}).get('build_args', {})

    def build(self, no_cache: bool = False, pull: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Execute the Docker build.

        Args:
            no_cache: Disable build cache
            pull: Always pull base image

        Returns:
            Tuple of (success: bool, image_id: Optional[str])

        Raises:
            BuildExecutionError: If build fails critically
        """
        self.logger.info("=" * 60)
        self.logger.info(f"Starting Docker build: {self.config['build_name']}")
        self.logger.info("=" * 60)

        start_time = time.time()

        try:
            if self.use_sdk:
                success, image_id = self._build_with_sdk(no_cache, pull)
            else:
                success, image_id = self._build_with_cli(no_cache, pull)

            elapsed_time = time.time() - start_time

            if success:
                self.logger.info("=" * 60)
                self.logger.info(f"✓ Build completed successfully in {elapsed_time:.2f}s")
                self.logger.info(f"  Image ID: {image_id}")
                self.logger.info("=" * 60)

                # Update build state
                self._save_build_state({
                    'status': 'success',
                    'image_id': image_id,
                    'timestamp': datetime.now().isoformat(),
                    'elapsed_time': elapsed_time
                })
            else:
                self.logger.error("=" * 60)
                self.logger.error(f"✗ Build failed after {elapsed_time:.2f}s")
                self.logger.error("=" * 60)

                # Update build state
                self._save_build_state({
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat(),
                    'elapsed_time': elapsed_time
                })

            return success, image_id

        except Exception as e:
            self.logger.error(f"Build execution error: {e}", exc_info=True)
            raise BuildExecutionError(f"Build failed: {e}")

    def _build_with_sdk(self, no_cache: bool, pull: bool) -> Tuple[bool, Optional[str]]:
        """
        Build using Docker SDK for Python.

        Args:
            no_cache: Disable build cache
            pull: Always pull base image

        Returns:
            Tuple of (success: bool, image_id: Optional[str])
        """
        self.logger.info("Building with Docker SDK")

        tags = self._get_image_tags()
        build_args = self._get_build_args()

        self.logger.info(f"Tags: {', '.join(tags)}")
        self.logger.info(f"Build context: {self.build_context}")
        self.logger.info(f"Dockerfile: {self.dockerfile_path}")

        try:
            # Build the image
            image, build_logs = self.docker_client.images.build(
                path=str(self.build_context),
                dockerfile=str(self.dockerfile_path.relative_to(self.build_context)),
                tag=tags[0],
                buildargs=build_args,
                nocache=no_cache,
                pull=pull,
                rm=True,  # Remove intermediate containers
                forcerm=True  # Always remove intermediate containers
            )

            # Process build logs
            for log in build_logs:
                if 'stream' in log:
                    msg = log['stream'].rstrip()
                    if msg:
                        self.logger.info(f"  {msg}")
                elif 'error' in log:
                    self.logger.error(f"  ERROR: {log['error']}")
                elif 'status' in log:
                    self.logger.debug(f"  {log['status']}")

            # Tag with additional tags
            for tag in tags[1:]:
                image.tag(tag)
                self.logger.info(f"Tagged image as: {tag}")

            return True, image.id

        except BuildError as e:
            self.logger.error(f"Build error: {e}")
            for log in e.build_log:
                if 'stream' in log:
                    self.logger.error(f"  {log['stream'].rstrip()}")
            return False, None

        except APIError as e:
            self.logger.error(f"Docker API error: {e}")
            return False, None

    def _build_with_cli(self, no_cache: bool, pull: bool) -> Tuple[bool, Optional[str]]:
        """
        Build using Docker command-line interface.

        Args:
            no_cache: Disable build cache
            pull: Always pull base image

        Returns:
            Tuple of (success: bool, image_id: Optional[str])
        """
        self.logger.info("Building with Docker CLI")

        tags = self._get_image_tags()
        build_args = self._get_build_args()

        # Build docker command
        cmd = ['docker', 'build']

        # Add tags
        for tag in tags:
            cmd.extend(['-t', tag])

        # Add build args
        for key, value in build_args.items():
            cmd.extend(['--build-arg', f'{key}={value}'])

        # Add options
        if no_cache:
            cmd.append('--no-cache')
        if pull:
            cmd.append('--pull')

        # Add dockerfile and context
        cmd.extend(['-f', str(self.dockerfile_path)])
        cmd.append(str(self.build_context))

        self.logger.info(f"Command: {' '.join(cmd)}")

        try:
            # Execute build
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Stream output
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    self.logger.info(f"  {line}")

            # Wait for completion
            return_code = process.wait()

            if return_code == 0:
                # Get image ID
                image_id = self._get_image_id_cli(tags[0])
                return True, image_id
            else:
                self.logger.error(f"Docker build failed with exit code {return_code}")
                return False, None

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {e}")
            return False, None

        except FileNotFoundError:
            self.logger.error("Docker command not found. Is Docker installed?")
            return False, None

    def _get_image_id_cli(self, tag: str) -> Optional[str]:
        """Get image ID using docker inspect."""
        try:
            result = subprocess.run(
                ['docker', 'inspect', '--format={{.Id}}', tag],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def push(self, tag: Optional[str] = None) -> bool:
        """
        Push image to registry.

        Args:
            tag: Specific tag to push (default: push all tags)

        Returns:
            True if push succeeded
        """
        registry_config = self.config.get('build_options', {}).get('registry', {})

        if 'url' not in registry_config:
            self.logger.warning("No registry configured, skipping push")
            return False

        tags_to_push = [tag] if tag else self._get_image_tags()

        self.logger.info("=" * 60)
        self.logger.info("Pushing images to registry")
        self.logger.info("=" * 60)

        all_success = True

        for image_tag in tags_to_push:
            self.logger.info(f"Pushing {image_tag}...")

            if self.use_sdk:
                success = self._push_with_sdk(image_tag)
            else:
                success = self._push_with_cli(image_tag)

            if success:
                self.logger.info(f"✓ Successfully pushed {image_tag}")
            else:
                self.logger.error(f"✗ Failed to push {image_tag}")
                all_success = False

        return all_success

    def _push_with_sdk(self, tag: str) -> bool:
        """Push using Docker SDK."""
        try:
            self.docker_client.images.push(tag)
            return True
        except APIError as e:
            self.logger.error(f"Failed to push {tag}: {e}")
            return False

    def _push_with_cli(self, tag: str) -> bool:
        """Push using Docker CLI."""
        try:
            result = subprocess.run(
                ['docker', 'push', tag],
                capture_output=True,
                text=True,
                check=True
            )
            self.logger.debug(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to push {tag}: {e.stderr}")
            return False


if __name__ == '__main__':
    # Simple test
    import json

    if len(sys.argv) != 3:
        print("Usage: python build_executor.py <config.json> <dockerfile>")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        config = json.load(f)

    executor = BuildExecutor(config, sys.argv[2])
    success, image_id = executor.build()

    sys.exit(0 if success else 1)
