import pytest

from codecgc_policy import classify_path
from codecgc_policy import evaluate_paths
from codecgc_policy import load_policy
from codecgc_policy import parse_hook_payload
from codecgc_policy import validate_executor_target
from codecgc_policy import validate_policy
from codecgc_routing_template import merge_routing_template


@pytest.fixture
def policy():
    return {
        "version": 2,
        "orchestration_paths": ["codecgc/**", ".claude/commands/**", "model-routing.yaml"],
        "docs_paths": ["README.md", "docs/**"],
        "frontend_paths": ["apps/web/**", "src/components/**"],
        "backend_paths": ["apps/api/**", "server/**"],
        "test_paths": {
            "frontend": ["apps/web/**/*.test.*"],
            "backend": ["apps/api/**/*.test.*"],
        },
        "shared_paths": ["packages/shared/**", "src/lib/**"],
        "rules": {
            "claude_allowed_owners": ["orchestration", "docs"],
            "backend_executor": "codexmcp",
            "frontend_executor": "geminimcp",
            "shared_policy": "split-first",
        },
    }


def test_classify_path_uses_policy_sections(policy):
    assert classify_path("codecgc/features/demo/checklist.yaml", policy) == "orchestration"
    assert classify_path("README.md", policy) == "docs"
    assert classify_path("apps/api/src/user.py", policy) == "backend"
    assert classify_path("apps/web/src/App.test.tsx", policy) == "frontend-test"
    assert classify_path("src/lib/types.ts", policy) == "shared"
    assert classify_path("unknown/file.txt", policy) == "unknown"


def test_claude_can_write_docs_but_not_backend(policy):
    docs_result = evaluate_paths(["README.md"], actor="claude", operation="write", policy=policy)
    backend_result = evaluate_paths(["apps/api/src/user.py"], actor="claude", operation="write", policy=policy)

    assert docs_result["allowed"] is True
    assert backend_result["allowed"] is False
    assert backend_result["decisions"][0]["owner"] == "backend"


def test_executor_target_enforces_owner(policy):
    backend_result = evaluate_paths(["apps/api/src/user.py"], actor="codex", operation="write", policy=policy)
    frontend_result = evaluate_paths(["apps/api/src/user.py"], actor="gemini", operation="write", policy=policy)

    assert backend_result["allowed"] is True
    assert frontend_result["allowed"] is False


def test_loaded_policy_classifies_project_internal_absolute_paths(policy, tmp_path):
    routing_file = tmp_path / "model-routing.yaml"
    routing_file.write_text(merge_routing_template(""), encoding="utf-8")
    loaded_policy = load_policy(routing_file)

    docs_path = tmp_path / "README.md"
    orchestration_path = tmp_path / "codecgc" / "START_HERE.md"
    backend_path = tmp_path / "apps" / "api" / "src" / "user.py"

    assert classify_path(str(docs_path), loaded_policy) == "docs"
    assert classify_path(str(orchestration_path), loaded_policy) == "orchestration"
    assert classify_path(str(backend_path), loaded_policy) == "backend"

    docs_result = evaluate_paths([str(docs_path)], actor="claude", operation="write", policy=loaded_policy)
    backend_result = validate_executor_target("backend", [str(backend_path)], loaded_policy)
    frontend_result = validate_executor_target("frontend", [str(backend_path)], loaded_policy)

    assert docs_result["allowed"] is True
    assert docs_result["decisions"][0]["path"] == "README.md"
    assert backend_result["allowed"] is True
    assert backend_result["decisions"][0]["path"] == "apps/api/src/user.py"
    assert frontend_result["allowed"] is False
    assert frontend_result["decisions"][0]["owner"] == "backend"


def test_loaded_policy_rejects_workspace_external_absolute_paths(tmp_path):
    routing_file = tmp_path / "project" / "model-routing.yaml"
    routing_file.parent.mkdir()
    routing_file.write_text(merge_routing_template(""), encoding="utf-8")
    loaded_policy = load_policy(routing_file)

    outside_path = tmp_path / "outside" / "README.md"
    result = evaluate_paths([str(outside_path)], actor="claude", operation="write", policy=loaded_policy)

    assert result["allowed"] is False
    assert result["decisions"][0]["owner"] == "unknown"
    assert result["decisions"][0]["path"].endswith("/outside/README.md")


def test_policy_requires_split_first_shared_policy(policy):
    validate_policy(policy)
    policy["rules"]["shared_policy"] = "direct"
    with pytest.raises(ValueError):
        validate_policy(policy)


def test_merge_routing_template_preserves_valid_v2_policy():
    existing = """version: 2

orchestration_paths:
  - "codecgc/**"
docs_paths:
  - "README.md"
frontend_paths:
  - "custom-ui/**"
backend_paths:
  - "custom-api/**"
test_paths:
  frontend: []
  backend: []
shared_paths:
  - "shared/**"
rules:
  claude_allowed_owners:
    - "orchestration"
    - "docs"
  backend_executor: "codexmcp"
  frontend_executor: "geminimcp"
  shared_policy: "split-first"
"""

    assert merge_routing_template(existing) == existing


def test_parse_hook_payload_supports_multiedit():
    tool_name, file_path = parse_hook_payload(
        '{"tool_name":"MultiEdit","tool_input":{"file_path":"apps/api/src/user.py"}}'
    )

    assert tool_name == "MultiEdit"
    assert file_path == "apps/api/src/user.py"
