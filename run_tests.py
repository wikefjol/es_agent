#!/usr/bin/env python3
"""Test runner script with different test categories."""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    result = subprocess.run(cmd, shell=True, capture_output=False)
    
    if result.returncode != 0:
        print(f"❌ {description} failed with return code {result.returncode}")
        return False
    else:
        print(f"✅ {description} completed successfully")
        return True


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run ES Agent tests")
    parser.add_argument(
        "--category",
        choices=[
            "all", "unit", "integration", "performance", "error_handling",
            "realistic_data", "slow", "fast", "end_to_end", "quick"
        ],
        default="all",
        help="Test category to run"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run tests with coverage reporting"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (requires pytest-xdist)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Base command
    base_cmd = "python -m pytest"
    
    # Add coverage if requested
    if args.coverage:
        base_cmd += " --cov=src --cov-report=html --cov-report=term-missing"
    
    # Add parallel execution if requested
    if args.parallel:
        base_cmd += " -n auto"
    
    # Add verbosity
    if args.verbose:
        base_cmd += " -v"
    
    # Define test commands for different categories
    test_commands = {
        "all": f"{base_cmd} tests/",
        "unit": f"{base_cmd} -m unit tests/unit/",
        "integration": f"{base_cmd} -m integration tests/integration/",
        "performance": f"{base_cmd} -m performance tests/",
        "error_handling": f"{base_cmd} -m error_handling tests/",
        "realistic_data": f"{base_cmd} -m realistic_data tests/",
        "slow": f"{base_cmd} -m slow tests/",
        "fast": f"{base_cmd} -m 'not slow' tests/",
        "end_to_end": f"{base_cmd} -m end_to_end tests/integration/",
        "quick": f"{base_cmd} -m 'unit and not slow' tests/unit/",
    }
    
    # Run selected test category
    if args.category in test_commands:
        success = run_command(
            test_commands[args.category],
            f"{args.category.title()} tests"
        )
        
        if not success:
            sys.exit(1)
    else:
        print(f"Unknown test category: {args.category}")
        sys.exit(1)
    
    print(f"\n✅ All {args.category} tests completed successfully!")


if __name__ == "__main__":
    main()