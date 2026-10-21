"""Put the backend root on sys.path so tests import what the app imports."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(autouse=True)
def _isolate_process_state():
    """Clear caches and connection memoization between tests.

    The search cache is module-level, so without this a result cached by one
    test is served to the next.
    """
    import cache
    import shared

    cache.clear()
    shared.reset()
    yield
    cache.clear()
    shared.reset()
