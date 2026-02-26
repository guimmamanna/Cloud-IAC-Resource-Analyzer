#!/usr/bin/env python3
"""
CLI wrapper for the cloud-to-IaC resource analyzer.

Usage:
    python -m cloud_iac_analyzer.cli cloud.json iac.json report.json
"""

import os
import sys
import argparse
from pathlib import Path
from cloud_iac_analyzer.analyzer import generate_analysis_report


def validate_input_file(file_path: str) -> str:
    """Validate that the path points to an existing .json file."""
    path = Path(file_path)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"File not found: {file_path}")
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"Not a file: {file_path}")
    if path.suffix.lower() != '.json':
        raise argparse.ArgumentTypeError(f"File must be JSON: {file_path}")
    return str(path.absolute())


def validate_output_path(file_path: str) -> str:
    """Ensure the output directory exists (created if needed) and is writable."""
    path = Path(file_path)
    parent = path.parent
    if not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise argparse.ArgumentTypeError(f"Cannot create output directory {parent}: {e}")
    if not parent.is_dir():
        raise argparse.ArgumentTypeError(f"Output parent path is not a directory: {parent}")
    if not os.access(str(parent), os.W_OK):
        raise argparse.ArgumentTypeError(f"Output directory is not writable: {parent}")
    return str(path.absolute())


def main() -> int:
    parser = argparse.ArgumentParser(
        prog='cloud-iac-analyzer',
        description='Detect configuration drift between cloud resources and IaC declarations.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  cloud-iac-analyzer cloud.json iac.json report.json",
    )
    parser.add_argument('cloud_file',  type=validate_input_file,  help='Cloud resources JSON')
    parser.add_argument('iac_file',    type=validate_input_file,  help='IaC resource declarations JSON')
    parser.add_argument('output_file', type=validate_output_path, help='Output report path')

    args = parser.parse_args()

    try:
        generate_analysis_report(
            cloud_file=args.cloud_file,
            iac_file=args.iac_file,
            output_file=args.output_file,
        )
        return 0
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"[ERROR] Invalid data: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
