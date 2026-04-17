"""
Status vocabulary for V2 workstream/memo/adapter results.

Every WorkstreamResult, TriageCheck, MemoV2 field, and AdapterResult carries a
`status: Status`. Output JSON never uses implicit/empty or boolean states for
gate-like decisions — downstream consumers must be able to distinguish a hard
fail from unavailable data from analyst-required input.

Precedence (worst-case merge, used by combine_statuses):
    FAILED > MANUAL_REVIEW_REQUIRED > NOT_ASSESSED > PASSED

Rationale:
- FAILED is terminal — any hard fail in a composite must dominate.
- MANUAL_REVIEW_REQUIRED outranks NOT_ASSESSED because it carries an action
  (analyst input) whereas NOT_ASSESSED is purely informational (data gap).
- PASSED only survives if every input passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional


class Status(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_ASSESSED = "not_assessed"  # data unavailable (premium or fetch error)
    MANUAL_REVIEW_REQUIRED = "manual_review_required"  # analyst input expected


# Worst-case precedence. Higher number wins in combine_statuses.
_PRECEDENCE: dict[Status, int] = {
    Status.PASSED: 0,
    Status.NOT_ASSESSED: 1,
    Status.MANUAL_REVIEW_REQUIRED: 2,
    Status.FAILED: 3,
}


def combine_statuses(statuses: Iterable[Status]) -> Status:
    """Merge multiple statuses with worst-case precedence.

    Empty input defaults to NOT_ASSESSED — an empty set of checks is a data gap,
    not a pass.
    """
    items = list(statuses)
    if not items:
        return Status.NOT_ASSESSED
    return max(items, key=lambda s: _PRECEDENCE[s])


@dataclass
class StatusedResult:
    """Base dataclass for any object carrying a Status.

    Subclasses add their own fields. The `status` / `notes` pair is the minimum
    contract every workstream/adapter/check obeys.
    """

    status: Status = Status.NOT_ASSESSED
    notes: list[str] = field(default_factory=list)

    def add_note(self, note: str) -> None:
        if note:
            self.notes.append(note)

    def is_passed(self) -> bool:
        return self.status == Status.PASSED

    def is_failed(self) -> bool:
        return self.status == Status.FAILED

    def needs_analyst(self) -> bool:
        return self.status == Status.MANUAL_REVIEW_REQUIRED

    def is_not_assessed(self) -> bool:
        return self.status == Status.NOT_ASSESSED
