#!/usr/bin/env python3
"""
Enhanced test runner script for ProxTagger

Supports both unit/integration tests and live testing against real Proxmox.
Live tests require PROXTAGGER_LIVE_TESTS=true environment variable.
"""

import sys
import subprocess
import argparse
import os
import json
from pathlib import Path
from typing import Dict, List


def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False


def validate_live_test_environment() -> Dict[str, bool]:
    """Validate environment for live testing"""
    checks = {}
    
    # Check if live testing is enabled
    checks["live_tests_enabled"] = os.getenv("PROXTAGGER_LIVE_TESTS", "false").lower() == "true"
    
    # Check if config file exists
    config_file = Path("config.json")
    checks["config_exists"] = config_file.exists()
    
    if checks["config_exists"]:
        try:
            with open(config_file) as f:
                config = json.load(f)
            
            required_fields = ["PROXMOX_HOST", "PROXMOX_USER", "PROXMOX_TOKEN_NAME", "PROXMOX_TOKEN_VALUE"]
            checks["config_complete"] = all(field in config for field in required_fields)
            checks["config_valid"] = True
        except Exception:
            checks["config_complete"] = False
            checks["config_valid"] = False
    else:
        checks["config_complete"] = False
        checks["config_valid"] = False
    
    # Check for test VMs (requires importing modules)
    checks["test_vms_available"] = False
    if checks["live_tests_enabled"] and checks["config_complete"]:
        try:
            # Import here to avoid import errors if modules not available
            sys.path.insert(0, str(Path.cwd()))
            from tests.live_config import live_config
            test_vms = live_config.get_test_vms() if live_config else []
            checks["test_vms_available"] = len(test_vms) > 0
            checks["test_vm_count"] = len(test_vms)
        except Exception as e:
            checks["test_vms_available"] = False
            checks["import_error"] = str(e)
    
    # Additional environment checks can be added here
    
    return checks


def print_live_test_status():
    """Print status of live testing configuration"""
    print("\n" + "="*60)
    print("LIVE TEST ENVIRONMENT STATUS")
    print("="*60)
    
    checks = validate_live_test_environment()
    
    status_items = [
        ("Live testing enabled", checks.get("live_tests_enabled", False)),
        ("Config file exists", checks.get("config_exists", False)),
        ("Config complete", checks.get("config_complete", False)),
        ("Test VMs available", checks.get("test_vms_available", False)),
    ]
    
    for item, status in status_items:
        icon = "✅" if status else "❌"
        print(f"{icon} {item}")
    
    if "test_vm_count" in checks:
        print(f"📊 Test VMs found: {checks['test_vm_count']}")
    
    if "import_error" in checks:
        print(f"⚠️  Import error: {checks['import_error']}")
    
    overall_ready = all([
        checks.get("live_tests_enabled", False),
        checks.get("config_complete", False),
        checks.get("test_vms_available", False)
    ])
    
    print(f"\n{'🟢' if overall_ready else '🔴'} Live testing: {'READY' if overall_ready else 'NOT READY'}")
    
    if not overall_ready:
        print("\nTo enable live testing:")
        if not checks.get("live_tests_enabled"):
            print("  export PROXTAGGER_LIVE_TESTS=true")
        if not checks.get("config_complete"):
            print("  Ensure config.json has complete Proxmox credentials")
        if not checks.get("test_vms_available"):
            print("  Create VMs for testing")
    
    print("="*60)




def main():
    parser = argparse.ArgumentParser(description="Run ProxTagger tests")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--live", action="store_true", help="Run live tests against real Proxmox")
    parser.add_argument("--templates", action="store_true", help="Run quick templates tests")
    parser.add_argument("--status", action="store_true", help="Show live test environment status")
    parser.add_argument("--coverage", action="store_true", help="Run with coverage report")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--failfast", "-x", action="store_true", help="Stop on first failure")
    parser.add_argument("--pattern", "-k", help="Run tests matching pattern")
    
    args = parser.parse_args()
    
    # Handle utility commands first
    if args.status:
        print_live_test_status()
        return 0
    
    # Set environment for live tests
    if args.live:
        os.environ["PROXTAGGER_LIVE_TESTS"] = "true"
        print("🔴 LIVE TESTING ENABLED - Tests will run against real Proxmox instance")
        print("   Make sure you have VMs you can safely test with!")
    
    # Base pytest command
    cmd = ["python3", "-m", "pytest"]
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    
    # Add fail fast
    if args.failfast:
        cmd.append("-x")
    
    # Add pattern matching
    if args.pattern:
        cmd.extend(["-k", args.pattern])
    
    # Add test markers
    if args.unit and not args.integration and not args.live and not args.templates:
        cmd.extend(["-m", "unit"])
    elif args.integration and not args.unit and not args.live and not args.templates:
        cmd.extend(["-m", "integration"])
    elif args.live:
        if args.templates:
            cmd.extend(["-m", "live and templates"])
        else:
            cmd.extend(["-m", "live"])
    elif args.templates:
        cmd.extend(["-m", "templates"])
    elif not args.unit and not args.integration and not args.live and not args.templates:
        # Run unit and integration tests by default (exclude live)
        cmd.extend(["-m", "unit or integration"])
    
    # Add coverage options
    if args.coverage or args.html:
        cmd.extend([
            "--cov=.",
            "--cov-report=term-missing",
            "--cov-exclude=tests/*",
            "--cov-exclude=static/*",
            "--cov-exclude=templates/*"
        ])
        
        if args.html:
            cmd.extend(["--cov-report=html:htmlcov"])
    
    # Add test directory
    cmd.append("tests/")
    
    # Run tests
    success = run_command(cmd, "Running tests")
    
    if success:
        print(f"\n🎉 All tests passed!")
        
        if args.html:
            print(f"\n📊 HTML coverage report generated in htmlcov/index.html")
            print(f"   Open file://{Path.cwd() / 'htmlcov' / 'index.html'} in your browser")
    else:
        print(f"\n💥 Some tests failed!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())