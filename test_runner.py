import subprocess
import sys


def run_tests(test_file_path):
    """Run a single test file with pytest and return (passed, output)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_file_path, "-v"],
        capture_output=True,
        text=True,
    )
    passed = result.returncode == 0
    output = result.stdout + result.stderr
    return passed, output
