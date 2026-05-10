"""End-to-end workflow checks for the project-local CodeCGC loop."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
SLUG = "2026-05-10-p2-loop-demo"
BASE_SLUG = "p2-loop-demo"
TASK_ID = "p2-loop-demo-step-1"
TARGET_PATH = "src/server/p2_loop_demo.py"


def run_codecgc_script(workspace: Path, script_name: str, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["CODECGC_WORKSPACE_ROOT"] = str(workspace)
    env["PYTHONUTF8"] = "1"

    completed = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script_name), *args],
        cwd=workspace,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = completed.stdout.strip() or completed.stderr.strip()
    assert output, f"{script_name} produced no output"
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"{script_name} did not return JSON.\n"
            f"returncode={completed.returncode}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        ) from error
    assert completed.returncode == 0, (
        f"{script_name} failed with return code {completed.returncode}: {parsed}"
    )
    return parsed


def write_workspace(workspace: Path) -> None:
    (workspace / "src" / "server").mkdir(parents=True)
    (workspace / TARGET_PATH).write_text(
        "def current_value() -> str:\n"
        "    return 'before'\n",
        encoding="utf-8",
    )

    (workspace / "model-routing.yaml").write_text(
        (REPO_ROOT / "model-routing.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    feature_dir = workspace / "codecgc" / "features" / SLUG
    feature_dir.mkdir(parents=True)
    (workspace / "codecgc" / "execution").mkdir(parents=True)

    (feature_dir / f"{BASE_SLUG}-design.md").write_text(
        "# P2 Loop Demo\n\n"
        "This fixture-like product workflow validates routing, execution audit, review, and closure.\n",
        encoding="utf-8",
    )
    (feature_dir / f"{BASE_SLUG}-checklist.yaml").write_text(
        f"""feature: {SLUG}
artifact_class: product
steps:
  - action: "Implement backend demo endpoint"
    status: pending
    exit_signal: "Backend demo helper returns the updated value"
    codecgc:
      kind: backend
      task_id: {TASK_ID}
      task_summary: "Update the backend demo helper"
      target_paths:
        - "{TARGET_PATH}"
      acceptance:
        - "The backend demo helper returns the updated value"
""",
        encoding="utf-8",
    )
    (feature_dir / f"{BASE_SLUG}-acceptance.md").write_text(
        "# Acceptance\n\nTODO: review pending.\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_project_local_workflow_loop_without_real_executors(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    write_workspace(workspace)

    route = run_codecgc_script(
        workspace,
        "route_codecgc_workflow.py",
        "--flow",
        "feature",
        "--slug",
        SLUG,
    )
    assert route["success"] is True
    assert route["artifact_class"] == "product"
    assert route["recommended_command"] == "cgc-build"
    assert route["summary"]["workflow_state"] == "awaiting-build"
    assert route["current_step"]["step_number"] == 1
    assert route["current_step"]["task_id"] == TASK_ID

    explain = run_codecgc_script(
        workspace,
        "entry_codecgc_workflow.py",
        "--mode",
        "explain",
        "--flow",
        "feature",
        "--slug",
        SLUG,
    )
    assert explain["success"] is True
    assert explain["operator_brief"]["needs_execution"] is True
    assert explain["operator_brief"]["machine_next_action"]["execution"]["command"] == "cgc-build"
    assert explain["operator_brief"]["machine_next_action"]["execution"]["workflow_state"] == "awaiting-build"

    dry_run = run_codecgc_script(
        workspace,
        "run_codecgc_build.py",
        "--slug",
        SLUG,
        "--dry-run",
    )
    assert dry_run["success"] is False
    assert dry_run["state"] == "executed-dry-run"
    assert dry_run["recommended_command"] == "cgc-build"
    assert dry_run["execution"]["mode"] == "dry-run"
    audit_path = workspace / dry_run["audit_path"]
    assert audit_path.exists()
    dry_audit = load_json(audit_path)
    assert dry_audit["mode"] == "dry-run"
    assert dry_audit["source"]["artifact_file"] == f"codecgc/features/{SLUG}/{BASE_SLUG}-checklist.yaml"
    assert dry_audit["source"]["artifact_slug"] == SLUG

    review_dry_run = run_codecgc_script(
        workspace,
        "review_codecgc_workflow.py",
        "--audit-file",
        dry_run["audit_path"],
        "--decision",
        "accepted",
        "--force",
    )
    assert review_dry_run["success"] is True
    assert review_dry_run["requested_decision"] == "accepted"
    assert review_dry_run["final_decision"] == "changes-requested"
    assert review_dry_run["recommended_action_kind"] == "execute-for-real"
    assert review_dry_run["writeback"]["step_status"] == "pending"

    route_after_dry_review = run_codecgc_script(
        workspace,
        "route_codecgc_workflow.py",
        "--flow",
        "feature",
        "--slug",
        SLUG,
    )
    assert route_after_dry_review["recommended_command"] == "cgc-build"
    assert route_after_dry_review["summary"]["workflow_state"] == "awaiting-build"
    assert route_after_dry_review["review"]["decision"] == "changes-requested"

    synthetic_audit = dict(dry_audit)
    synthetic_audit["mode"] = "execute"
    synthetic_audit["result"] = {
        **synthetic_audit["result"],
        "success": True,
        "outcome": "done",
        "changed_files": [TARGET_PATH],
        "policy_checks": [],
        "risks": [],
        "summary": "Synthetic executor result for workflow closure.",
    }
    synthetic_audit["file_evidence"] = {
        "evidence_source": "workspace-unified-diff-snapshot",
        "workspace_changed_files": [TARGET_PATH],
        "verified_changed_files": [TARGET_PATH],
        "out_of_scope_changed_files": [],
        "file_diffs": [
            {
                "path": TARGET_PATH,
                "in_scope": True,
                "scope_match_kind": "exact",
                "change_type": "modified",
                "diff_kind": "unified-text-diff",
                "changed_line_count": 1,
                "diff_excerpt": "-    return 'before'\\n+    return 'after'",
            }
        ],
        "evidence_confidence": "local-diff-verified",
        "git_evidence": {
            "git_repository_detected": False,
            "git_root": "",
            "history_available": False,
            "status": "not-a-git-repository",
            "tracked_changed_files": [],
            "untracked_changed_files": [],
            "git_changed_files": [],
        },
    }
    audit_path.write_text(json.dumps(synthetic_audit, ensure_ascii=False, indent=2), encoding="utf-8")

    route_ready_for_review = run_codecgc_script(
        workspace,
        "route_codecgc_workflow.py",
        "--flow",
        "feature",
        "--slug",
        SLUG,
    )
    assert route_ready_for_review["recommended_command"] == "cgc-review"
    assert route_ready_for_review["summary"]["workflow_state"] == "awaiting-review"

    review_accepted = run_codecgc_script(
        workspace,
        "review_codecgc_workflow.py",
        "--audit-file",
        str(audit_path),
        "--decision",
        "accepted",
        "--force",
    )
    assert review_accepted["success"] is True
    assert review_accepted["final_decision"] == "accepted"
    assert review_accepted["writeback"]["step_status"] == "done"

    closed = run_codecgc_script(
        workspace,
        "route_codecgc_workflow.py",
        "--flow",
        "feature",
        "--slug",
        SLUG,
    )
    assert closed["success"] is True
    assert closed["recommended_command"] == ""
    assert closed["summary"]["workflow_state"] == "closed"
    assert closed["summary"]["is_closed"] is True
