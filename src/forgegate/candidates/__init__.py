from typing import TYPE_CHECKING, Any

from forgegate.candidates.evidence_binding import (
    CandidateEvidenceBinding,
    create_candidate_evidence_binding,
)
from forgegate.candidates.lifecycle import (
    CandidateLifecycleError,
    create_candidate,
    transition_candidate,
)
from forgegate.candidates.models import (
    CandidateTransition,
    CandidateTransitionResult,
    ReleaseCandidate,
)

if TYPE_CHECKING:
    from forgegate.candidates.store import (
        CandidateHistory,
        CandidateStoreError,
        SQLiteCandidateRepository,
    )

__all__ = [
    "CandidateEvidenceBinding",
    "CandidateHistory",
    "CandidateLifecycleError",
    "CandidateStoreError",
    "CandidateTransition",
    "CandidateTransitionResult",
    "ReleaseCandidate",
    "SQLiteCandidateRepository",
    "create_candidate",
    "create_candidate_evidence_binding",
    "transition_candidate",
]


def __getattr__(name: str) -> Any:
    """Load the SQLite adapter lazily so domain models remain dependency-free."""
    if name in {"CandidateHistory", "CandidateStoreError", "SQLiteCandidateRepository"}:
        from forgegate.candidates import store

        return getattr(store, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
