#!/usr/bin/env python3
"""
Netcool Docker Image Builder

Main CLI tool for building Docker images containing IBM Netcool/OMNIbus
system components. Orchestrates configuration parsing, Dockerfile generation,
and Docker build execution.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add netcool_builder to path
sys.path.insert(0, str(Path(__file__).parent))

from netcool_builder.config_parser import (
    ConfigParser, ConfigValidationError, load_and_validate_config
)
from netcool_builder.dockerfile_generator import DockerfileGenerator
from netcool_builder.build_executor import BuildExecutor, BuildExecutionError


__version__ = '1.0.0'


def setup_arg_parser() -> argparse.ArgumentParser:
    """Setup command-line argument parser."""
    parser = argparse.ArgumentParser(
        description='Netcool Docker Image Builder - Build Docker images for IBM Netcool/OMNIbus components',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate Dockerfile only
  %(prog)s --config examples/objectserver.yaml --generate-only

  # Build image
  %(prog)s --config examples/objectserver.yaml --build

  # Build and push to registry
  %(prog)s --config examples/objectserver.yaml --build --push

  # Build with custom output directory
  %(prog)s --config examples/objectserver.yaml --build --output ./build

  # Validate configuration only
  %(prog)s --config examples/objectserver.yaml --validate

  # Build with no cache
  %(prog)s --config examples/objectserver.yaml --build --no-cache

Version: %(prog)s v{}
        """.format(__version__)
    )

    # Required arguments
    parser.add_argument(
        '-c', '--config',
        required=True,
        help='Path to configuration file (YAML or JSON)'
    )

    # Action arguments
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        '--validate',
        action='store_true',
        help='Validate configuration only (no build)'
    )
    action_group.add_argument(
        '--generate-only',
        action='store_true',
        help='Generate Dockerfile only (no build)'
    )
    action_group.add_argument(
        '--build',
        action='store_true',
        help='Build Docker image'
    )

    # Build options
    parser.add_argument(
        '--push',
        action='store_true',
        help='Push image to registry after successful build (requires --build)'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Build without using cache'
    )
    parser.add_argument(
        '--no-pull',
        action='store_true',
        help='Do not pull base image before building'
    )

    # Output options
    parser.add_argument(
        '-o', '--output',
        default='./build',
        help='Output directory for Dockerfile and build artifacts (default: ./build)'
    )
    parser.add_argument(
        '--log-dir',
        help='Directory for build logs (default: ./build_logs)'
    )

    # Execution options
    parser.add_argument(
        '--use-cli',
        action='store_true',
        help='Use Docker CLI instead of Docker SDK'
    )

    # Information
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    return parser


def validate_configuration(config_path: str, verbose: bool = False) -> ConfigParser:
    """
    Validate configuration file.

    Args:
        config_path: Path to configuration file
        verbose: Enable verbose output

    Returns:
        Validated ConfigParser instance

    Raises:
        SystemExit: If validation fails
    """
    print(f"Validating configuration: {config_path}")

    try:
        parser = load_and_validate_config(config_path)
        print(f"✓ Configuration validated successfully")

        if verbose:
            print(f"\n  Build name: {parser.get_build_name()}")
            print(f"  Base image: {parser.get_base_image()}")
            print(f"  Components: {len(parser.get_components())}")
            for idx, comp in enumerate(parser.get_components(), 1):
                print(f"    {idx}. {comp['name']} ({comp['type']})")
            print(f"  Multi-stage: {parser.is_multi_stage()}")

        return parser

    except FileNotFoundError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ConfigValidationError as e:
        print(f"✗ Configuration validation failed: {e}", file=sys.stderr)
        sys.exit(1)


def generate_dockerfile(parser: ConfigParser, output_dir: str, verbose: bool = False) -> str:
    """
    Generate Dockerfile from configuration.

    Args:
        parser: Validated ConfigParser instance
        output_dir: Output directory
        verbose: Enable verbose output

    Returns:
        Path to generated Dockerfile
    """
    print(f"\nGenerating Dockerfile...")

    config = parser.get_config()
    generator = DockerfileGenerator(config, output_dir)

    dockerfile_path = generator.generate()
    dockerignore_path = generator.generate_dockerignore()

    print(f"✓ Generated Dockerfile: {dockerfile_path}")
    print(f"✓ Generated .dockerignore: {dockerignore_path}")

    if verbose:
        print("\nDockerfile preview:")
        print("-" * 60)
        with open(dockerfile_path, 'r') as f:
            for line in f.readlines()[:20]:  # Show first 20 lines
                print(f"  {line.rstrip()}")
        print("  ...")
        print("-" * 60)

    return dockerfile_path


def build_image(
    parser: ConfigParser,
    dockerfile_path: str,
    output_dir: str,
    no_cache: bool = False,
    pull: bool = True,
    use_cli: bool = False,
    log_dir: str = None
) -> tuple:
    """
    Build Docker image.

    Args:
        parser: Validated ConfigParser instance
        dockerfile_path: Path to Dockerfile
        output_dir: Build context directory
        no_cache: Disable build cache
        pull: Pull base image
        use_cli: Use Docker CLI instead of SDK
        log_dir: Directory for logs

    Returns:
        Tuple of (success: bool, image_id: Optional[str])
    """
    print(f"\nBuilding Docker image...")

    config = parser.get_config()
    executor = BuildExecutor(
        config=config,
        dockerfile_path=dockerfile_path,
        build_context=output_dir,
        use_sdk=not use_cli,
        log_dir=log_dir
    )

    try:
        success, image_id = executor.build(no_cache=no_cache, pull=pull)
        return success, image_id, executor
    except BuildExecutionError as e:
        print(f"✗ Build execution failed: {e}", file=sys.stderr)
        return False, None, executor


def push_image(executor: BuildExecutor) -> bool:
    """
    Push image to registry.

    Args:
        executor: BuildExecutor instance

    Returns:
        True if push succeeded
    """
    print(f"\nPushing image to registry...")

    try:
        success = executor.push()
        return success
    except Exception as e:
        print(f"✗ Push failed: {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    parser = setup_arg_parser()
    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print(f"  Netcool Docker Image Builder v{__version__}")
    print("=" * 70)

    # Validate configuration
    config_parser = validate_configuration(args.config, args.verbose)

    # If only validation requested, exit
    if args.validate:
        print("\n✓ Configuration is valid")
        sys.exit(0)

    # Generate Dockerfile
    dockerfile_path = generate_dockerfile(config_parser, args.output, args.verbose)

    # If only generation requested, exit
    if args.generate_only:
        print("\n✓ Dockerfile generation complete")
        sys.exit(0)

    # Build image if requested
    if args.build:
        success, image_id, executor = build_image(
            parser=config_parser,
            dockerfile_path=dockerfile_path,
            output_dir=args.output,
            no_cache=args.no_cache,
            pull=not args.no_pull,
            use_cli=args.use_cli,
            log_dir=args.log_dir
        )

        if not success:
            print("\n✗ Build failed")
            sys.exit(1)

        print(f"\n✓ Build successful")
        print(f"  Image ID: {image_id}")

        # Push if requested
        if args.push:
            push_success = push_image(executor)
            if not push_success:
                print("\n✗ Push failed")
                sys.exit(1)
            print("\n✓ Push successful")

        print("\n" + "=" * 70)
        print("  Build completed successfully!")
        print("=" * 70)
        sys.exit(0)

    # If no action specified, show help
    if not any([args.validate, args.generate_only, args.build]):
        print("\n✗ No action specified. Use --validate, --generate-only, or --build")
        print("   Run with --help for usage information")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
