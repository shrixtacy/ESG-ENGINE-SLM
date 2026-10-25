"""
Shared pytest configuration and fixtures for rules tests.
"""
import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow (deselect with -m 'not slow')")
    config.addinivalue_line("markers", "integration: mark test as integration test")
