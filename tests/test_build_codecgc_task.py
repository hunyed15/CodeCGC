"""Tests for build_codecgc_task.py - task payload construction."""
import pytest
from pathlib import Path
from unittest.mock import Mock
from build_codecgc_task import (
    normalize_string_list,
    resolve_optional_value,
    is_executable_codecgc_block,
    build_tool_call,
)


@pytest.mark.unit
class TestNormalizeStringList:
    """Test string list normalization."""

    def test_normalize_none_returns_empty_list(self):
        assert normalize_string_list(None) == []

    def test_normalize_empty_string_returns_empty_list(self):
        assert normalize_string_list("") == []

    def test_normalize_single_string_returns_list(self):
        result = normalize_string_list("src/api/")
        assert result == ["src/api/"]

    def test_normalize_list_of_strings_returns_same(self):
        input_list = ["src/api/", "src/db/"]
        result = normalize_string_list(input_list)
        assert result == ["src/api/", "src/db/"]

    def test_normalize_filters_empty_strings(self):
        input_list = ["src/api/", "", "src/db/", ""]
        result = normalize_string_list(input_list)
        assert result == ["src/api/", "src/db/"]

    def test_normalize_strips_whitespace(self):
        input_list = ["  src/api/  ", " src/db/ "]
        result = normalize_string_list(input_list)
        assert result == ["src/api/", "src/db/"]

    def test_normalize_comma_separated_string(self):
        result = normalize_string_list("src/api/, src/db/, src/ui/")
        assert result == ["src/api/", "src/db/", "src/ui/"]

    def test_normalize_mixed_types_converts_to_strings(self):
        input_list = ["src/api/", 123, None, "src/db/"]
        result = normalize_string_list(input_list)
        assert result == ["src/api/", "123", "src/db/"]


@pytest.mark.unit
class TestResolveOptionalValue:
    """Test optional value resolution with fallback chain."""

    def test_resolve_returns_explicit_value_when_provided(self):
        result = resolve_optional_value("explicit", "from_spec", "fallback")
        assert result == "explicit"

    def test_resolve_returns_spec_value_when_explicit_is_none(self):
        result = resolve_optional_value(None, "from_spec", "fallback")
        assert result == "from_spec"

    def test_resolve_returns_fallback_when_both_none(self):
        result = resolve_optional_value(None, None, "fallback")
        assert result == "fallback"

    def test_resolve_returns_none_when_all_none(self):
        result = resolve_optional_value(None, None, None)
        assert result is None

    def test_resolve_empty_string_is_treated_as_none(self):
        result = resolve_optional_value("", "from_spec", "fallback")
        assert result == "from_spec"

    def test_resolve_zero_is_valid_value(self):
        result = resolve_optional_value(0, 100, 200)
        assert result == 0

    def test_resolve_false_is_valid_value(self):
        result = resolve_optional_value(False, True, True)
        assert result is False

    def test_resolve_empty_list_is_treated_as_none(self):
        result = resolve_optional_value([], ["from_spec"], ["fallback"])
        assert result == ["from_spec"]


@pytest.mark.unit
class TestIsExecutableCodecgcBlock:
    """Test codecgc block executability validation."""

    def test_executable_with_all_required_fields(self):
        block = {
            "kind": "backend",
            "target_paths": ["src/api/"],
            "task_summary": "Implement API",
            "task_id": "api-impl",
        }
        assert is_executable_codecgc_block(block) is True

    def test_executable_with_minimal_fields(self):
        block = {
            "kind": "frontend",
            "target_paths": ["src/ui/"],
        }
        assert is_executable_codecgc_block(block) is True

    def test_not_executable_missing_kind(self):
        block = {
            "target_paths": ["src/api/"],
            "task_summary": "Implement API",
        }
        assert is_executable_codecgc_block(block) is False

    def test_not_executable_kind_is_empty_string(self):
        block = {
            "kind": "",
            "target_paths": ["src/api/"],
        }
        assert is_executable_codecgc_block(block) is False

    def test_not_executable_kind_is_auto(self):
        block = {
            "kind": "auto",
            "target_paths": ["src/api/"],
        }
        assert is_executable_codecgc_block(block) is False

    def test_not_executable_missing_target_paths(self):
        block = {
            "kind": "backend",
            "task_summary": "Implement API",
        }
        assert is_executable_codecgc_block(block) is False

    def test_not_executable_empty_target_paths_list(self):
        block = {
            "kind": "backend",
            "target_paths": [],
        }
        assert is_executable_codecgc_block(block) is False

    def test_not_executable_target_paths_with_only_empty_strings(self):
        block = {
            "kind": "backend",
            "target_paths": ["", "  ", ""],
        }
        assert is_executable_codecgc_block(block) is False

    def test_executable_target_paths_with_mixed_empty_and_valid(self):
        block = {
            "kind": "backend",
            "target_paths": ["", "src/api/", "  "],
        }
        # Should be executable because at least one valid path exists
        assert is_executable_codecgc_block(block) is True

    def test_not_executable_none_input(self):
        assert is_executable_codecgc_block(None) is False

    def test_not_executable_non_dict_input(self):
        assert is_executable_codecgc_block("not a dict") is False
        assert is_executable_codecgc_block(["list"]) is False
        assert is_executable_codecgc_block(123) is False


