"""
conftest.py -- Shared fixtures and helpers for vigilex test suite.

Plain functions (make_search_result, mock_search_results) are importable
directly in test modules. pytest fixtures are defined separately below.
"""

import pytest
from vigilex.coding.hybrid_search import SearchResult
from tests.helpers import make_search_result, mock_search_results


# ---------------------------------------------------------------------------
# pytest fixtures (helpers live in tests/helpers.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def single_result() -> SearchResult:
    return make_search_result()


@pytest.fixture
def ten_results() -> list:
    return mock_search_results(10)
