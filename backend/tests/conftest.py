import pytest


@pytest.fixture(autouse=True)
def _fresh_live_cache():
    """The /api/live cache is process-wide; each test starts without another test's result."""
    from app import main

    main._live_cache.clear()
    yield
    main._live_cache.clear()