@pytest.mark.integration
class TestLoadChecklistStepPayload:
    """Integration tests for loading step payload from checklist."""

    @pytest.fixture
    def sample_checklist_file(self, tmp_path):
        """Create a sample checklist with various step configurations."""
        checklist_path = tmp_path / "test-checklist.yaml"
        content = """feature: test-feature
artifact_class: product
steps:
  - action: "Backend implementation"
    status: pending
    exit_signal: "API endpoints working"
    codecgc:
      kind: backend
      task_id: backend-impl
      task_summary: "Implement backend API"
      target_paths: ["src/api/", "src/db/"]
      constraints: ["Use FastAPI", "Add type hints"]
      acceptance: ["All tests pass", "API documented"]
      timeout_seconds: 300
      session_id: "session-123"
      codex_sandbox: "workspace-write"

  - action: "Frontend implementation"
    status: pending
    codecgc:
      kind: frontend
      task_summary: "Implement UI components"
      target_paths: ["src/components/"]
      gemini_sandbox: true
"""
        checklist_path.write_text(content, encoding="utf-8")
        return checklist_path

    def test_load_step_payload_with_all_fields(self, sample_checklist_file):
        """Test loading a step with all optional fields specified."""
        from build_codecgc_task import load_checklist_step_payload

        # Mock args
        args = Mock()
        args.checklist_file = str(sample_checklist_file)
        args.step_number = 1
        args.kind = "auto"
        args.task_summary = None
        args.target_path = None
        args.constraint = None
        args.acceptance = None
        args.task_id = None
        args.cd = None
        args.routing_file = "model-routing.yaml"
        args.session_id = None
        args.model = None
        args.profile = None
        args.codex_sandbox = None
        args.gemini_sandbox = None
        args.return_all_messages = None

        payload = load_checklist_step_payload(args)

        assert payload["kind"] == "backend"
        assert payload["task_id"] == "backend-impl"
        assert payload["task_summary"] == "Implement backend API"
        assert payload["target_path"] == ["src/api/", "src/db/"]
        assert payload["constraint"] == ["Use FastAPI", "Add type hints"]
        assert payload["acceptance"] == ["All tests pass", "API documented"]
        assert payload["timeout_seconds"] == 300
        assert payload["session_id"] == "session-123"
        assert payload["codex_sandbox"] == "workspace-write"
        assert payload["gemini_sandbox"] is False
        assert payload["source"]["step_number"] == 1
        assert payload["source"]["artifact_type"] == "feature"
        assert payload["source"]["artifact_slug"] == "test-feature"

    def test_load_step_payload_with_minimal_fields(self, sample_checklist_file):
        """Test loading a step with minimal fields."""
        from build_codecgc_task import load_checklist_step_payload

        args = Mock()
        args.checklist_file = str(sample_checklist_file)
        args.step_number = 2
        args.kind = "auto"
        args.task_summary = None
        args.target_path = None
        args.constraint = None
        args.acceptance = None
        args.task_id = None
        args.cd = None
        args.routing_file = "model-routing.yaml"
        args.session_id = None
        args.model = None
        args.profile = None
        args.codex_sandbox = None
        args.gemini_sandbox = None
        args.return_all_messages = None

        payload = load_checklist_step_payload(args)

        assert payload["kind"] == "frontend"
        assert payload["task_summary"] == "Implement UI components"
        assert payload["target_path"] == ["src/components/"]
        assert payload["timeout_seconds"] == 0  # Not specified, defaults to 0
        assert payload["gemini_sandbox"] is True
        assert payload["source"]["step_number"] == 2

    def test_build_frontend_tool_call_forwards_timeout_to_gemini(self, sample_checklist_file):
        args = Mock()
        args.checklist_file = str(sample_checklist_file)
        args.step_number = 2
        args.kind = "auto"
        args.task_summary = None
        args.target_path = None
        args.constraint = None
        args.acceptance = None
        args.task_id = None
        args.cd = None
        args.routing_file = "model-routing.yaml"
        args.session_id = None
        args.model = None
        args.profile = None
        args.codex_sandbox = None
        args.gemini_sandbox = None
        args.return_all_messages = None

        checklist_path = Path(sample_checklist_file)
        checklist_text = checklist_path.read_text(encoding="utf-8")
        checklist_path.write_text(
            checklist_text.replace(
                'target_paths: ["src/components/"]\n      gemini_sandbox: true',
                'target_paths: ["src/components/"]\n      timeout_seconds: 240\n      gemini_sandbox: true',
            ),
            encoding="utf-8",
        )
        routing = {
            "version": 2,
            "orchestration_paths": [],
            "docs_paths": [],
            "frontend_paths": ["src/components/**"],
            "backend_paths": ["src/api/**", "src/db/**"],
            "test_paths": {"frontend": [], "backend": []},
            "shared_paths": [],
            "rules": {
                "claude_allowed_owners": ["orchestration", "docs"],
                "backend_executor": "codexmcp",
                "frontend_executor": "geminimcp",
                "shared_policy": "split-first",
            },
        }

        payload = build_tool_call(args, routing)

        assert payload["target"] == "frontend"
        assert payload["timeout_seconds"] == 240
        assert payload["tool_args"]["timeout_seconds"] == 240
