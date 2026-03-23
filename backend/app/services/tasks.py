from __future__ import annotations

from typing import Any

from .utils import new_id, utc_now_iso

ROUTE_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "administrative": [
        {"title": "Upload EOB", "description": "Upload the Explanation of Benefits document.", "owner": "patient"},
        {"title": "Verify claim identifiers", "description": "Confirm claim/auth/member IDs are correct.", "owner": "patient"},
        {"title": "Generate appeal packet", "description": "Create letter + supporting packet for submission.", "owner": "patient"},
    ],
    "medical_necessity": [
        {"title": "Request clinical notes", "description": "Collect treating provider clinical notes.", "owner": "provider"},
        {"title": "Obtain letter of medical necessity", "description": "Ask provider for medical necessity letter.", "owner": "provider"},
        {"title": "Compile prior treatment history", "description": "Document failed conservative therapies.", "owner": "patient"},
        {"title": "Generate appeal packet", "description": "Create letter + supporting packet for submission.", "owner": "patient"},
    ],
    "prior_authorization": [
        {"title": "Upload prior authorization records", "description": "Attach authorization and approval evidence.", "owner": "patient"},
        {"title": "Confirm service/procedure code match", "description": "Check code alignment between authorization and claim.", "owner": "provider"},
        {"title": "Generate appeal packet", "description": "Create letter + supporting packet for submission.", "owner": "patient"},
    ],
    "coding_billing": [
        {"title": "Validate coding details", "description": "Review CPT/ICD/modifier details with billing office.", "owner": "provider"},
        {"title": "Prepare corrected claim evidence", "description": "Collect corrected coding documentation.", "owner": "provider"},
        {"title": "Generate appeal packet", "description": "Create letter + supporting packet for submission.", "owner": "patient"},
    ],
    "out_of_network": [
        {"title": "Collect plan network exceptions", "description": "Gather evidence of network inadequacy or exception criteria.", "owner": "patient"},
        {"title": "Gather provider billing justification", "description": "Obtain supporting billing rationale from provider.", "owner": "provider"},
        {"title": "Generate appeal packet", "description": "Create letter + supporting packet for submission.", "owner": "patient"},
    ],
}


def _pick_route(case_json: dict[str, Any]) -> str:
    reasons = case_json.get("denial_reasons") or []
    for reason in reasons:
        label = reason.get("label")
        if label in ROUTE_TEMPLATES:
            return str(label)
    return "administrative"


def generate_tasks(conn, *, case_id: str, case_json: dict[str, Any]) -> list[dict[str, Any]]:
    route = _pick_route(case_json)
    template = ROUTE_TEMPLATES[route]

    deadlines = case_json.get("deadlines") or []
    due_date = None
    if deadlines:
        due_date = (deadlines[0] or {}).get("value")

    conn.execute("DELETE FROM tasks WHERE case_id = ?", (case_id,))

    created: list[dict[str, Any]] = []
    for item in template:
        task = {
            "task_id": new_id("tsk"),
            "case_id": case_id,
            "title": item["title"],
            "description": item["description"],
            "owner": item["owner"],
            "due_date": due_date,
            "status": "todo",
            "created_at": utc_now_iso(),
        }
        conn.execute(
            """
            INSERT INTO tasks (task_id, case_id, title, description, owner, due_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["task_id"],
                task["case_id"],
                task["title"],
                task["description"],
                task["owner"],
                task["due_date"],
                task["status"],
                task["created_at"],
            ),
        )
        created.append(task)

    return created
