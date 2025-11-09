#!/usr/bin/env python3
"""
IBM Installation Manager Repository Checker

This script checks if specific IBM software offerings are available within
a given IBM Installation Manager repository using the imcl command-line tool.
"""

import argparse
import os
import subprocess
import sys
import shutil
import logging
from typing import List, Optional, Tuple

# --- Constants ---

# Timeouts in seconds
IMCL_LIST_TIMEOUT: int = 300
IMCL_DRY_RUN_TIMEOUT: int = 600

# Exit Codes
EXIT_SUCCESS: int = 0
EXIT_ERROR: int = 1
EXIT_UNEXPECTED: int = 2
EXIT_TIMEOUT: int = 124
EXIT_NOT_FOUND: int = 127

# Configure logging
log = logging.getLogger(__name__)


def check_imcl_available(imcl_path: str) -> bool:
    """
    Check if the imcl command is available.

    Args:
        imcl_path (str): Path to the imcl binary

    Returns:
        bool: True if imcl is available, False otherwise
    """
    if os.path.isabs(imcl_path):
        return os.path.isfile(imcl_path) and os.access(imcl_path, os.X_OK)
    return shutil.which(imcl_path) is not None


def find_repositories(root_path: str) -> List[str]:
    """
    Recursively search for IBM Installation Manager repositories.

    Searches for directories containing repository.config files, which
    indicate IBM IM repository locations.

    Args:
        root_path (str): Root directory to search

    Returns:
        list[str]: List of repository paths found
    """
    repositories = []

    if not os.path.isdir(root_path):
        return [root_path]

    for dirpath, _, filenames in os.walk(root_path):
        if 'repository.config' in filenames:
            log.debug(f"Found repository at: {dirpath}")
            repositories.append(dirpath)

    if not repositories:
        log.warning(f"No 'repository.config' found under '{root_path}'. "
                    "Using the root path directly.")
        repositories.append(root_path)

    return repositories


def _run_imcl_command(
    command: List[str],
    timeout: int
) -> Optional[subprocess.CompletedProcess]:
    """
    Internal helper to run an imcl command and handle common errors.

    Args:
        command (List[str]): The command and arguments to run.
        timeout (int): Timeout in seconds.

    Returns:
        Optional[subprocess.CompletedProcess]: The result object, or None on error.
    """
    log.debug(f"Running command: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # We check the returncode manually
        )
        return result

    except FileNotFoundError:
        log.error(
            f"ERROR: 'imcl' command not found at '{command[0]}'. "
            "Please ensure IBM Installation Manager is installed and the path is correct."
        )
        return None
    except subprocess.TimeoutExpired:
        log.error(
            f"ERROR: 'imcl' command timed out after {timeout} seconds. "
            "The repository may be too large or inaccessible."
        )
        return None
    except Exception as e:
        log.error(f"ERROR: An unexpected error occurred: {e}")
        return None


def list_offerings(repo_path: str, imcl_path: str) -> int:
    """
    List all available offerings in the repository.

    Args:
        repo_path (str): The absolute file path to the repository directory
        imcl_path (str): Path to the imcl binary

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    repositories = find_repositories(repo_path)
    if len(repositories) > 1:
        log.info(f"Found {len(repositories)} nested repositories, listing all offerings...\n")

    repo_list = ",".join(repositories)
    command = [imcl_path, "listAvailablePackages", "-repositories", repo_list]

    result = _run_imcl_command(command, IMCL_LIST_TIMEOUT)

    if result is None:
        return EXIT_ERROR  # Error already logged by helper

    if result.returncode != 0:
        log.error(f"ERROR: 'imcl' command failed with exit code {result.returncode}.")
        if result.stderr:
            log.error(f"Details:\n{result.stderr}")
        return result.returncode

    available_packages = [pkg.strip() for pkg in result.stdout.strip().split('\n') if pkg.strip()]

    if available_packages:
        log.info(f"Available offerings ({len(available_packages)} found):")
        for pkg in available_packages:
            print(f"  {pkg}")  # Use print for clean, parsable output
        return EXIT_SUCCESS
    else:
        log.info("No offerings found in the repository.")
        return EXIT_SUCCESS


def dry_run_install(repo_path: str, package_id: str, imcl_path: str, install_dir: str) -> int:
    """
    Perform a dry-run installation of a package.

    Args:
        repo_path (str): The absolute file path to the repository directory
        package_id (str): The package ID to install
        imcl_path (str): Path to the imcl binary
        install_dir (str): Installation directory for the dry-run

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    repositories = find_repositories(repo_path)
    if len(repositories) > 1:
        log.info(f"Found {len(repositories)} nested repositories, searching all...\n")

    repo_list = ",".join(repositories)

    log.info(f"Performing dry-run installation of: {package_id}")
    log.info(f"Repository: {repo_path}")
    log.info(f"Installation directory: {install_dir}\n")

    command = [
        imcl_path, "install", package_id,
        "-repositories", repo_list,
        "-installationDirectory", install_dir,
        "-acceptLicense",
        "-showVerboseProgress"
    ]

    result = _run_imcl_command(command, IMCL_DRY_RUN_TIMEOUT)

    if result is None:
        return EXIT_ERROR  # Error already logged by helper

    # Print output regardless of exit code for user to review
    print("--- Dry-run Output (stdout) ---")
    print(result.stdout)
    print("--- End of stdout ---")


    if result.stderr:
        print("\n--- Warnings/Errors (stderr) ---")
        print(result.stderr)
        print("--- End of stderr ---")

    if result.returncode == 0:
        log.info("\nDry-run completed successfully.")
    else:
        log.error(f"\nDry-run failed with exit code {result.returncode}.")

    return result.returncode


