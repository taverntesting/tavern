#!/usr/bin/env python3
"""
Tavern Getting Started Examples Runner
=====================================

This script runs all the getting started examples and provides a comprehensive
demonstration of Tavern's capabilities.

Usage:
    python run_examples.py [--server-only] [--tests-only] [--all]

Examples:
    python run_examples.py --server-only    # Just start the test server
    python run_examples.py --tests-only     # Run tests (assumes server is running)
    python run_examples.py --all            # Start server and run all tests
"""

import argparse
import subprocess
import sys
import time
import os
import signal
import threading
from pathlib import Path

def print_banner():
    """Print a nice banner for the examples runner."""
    print("=" * 60)
    print("🎯 Tavern Getting Started Examples")
    print("=" * 60)
    print("This will demonstrate:")
    print("  • Basic API testing with YAML")
    print("  • Authentication and session management")
    print("  • Pytest marks and fixtures")
    print("  • External functions and custom validation")
    print("  • Error handling and edge cases")
    print("=" * 60)

def start_server():
    """Start the test server in the background."""
    print("🚀 Starting test server...")

    # Check if server is already running
    try:
        import requests
        response = requests.get("http://localhost:5000/health", timeout=2)
        if response.status_code == 200:
            print("✅ Test server is already running")
            return None
    except:
        pass

    # Start the server
    server_process = subprocess.Popen(
        [sys.executable, "server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    print("⏳ Waiting for server to start...")
    for i in range(10):
        try:
            import requests
            response = requests.get("http://localhost:5000/health", timeout=2)
            if response.status_code == 200:
                print("✅ Test server started successfully")
                return server_process
        except:
            time.sleep(1)
            print(f"⏳ Still waiting... ({i+1}/10)")

    print("❌ Failed to start test server")
    return None

def stop_server(server_process):
    """Stop the test server."""
    if server_process:
        print("🛑 Stopping test server...")
        server_process.terminate()
        server_process.wait()
        print("✅ Test server stopped")

def run_tests(test_file, description):
    """Run a specific test file."""
    print(f"\n🧪 Running {description}...")
    print("-" * 40)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v"],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
        else:
            print(f"❌ {description} - FAILED")
            print("Error output:")
            print(result.stderr)

        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False

def run_all_examples():
    """Run all the getting started examples."""
    examples = [
        ("test_basic_api.tavern.yaml", "Basic API Testing"),
        ("test_marks_and_fixtures.tavern.yaml", "Pytest Marks & Fixtures"),
        ("test_external_functions.tavern.yaml", "External Functions"),
    ]

    results = []
    for test_file, description in examples:
        success = run_tests(test_file, description)
        results.append((description, success))

    return results

def print_summary(results):
    """Print a summary of test results."""
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    passed = 0
    for description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{description:<30} {status}")
        if success:
            passed += 1

    print("-" * 60)
    print(f"Total: {len(results)} tests, {passed} passed, {len(results) - passed} failed")

    if passed == len(results):
        print("🎉 All tests passed! You're ready to use Tavern!")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

    print("=" * 60)

def main():
    """Main function to run the examples."""
    parser = argparse.ArgumentParser(description="Run Tavern getting started examples")
    parser.add_argument("--server-only", action="store_true", help="Only start the test server")
    parser.add_argument("--tests-only", action="store_true", help="Only run tests (assumes server is running)")
    parser.add_argument("--all", action="store_true", help="Start server and run all tests")

    args = parser.parse_args()

    print_banner()

    server_process = None

    try:
        if args.server_only:
            server_process = start_server()
            if server_process:
                print("\n🔄 Server is running. Press Ctrl+C to stop.")
                server_process.wait()
        elif args.tests_only:
            results = run_all_examples()
            print_summary(results)
        elif args.all or not (args.server_only or args.tests_only):
            server_process = start_server()
            if server_process:
                time.sleep(2)  # Give server a moment to fully start
                results = run_all_examples()
                print_summary(results)
            else:
                print("❌ Cannot run tests without a server")
                sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")
    finally:
        if server_process:
            stop_server(server_process)

if __name__ == "__main__":
    main()
