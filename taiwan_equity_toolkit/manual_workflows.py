"""
Manual workflow templates that stay explicit in the V2 architecture.
"""

from __future__ import annotations


WORKFLOW_TEMPLATES: dict[str, dict[str, object]] = {
    "management_forensic": {
        "title": "Management forensic",
        "purpose": "Review incentives, governance behavior, capital allocation, and candor outside the FinMind default path.",
        "checklist": [
            "Describe management's explicit capital-allocation priorities over the last 3 years.",
            "List insider ownership, board composition, and any notable related-party issues.",
            "Review major equity issuance, buyback, dividend, or capital-reduction actions.",
            "Assess whether guidance, investor communication, and execution have been consistent.",
            "Record any unresolved governance concern and classify it as passed, failed, or manual_review_required.",
        ],
    },
    "share_pledging_review": {
        "title": "Share-pledging review",
        "purpose": "Capture Taiwan-specific director and supervisor pledge disclosures that are not automated in the free-tier default path.",
        "checklist": [
            "Identify the most recent share-pledging disclosure source and date.",
            "Record directors or supervisors with material pledge ratios.",
            "State whether the pledge level changes the investment verdict or monitoring cadence.",
        ],
    },
    "channel_check_protocol": {
        "title": "Channel-check protocol",
        "purpose": "Run scuttlebutt work explicitly and keep it separate from the automated scoring model.",
        "checklist": [
            "Name the channel-check objective before speaking with anyone.",
            "Use only MNPI-safe questions and record the source category, not confidential identities, when appropriate.",
            "Separate confirmed facts from anecdotes or hearsay.",
            "State whether the channel check supports, weakens, or leaves unchanged the current variant perception.",
        ],
    },
    "pre_mortem": {
        "title": "Pre-mortem",
        "purpose": "Force the analyst to imagine why the position fails before final sizing.",
        "checklist": [
            "Write the most likely thesis-break scenario.",
            "List the earliest observable signals that would show the thesis is wrong.",
            "Specify the monitoring cadence for each failure mode.",
            "Link each failure mode to an exit or forced-review rule.",
        ],
    },
    "decision_journal": {
        "title": "Decision journal",
        "purpose": "Create an auditable record of why the position was initiated and what evidence mattered at the time.",
        "checklist": [
            "Record thesis, variant perception, and sizing decision.",
            "Record what was passed, failed, not_assessed, and manual_review_required on entry.",
            "Record the single most important reason the decision could be wrong.",
        ],
    },
    "post_mortem": {
        "title": "Post-mortem",
        "purpose": "Review process quality after exit or thesis invalidation.",
        "checklist": [
            "Document the exit reason and date.",
            "Compare realized path vs. original base/bull/bear scenario framing.",
            "Identify one process improvement and one signal that was overweighted or underweighted.",
        ],
    },
}


def workflow_template(name: str) -> dict[str, object]:
    return WORKFLOW_TEMPLATES[name]


def workflow_sections() -> list[dict[str, object]]:
    return [
        {"name": name, **payload}
        for name, payload in WORKFLOW_TEMPLATES.items()
    ]
