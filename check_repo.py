#!/usr/bin/env python3
"""
IBM Installation Manager Repository Checker

This script checks if specific IBM software offerings are available within
a given IBM Installation Manager repository using the imcl command-line tool.
"""

import argparse
import subprocess
import sys
import shutil


def check_imcl_available():
    """
    Check if the imcl command is available in the system PATH.
    
    Returns:
        bool: True if imcl is available, False otherwise
    """
    return shutil.which("imcl") is not None


def check_offerings(repo_path, required_offerings):
    """
    Uses imcl to check a repository for a list of required offerings.
    
    Args:
        repo_path (str): The absolute file path to the repository directory
        required_offerings (list): List of software offering IDs to check for
        
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    if not check_imcl_available():
        sys.stderr.write(
            "ERROR: 'imcl' command not found. Please ensure IBM Installation Manager "
            "is installed and 'imcl' is in your system PATH.\n"
        )
        return 127
    
    imcl_path = "imcl"
    command = [imcl_path, "listAvailablePackages", "-repositories", repo_path]

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
            "ERROR: 'imcl' command not found. Please ensure IBM Installation Manager "
            "is installed and 'imcl' is in your system PATH.\n"
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

    args = parser.parse_args()

    exit_code = check_offerings(args.repo, args.software)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
