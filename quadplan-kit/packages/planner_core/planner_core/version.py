"""Version of the verification semantics (kept apart so every module can import it)."""

__version__ = "0.1.0"

#: Stored with every cached verification report; part of the cache key.
CORE_VERSION = f"planner_core-{__version__}"
