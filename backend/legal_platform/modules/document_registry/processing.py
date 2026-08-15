"""Document processing state machine (tasks/001-document-registry.md #Processing States).

This is Registry-owned, mutable processing state — *not* the canonical Document
lifecycle (Created -> Active -> Archived from document-contract.md). The two are kept
distinct (design decision): the Document ``status`` field is canonical; processing
state is derived/disposable per ADR-003 and constraints.md DC-002.

   UPLOADED
      |
      v
   OCR_PENDING
      |
      v
   OCR_RUNNING
      |
      v
   OCR_COMPLETED
      |
      v
   PARSING_PENDING
      |
      v
   PARSING_RUNNING
      |
      v
   READY
      |
      v
   ARCHIVED
      |
      v
   FAILED   (terminal, recoverable only via explicit re-queue)

Only valid transitions are allowed (task spec: "Only valid transitions are allowed.").
"""

from __future__ import annotations

from enum import Enum


class ProcessingState(str, Enum):
    """Mutable processing state of a Document in the ingestion pipeline."""

    UPLOADED = "UPLOADED"
    OCR_PENDING = "OCR_PENDING"
    OCR_RUNNING = "OCR_RUNNING"
    OCR_COMPLETED = "OCR_COMPLETED"
    PARSING_PENDING = "PARSING_PENDING"
    PARSING_RUNNING = "PARSING_RUNNING"
    READY = "READY"
    ARCHIVED = "ARCHIVED"
    FAILED = "FAILED"


# Allowed forward transitions, per task 001. Archival is a normal end-state; FAILED is
# reachable from any non-terminal state (a failure can halt the pipeline at any stage,
# per processing-pipeline.md: "Knowledge preservation takes precedence over completion").
_TERMINAL = {ProcessingState.READY, ProcessingState.ARCHIVED, ProcessingState.FAILED}
_TRANSITIONS: dict[ProcessingState, set[ProcessingState]] = {
    ProcessingState.UPLOADED: {
        ProcessingState.OCR_PENDING,
        ProcessingState.FAILED,
    },
    ProcessingState.OCR_PENDING: {
        ProcessingState.OCR_RUNNING,
        ProcessingState.FAILED,
    },
    ProcessingState.OCR_RUNNING: {
        ProcessingState.OCR_COMPLETED,
        ProcessingState.FAILED,
    },
    ProcessingState.OCR_COMPLETED: {
        ProcessingState.PARSING_PENDING,
        ProcessingState.FAILED,
    },
    ProcessingState.PARSING_PENDING: {
        ProcessingState.PARSING_RUNNING,
        ProcessingState.FAILED,
    },
    ProcessingState.PARSING_RUNNING: {
        ProcessingState.READY,
        ProcessingState.FAILED,
    },
    ProcessingState.READY: {
        ProcessingState.ARCHIVED,
        # Re-index/re-parse starts a new processing cycle on a new Document Version,
        # so READY itself is not re-entered; archival is the only forward step here.
    },
    ProcessingState.ARCHIVED: set(),  # terminal
    ProcessingState.FAILED: set(),  # terminal unless explicitly re-queued
}


def is_terminal(state: ProcessingState) -> bool:
    """True if ``state`` is a terminal processing state (READY/ARCHIVED/FAILED)."""
    return state in _TERMINAL


def can_transition(current: ProcessingState, target: ProcessingState) -> bool:
    """True if ``target`` is a valid forward transition from ``current``."""
    if current is target:
        return False
    return target in _TRANSITIONS.get(current, set())


def assert_transition(current: ProcessingState, target: ProcessingState) -> None:
    """Raise ``InvalidTransition`` unless ``target`` is valid from ``current``."""
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


class InvalidTransition(ValueError):
    """Raised when an invalid processing-state transition is attempted."""

    def __init__(self, current: ProcessingState, target: ProcessingState):
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid processing-state transition: {current.value} -> {target.value}"
        )


def reachable_states() -> set[ProcessingState]:
    """All states defined by the state machine (informational)."""
    return set(ProcessingState)
