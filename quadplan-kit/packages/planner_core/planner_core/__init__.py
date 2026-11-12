"""Trusted core of Quarterly: requirements DSL, verifier, solver and certificate checker.

Hard rule: this package never imports a database driver, a web framework, an HTTP
client or an LLM client, and does no I/O. Pydantic in, Pydantic out.
"""

__version__ = "0.1.0"

#: Version of the verification semantics. Stored with every cached verification report.
CORE_VERSION = f"planner_core-{__version__}"
