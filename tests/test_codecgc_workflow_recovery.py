"""Recovery-path coverage for the CodeCGC workflow state machine."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from codecgc_flow_control import build_execution_result


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def run_codecgc_script(
    workspace: Path,
    script_name: str,
    *args: str,
    expect_success_exit: bool = True,
) -> dict[str, Any]:
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
    if expect_success_exit:
        assert completed.returncode == 0, (
            f"{script_name} failed with return code {completed.returncode}: {parsed}"
        )
    return parsed


def write_routing_file(workspace: Path) -> None:
    (workspace / "model-routing.yaml").write_text(
        (REPO_ROOT / "model-routing.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def write_feature(
    workspace: Path,
    *,
    slug: str,
    base_slug: str,
    checklist_body: str,
    acceptance: str = "# Acceptance\n\nTODO: review pending.\n",
) -> Path:
    feature_dir = workspace / "codecgc" / "features" / slug
    feature_dir.mkdir(parents=True)
    (workspace / "codecgc" / "execution").mkdir(parents=True)
    (feature_dir / f"{base_slug}-design.md").write_text(
        f"# {base_slug}\n\nRecovery test workflow.\n",
        encoding="utf-8",
    )
    (feature_dir / f"{base_slug}-checklist.yaml").write_text(checklist_body, encoding="utf-8")
    (feature_dir / f"{base_slug}-acceptance.md").write_text(acceptance, encoding="utf-8")
    return feature_dir


def write_backend_target(workspace: Path, path: str = "src/server/recovery_demo.py") -> None:
    target = workspace / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def value() -> str:\n    return 'before'\n", encoding="utf-8")


def write_session_audit(workspace: Path, *, task_id: str, session_id: str, target_path: str) -> None:
    audit = {
        "product": "CodeCGC",
        "version": 1,
        "mode": "execute",
        "task_id": task_id,
        "target": "backend",
        "tool_name": "implement_backend_task",
        "target_paths": [target_path],
        "requested_session_id": "",
        "source": {
            "type": "workflow-step",
            "artifact_file": "codecgc/features/session-recovery/session-recovery-checklist.yaml",
            "artifact_type": "feature",
            "artifact_class": "product",
            "artifact_slug": "session-recovery",
            "step_number": 1,
        },
        "result": {
            "success": False,
            "outcome": "executor-failure",
            "task_id": task_id,
            "session_id": session_id,
            "summary": "Previous executor failed after opening a session.",
            "changed_files": [],
            "policy_checks": [],
            "risks": [],
            "error": "executor failed",
        },
    }
    audit_path = workspace / "codecgc" / "execution" / f"{task_id}.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


def test_executor_failure_recovery_result_keeps_retry_command() -> None:
    result = build_execution_result(
        flow="feature",
        slug="executor-failure-demo",
        route={"recommended_command": "cgc-build"},
        execution={
            "success": False,
            "mode": "execute",
            "result": {
                "success": False,
                "outcome": "executor-failure",
                "summary": "Executor returned invalid structured output.",
                "error": "Unable to parse structured MCP tool result.",
            },
            "audit": {"path": "codecgc/execution/executor-failure-demo-step-1.json"},
        },
    )

    assert result["success"] is False
    assert result["state"] == "blocked"
    assert result["failure_type"] == "executor-failure"
    assert result["recommended_command"] == ""
    assert result["audit_path"] == "codecgc/execution/executor-failure-demo-step-1.json"


def test_mixed_path_route_exposes_split_payload_to_entry(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    write_routing_file(workspace)
    write_backend_target(workspace, "src/server/mixed.py")
    frontend_target = workspace / "src" / "components" / "Mixed.tsx"
    frontend_target.parent.mkdir(parents=True, exist_ok=True)
    frontend_target.write_text("export function Mixed() { return null; }\n", encoding="utf-8")

    slug = "2026-05-10-mixed-recovery"
    base_slug = "mixed-recovery"
    write_feature(
        workspace,
        slug=slug,
        base_slug=base_slug,
        checklist_body=f"""feature: {slug}
artifact_class: product
steps:
  - action: "Mixed implementation"
    status: pending
    codecgc:
      kind: auto
      task_id: mixed-recovery-step-1
      task_summary: "Mixed frontend and backend step"
      target_paths:
        - "src/server/mixed.py"
        - "src/components/Mixed.tsx"
