#!/usr/bin/env python3
"""
End-to-End MVP Test Script
Tests the complete user flow through the web application.
"""

import requests
import time
import json
from typing import Optional, Dict


class Colors:
    """ANSI colors for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_step(step: str, step_num: int):
    """Print a test step header."""
    print(f"\n{Colors.BOLD}[{step_num}] {step}{Colors.RESET}")
    print("-" * 50)


def print_success(message: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_warning(message: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def print_info(message: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


class MVPTester:
    """Test the MVP end-to-end flow."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.job_id: Optional[int] = None
        self.test_results = []

    def register_user(self, username: str, password: str) -> bool:
        """Test user registration."""
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/register",
                json={"username": username, "password": password},
                timeout=10
            )

            if response.status_code == 201:
                self.token = response.json().get("access_token")
                print_success("User registered successfully")
                return True
            else:
                print_error(f"Registration failed: {response.status_code}")
                print_error(response.text)
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def login(self, username: str, password: str) -> bool:
        """Test user login."""
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": username, "password": password},
                timeout=10
            )

            if response.status_code == 200:
                self.token = response.json().get("access_token")
                print_success(f"Logged in as {username}")
                return True
            else:
                print_error(f"Login failed: {response.status_code}")
                print_error(response.text)
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def get_current_user(self) -> bool:
        """Test getting current user."""
        if not self.token:
            print_error("No token available")
            return False

        try:
            response = requests.get(
                f"{self.base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                self.user_id = user_data.get("id")
                print_success(f"Current user: {user_data.get('username')} (ID: {self.user_id})")
                return True
            else:
                print_error(f"Get user failed: {response.status_code}")
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def save_config(self) -> bool:
        """Test saving configuration."""
        if not self.token:
            return False

        try:
            response = requests.put(
                f"{self.base_url}/api/config",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "huggingface_repo_id": "test-user/test-dataset",
                    "huggingface_private": False,
                    "download_max_workers": 4,
                    "noise_reduction_enabled": True,
                    "filtering_enabled": True
                },
                timeout=10
            )

            if response.status_code == 200:
                print_success("Configuration saved")
                return True
            else:
                print_error(f"Save config failed: {response.status_code}")
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def get_config(self) -> bool:
        """Test getting configuration."""
        if not self.token:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/api/config",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )

            if response.status_code == 200:
                config = response.json()
                print_success(f"Config retrieved: HF repo = {config.get('huggingface', {}).get('repo_id')}")
                return True
            else:
                print_error(f"Get config failed: {response.status_code}")
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def create_job(self) -> bool:
        """Test creating a pipeline job."""
        if not self.token:
            return False

        try:
            response = requests.post(
                f"{self.base_url}/api/pipelines",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "source_type": "local",
                    "source_value": "./data/raw",
                    "skip_download": True,
                    "skip_push": True
                },
                timeout=10
            )

            if response.status_code in [200, 201]:
                job_data = response.json()
                self.job_id = job_data.get("id")
                print_success(f"Job created: #{self.job_id}")
                print_info(f"Status: {job_data.get('status')}")
                return True
            else:
                print_error(f"Create job failed: {response.status_code}")
                print_error(response.text)
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def get_job_status(self) -> bool:
        """Test getting job status."""
        if not self.token or not self.job_id:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/api/pipelines/{self.job_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )

            if response.status_code == 200:
                job_data = response.json()
                print_success(f"Job status: {job_data.get('status')}")
                print_info(f"Source: {job_data.get('source_type')}")
                print_info(f"Created: {job_data.get('created_at')}")
                return True
            else:
                print_error(f"Get job failed: {response.status_code}")
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def list_jobs(self) -> bool:
        """Test listing jobs."""
        if not self.token:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/api/pipelines",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )

            if response.status_code == 200:
                payload = response.json()
                if isinstance(payload, dict) and isinstance(payload.get("items"), list):
                    jobs = payload["items"]
                elif isinstance(payload, list):
                    jobs = payload
                else:
                    jobs = []
                print_success(f"Found {len(jobs)} job(s)")
                return True
            else:
                print_error(f"List jobs failed: {response.status_code}")
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def test_system_status(self) -> bool:
        """Test system status endpoints."""
        if not self.token:
            return False

        try:
            # System status
            response = requests.get(
                f"{self.base_url}/api/pipelines/system/status",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )

            if response.status_code == 200:
                status = response.json()
                print_success(f"System status: {status.get('current_running')}/{status.get('max_concurrent_jobs')} jobs running")
                return True
            else:
                print_error(f"System status failed: {response.status_code}")
                return False
        except requests.RequestException as e:
            print_error(f"Connection error: {e}")
            return False

    def run_all_tests(self):
        """Run all MVP tests."""
        print(f"\n{Colors.BOLD}{'='*60}")
        print(f"MVP End-to-End Test Suite")
        print(f"Target: {self.base_url}")
        print(f"{'='*60}{Colors.RESET}\n")

        test_username = "mvp_test_user"
        test_password = "test123456"

        results = {}

        # Test 1: Register
        print_step("Test Registration", 1)
        results['register'] = self.register_user(test_username, test_password)

        # Test 2: Login
        print_step("Test Login", 2)
        if not results['register']:
            print_warning("Skipping login due to registration failure")
            results['login'] = False
        else:
            results['login'] = self.login(test_username, test_password)

        # Test 3: Get Current User
        print_step("Test Get Current User", 3)
        if not results['login']:
            print_warning("Skipping due to login failure")
            results['get_user'] = False
        else:
            results['get_user'] = self.get_current_user()

        # Test 4: Get Config
        print_step("Test Get Config", 4)
        if not results['login']:
            print_warning("Skipping due to login failure")
            results['get_config'] = False
        else:
            results['get_config'] = self.get_config()

        # Test 5: Save Config
        print_step("Test Save Config", 5)
        if not results['login']:
            print_warning("Skipping due to login failure")
            results['save_config'] = False
        else:
            results['save_config'] = self.save_config()

        # Test 6: Create Job
        print_step("Test Create Job", 6)
        if not results['login']:
            print_warning("Skipping due to login failure")
            results['create_job'] = False
        else:
            results['create_job'] = self.create_job()

        # Test 7: Get Job Status
        print_step("Test Get Job Status", 7)
        if not results['create_job']:
            print_warning("Skipping due to job creation failure")
            results['get_job'] = False
        else:
            results['get_job'] = self.get_job_status()

        # Test 8: List Jobs
        print_step("Test List Jobs", 8)
        if not results['login']:
            print_warning("Skipping due to login failure")
            results['list_jobs'] = False
        else:
            results['list_jobs'] = self.list_jobs()

        # Test 9: System Status
        print_step("Test System Status", 9)
        if not results['login']:
            print_warning("Skipping due to login failure")
            results['system_status'] = False
        else:
            results['system_status'] = self.test_system_status()

        # Summary
        self.print_summary(results)

    def print_summary(self, results: Dict[str, bool]):
        """Print test summary."""
        print(f"\n{Colors.BOLD}{'='*60}")
        print(f"Test Summary")
        print(f"{'='*60}{Colors.RESET}\n")

        total_tests = len(results)
        passed_tests = sum(1 for v in results.values() if v)
        failed_tests = total_tests - passed_tests

        for test_name, passed in results.items():
            status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
            print(f"  {test_name:20}: {status}")

        print(f"\nTotal: {total_tests} | Passed: {passed_tests} | Failed: {failed_tests}")

        if passed_tests == total_tests:
            print(f"\n{Colors.GREEN}{Colors.BOLD}ALL TESTS PASSED! 🎉{Colors.RESET}\n")
        elif passed_tests > total_tests // 2:
            print(f"\n{Colors.YELLOW}SOME TESTS FAILED{Colors.RESET}\n")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}MANY TESTS FAILED{Colors.RESET}\n")

        print(f"\n{Colors.BLUE}Next steps:{Colors.RESET}")
        print("  1. Open browser to http://localhost:5173")
        print("  2. Try the web interface manually")
        print("  3. Check browser console (F12) for errors")
        print("  4. Check backend logs for detailed errors")


def main():
    """Main entry point."""
    import sys

    # Check if backend is running
    base_url = "http://localhost:8000"
    print(f"Checking backend at {base_url}...")

    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print_success("Backend is running!")
        else:
            print_error(f"Backend responded with status {response.status_code}")
            print_info("Please start the backend first:")
            print_info("  python -m uvicorn backend.app:app --reload")
            sys.exit(1)
    except requests.RequestException:
        print_error("Backend is not responding!")
        print_info("Please start the backend first:")
        print_info("  python -m uvicorn backend.app:app --reload")
        sys.exit(1)

    # Run tests
    tester = MVPTester(base_url=base_url)
    tester.run_all_tests()


if __name__ == '__main__':
    main()
