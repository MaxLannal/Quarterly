"""Trusted core of Quarterly: requirements DSL, verifier, solver and certificate checker.

Hard rule: this package never imports a database driver, a web framework, an HTTP client or an
LLM client, and does no I/O. Pydantic in, Pydantic out.
"""

from planner_core.certificate import certificate_problems, check_certificate
from planner_core.verify import verify, verify_checked
from planner_core.version import CORE_VERSION, __version__

__all__ = [
    "CORE_VERSION",
    "__version__",
    "certificate_problems",
    "check_certificate",
    "verify",
    "verify_checked",
]