""",
    )

    route = run_codecgc_script(workspace, "route_codecgc_workflow.py", "--flow", "feature", "--slug", slug)
    assert route["success"] is False
    assert route["recommended_command"] == "cgc-plan"
    assert route["summary"]["workflow_state"] == "needs-planning"
    assert route["split_suggestion"]["grouped_paths"]["backend"] == ["src/server/mixed.py"]
    assert route["split_suggestion"]["grouped_paths"]["frontend"] == ["src/components/Mixed.tsx"]

    explain = run_codecgc_script(
        workspace,
        "entry_codecgc_workflow.py",
        "--mode",
        "explain",
        "--flow",
        "feature",
        "--slug",
        slug,
    )
    followup = explain["operator_brief"]["machine_next_action"]["user_action"]["followup_payload"]
    payload = followup["payload"]
    assert payload["split_scope"] is True
    assert payload["grouped_paths"]["backend"] == ["src/server/mixed.py"]
    assert payload["grouped_paths"]["frontend"] == ["src/components/Mixed.tsx"]


def test_explicit_test_step_routes_to_cgc_test_and_dry_run_recovers(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    write_routing_file(workspace)
    test_target = workspace / "tests" / "backend" / "test_recovery_demo.py"
    test_target.parent.mkdir(parents=True, exist_ok=True)
    test_target.write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")

    slug = "2026-05-10-test-recovery"
    base_slug = "test-recovery"
    write_feature(
        workspace,
        slug=slug,
        base_slug=base_slug,
        checklist_body=f"""feature: {slug}
artifact_class: product
steps:
  - action: "Add backend regression test"
    status: pending
    codecgc:
      kind: backend
      step_type: test
      task_id: backend-regression-step-1
      task_summary: "Add backend regression test"
      target_paths:
        - "tests/backend/test_recovery_demo.py"
""",
    )

    route = run_codecgc_script(workspace, "route_codecgc_workflow.py", "--flow", "feature", "--slug", slug)
    assert route["recommended_command"] == "cgc-test"
    assert route["summary"]["workflow_state"] == "step-selected"
    assert route["current_step"]["step_type"] == "test"

    dry_run = run_codecgc_script(
        workspace,
        "run_codecgc_test.py",
        "--flow",
        "feature",
        "--slug",
        slug,
        "--dry-run",
    )
    assert dry_run["success"] is False
    assert dry_run["state"] == "executed-dry-run"
    assert dry_run["recommended_command"] == "cgc-test"


def test_changes_requested_review_reuses_session_on_next_execution(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    write_routing_file(workspace)
    target_path = "src/server/session_recovery.py"
    write_backend_target(workspace, target_path)

    slug = "2026-05-10-session-recovery"
    base_slug = "session-recovery"
    task_id = "session-recovery-step-1"
    write_feature(
        workspace,
        slug=slug,
        base_slug=base_slug,
        checklist_body=f"""feature: {slug}
artifact_class: product
steps:
  - action: "Continue backend recovery"
    status: pending
    codecgc:
      kind: backend
      task_id: {task_id}
      task_summary: "Continue backend recovery"
      target_paths:
        - "{target_path}"
""",
        acceptance=f"""# Review Result

- Review decision: changes-requested
- Reviewed task_id: {task_id}
- Reviewed step_number: 1
""",
    )
    write_session_audit(workspace, task_id=task_id, session_id="session-recovery-123", target_path=target_path)

    route = run_codecgc_script(workspace, "route_codecgc_workflow.py", "--flow", "feature", "--slug", slug)
    assert route["recommended_command"] == "cgc-build"
    assert route["summary"]["workflow_state"] == "awaiting-build"
    assert route["review"]["decision"] == "changes-requested"

    explain = run_codecgc_script(
        workspace,
        "entry_codecgc_workflow.py",
        "--mode",
        "explain",
        "--flow",
        "feature",
        "--slug",
        slug,
    )
    action = explain["operator_brief"]["machine_next_action"]
    assert action["command"] == "cgc-build"
    assert action["execution"]["command_args"][-2:] == ["--session-id", "session-recovery-123"]
