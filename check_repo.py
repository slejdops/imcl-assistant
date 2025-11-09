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


def check_imcl_available(imcl_path):
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


def find_repositories(root_path):
    """
    Recursively search for IBM Installation Manager repositories.

    Searches for directories containing repository.config files, which
    indicate IBM IM repository locations.

    Args:
        root_path (str): Root directory to search

    Returns:
        list: List of repository paths found
    """
    repositories = []

    if not os.path.isdir(root_path):
        return [root_path]

    for dirpath, dirnames, filenames in os.walk(root_path):
        if 'repository.config' in filenames:
            repositories.append(dirpath)

    if not repositories:
        repositories.append(root_path)

    return repositories


def check_offerings(repo_path, required_offerings, imcl_path):
    """
    Uses imcl to check a repository for a list of required offerings.

    Args:
        repo_path (str): The absolute file path to the repository directory
        required_offerings (list): List of software offering IDs to check for
        imcl_path (str): Path to the imcl binary

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    if not check_imcl_available(imcl_path):
        sys.stderr.write(
            f"ERROR: 'imcl' command not found at '{imcl_path}'. "
            "Please ensure IBM Installation Manager is installed and the path is correct.\n"
        )
        return 127

    repositories = find_repositories(repo_path)

    if len(repositories) > 1:
        print(f"Found {len(repositories)} nested repositories, searching all...")

    repo_list = ",".join(repositories)
    command = [imcl_path, "listAvailablePackages", "-repositories", repo_list]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=300
        )

        available_packages = result.stdout.strip().split('\n')
        available_packages = [pkg.strip() for pkg in available_packages if pkg.strip()]

        missing_packages = []
        for req_pkg in required_offerings:
            found = any(pkg.startswith(req_pkg) for pkg in available_packages)
            if not found:
                missing_packages.append(req_pkg)

        if not missing_packages:
            print("SUCCESS: All required offerings are available in the repository.")
            return 0
        else:
            sys.stderr.write("ERROR: The following required offerings were NOT found:\n")
            for pkg in missing_packages:
                sys.stderr.write(f"- {pkg}\n")
            return 1

    except FileNotFoundError:
        sys.stderr.write(
            f"ERROR: 'imcl' command not found at '{imcl_path}'. "
            "Please ensure IBM Installation Manager is installed and the path is correct.\n"
        )
        return 127
    except subprocess.TimeoutExpired:
        sys.stderr.write(
            "ERROR: 'imcl' command timed out after 300 seconds. "
            "The repository may be too large or inaccessible.\n"
        )
        return 124
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"ERROR: 'imcl' command failed with exit code {e.returncode}.\n")
        if e.stderr:
            sys.stderr.write(f"Details:\n{e.stderr}\n")
        return e.returncode
    except Exception as e:
        sys.stderr.write(f"ERROR: An unexpected error occurred: {e}\n")
        return 2


def main():
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
  %(prog)s --repo /opt/ibm/repo --software com.ibm.websphere.ND.v90 \\
      --imcl-path /opt/IBM/InstallationManager/eclipse/tools/imcl
        """
    )

    parser.add_argument(
        "-r", "--repo",
        required=True,
        help="The absolute file path to the repository directory (e.g., /opt/ibm/repo)"
    )

    parser.add_argument(
        "-s", "--software",
        required=True,
        nargs='+',
        help="One or more software offering IDs to check for (e.g., com.ibm.websphere.ND.v90)"
    )

    parser.add_argument(
        "-i", "--imcl-path",
        default="imcl",
        help="Path to the imcl binary (default: 'imcl' from PATH)"
    )

    args = parser.parse_args()

    exit_code = check_offerings(args.repo, args.software, args.imcl_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