def check_offerings(repo_path: str, required_offerings: List[str], imcl_path: str) -> int:
    """
    Uses imcl to check a repository for a list of required offerings.

    Args:
        repo_path (str): The absolute file path to the repository directory
        required_offerings (list): List of software offering IDs to check for
        imcl_path (str): Path to the imcl binary

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    repositories = find_repositories(repo_path)
    if len(repositories) > 1:
        log.info(f"Found {len(repositories)} nested repositories, searching all...")

    repo_list = ",".join(repositories)
    command = [imcl_path, "listAvailablePackages", "-repositories", repo_list]

    result = _run_imcl_command(command, IMCL_LIST_TIMEOUT)

    if result is None:
        return EXIT_ERROR  # Error already logged by helper

    if result.returncode != 0:
        log.error(f"ERROR: 'imcl' command failed with exit code {result.returncode}.")
        if result.stderr:
            log.error(f"Details:\n{result.stderr}")
        return result.returncode

    available_packages = [pkg.strip() for pkg in result.stdout.strip().split('\n') if pkg.strip()]

    missing_packages = []
    for req_pkg in required_offerings:
        found = any(pkg.startswith(req_pkg) for pkg in available_packages)
        if not found:
            missing_packages.append(req_pkg)

    if not missing_packages:
        log.info("SUCCESS: All required offerings are available in the repository.")
        return EXIT_SUCCESS
    else:
        log.error("ERROR: The following required offerings were NOT found:")
        for pkg in missing_packages:
            log.error(f"- {pkg}")
        return EXIT_ERROR


def main() -> None:
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(
        description="Check IBM Installation Manager repository for required offerings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --repo /opt/ibm/repo --software com.ibm.websphere.ND.v90
  %(prog)s -r /opt/ibm/repo -s com.ibm.websphere.ND.v90 com.ibm.java.sdk.v8

  # List all available offerings
  %(prog)s --repo /opt/ibm/repo --list-offerings

  # Perform a verbose dry-run
  %(prog)s -r /opt/ibm/repo -d com.ibm.websphere.ND.v90 --install-dir /tmp/test-install -v

  %(prog)s --repo /opt/ibm/repo --software com.ibm.websphere.ND.v90 \\
      --imcl-path /opt/IBM/InstallationManager/eclipse/tools/imcl
        """
    )

    parser.add_argument(
        "-r", "--repo",
        required=True,
        help="The absolute file path to the repository directory (e.g., /opt/ibm/repo)"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-s", "--software",
        nargs='+',
        help="One or more software offering IDs to check for (e.g., com.ibm.websphere.ND.v90)"
    )
    group.add_argument(
        "-l", "--list-offerings",
        action="store_true",
        help="List all available offerings in the repository"
    )
    group.add_argument(
        "-d", "--dry-run",
        metavar="PACKAGE_ID",
        help="Perform a dry-run installation of the specified package"
    )

    parser.add_argument(
        "-i", "--imcl-path",
        default="imcl",
        help="Path to the imcl binary (default: 'imcl' from PATH)"
    )
    parser.add_argument(
        "--install-dir",
        help="Installation directory for dry-run (required with --dry-run)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging"
    )

    args = parser.parse_args()

    # --- Setup Logging ---
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s"
    )

    # --- Validate Arguments ---
    if args.dry_run and not args.install_dir:
        log.error("ERROR: --install-dir is required when using --dry-run")
        sys.exit(EXIT_ERROR)

    if not args.software and not args.list_offerings and not args.dry_run:
        log.error("ERROR: Either --software, --list-offerings, or --dry-run must be specified.")
        parser.print_help()
        sys.exit(EXIT_ERROR)

    # --- Check for imcl early ---
    if not check_imcl_available(args.imcl_path):
        log.error(
            f"ERROR: 'imcl' command not found at '{args.imcl_path}'. "
            "Please ensure IBM Installation Manager is installed and "
            "the path is correct or available in PATH."
        )
        sys.exit(EXIT_NOT_FOUND)

    log.debug(f"Using imcl at: {shutil.which(args.imcl_path) or args.imcl_path}")

    # --- Run main logic ---
    exit_code = EXIT_SUCCESS
    try:
        if args.list_offerings:
            exit_code = list_offerings(args.repo, args.imcl_path)
        elif args.dry_run:
            exit_code = dry_run_install(
                args.repo,
                args.dry_run,
                args.imcl_path,
                args.install_dir
            )
        elif args.software:
            exit_code = check_offerings(args.repo, args.software, args.imcl_path)

    except Exception as e:
        log.error(f"An unexpected critical error occurred: {e}", exc_info=True)
        exit_code = EXIT_UNEXPECTED

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
