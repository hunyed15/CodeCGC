"""Tests for codecgc_step_control.py - step selection and metadata extraction."""
import pytest
from pathlib import Path
from codecgc_step_control import (
    select_next_executable_step,
    get_step_metadata,
    is_executable_codecgc_block,
    replace_step_status,
)


@pytest.mark.unit
class TestIsExecutableCodecgcBlock:
    """Test codecgc block executability detection."""

    def test_executable_with_kind_and_target_paths(self):
        block = {
            "kind": "backend",
            "target_paths": ["src/api/"],
            "task_summary": "Implement API",
        }
        assert is_executable_codecgc_block(block) is True

    def test_not_executable_missing_kind(self):
        block = {
            "target_paths": ["src/api/"],
            "task_summary": "Implement API",
        }
        assert is_executable_codecgc_block(block) is False

    def test_not_executable_missing_target_paths(self):
        block = {
            "kind": "backend",
            "task_summary": "Implement API",
        }
        assert is_executable_codecgc_block(block) is False

    def test_not_executable_empty_target_paths(self):
        block = {
            "kind": "backend",
            "target_paths": [],
            "task_summary": "Implement API",
        }
        assert is_executable_codecgc_block(block) is False

    def test_not_executable_none_input(self):
        assert is_executable_codecgc_block(None) is False

    def test_not_executable_non_dict(self):
        assert is_executable_codecgc_block("not a dict") is False


@pytest.mark.unit
class TestReplaceStepStatus:
    """Test YAML step status replacement."""

    def test_replace_first_step_status(self):
        yaml_text = """steps:
  - action: "Step 1"
    status: pending
    codecgc:
      kind: backend
  - action: "Step 2"
    status: pending
"""
        result = replace_step_status(yaml_text, 1, "done")
        assert "  - action: \"Step 1\"\n    status: done" in result
        assert yaml_text.count("status: pending") == 2
        assert result.count("status: pending") == 1
        assert result.count("status: done") == 1

    def test_replace_second_step_status(self):
        yaml_text = """steps:
  - action: "Step 1"
    status: done
  - action: "Step 2"
    status: pending
  - action: "Step 3"
    status: pending
"""
        result = replace_step_status(yaml_text, 2, "done")
        assert "  - action: \"Step 2\"\n    status: done" in result
        assert result.count("status: done") == 2
        assert result.count("status: pending") == 1

    def test_replace_preserves_indentation(self):
        yaml_text = """steps:
  - action: "Step 1"
    status: pending
    codecgc:
      kind: backend
"""
        result = replace_step_status(yaml_text, 1, "in_progress")
        assert "    status: in_progress" in result
        # Verify indentation is preserved (4 spaces before status)
        lines = result.split("\n")
        status_line = [l for l in lines if "status:" in l][0]
        assert status_line.startswith("    status:")

    def test_replace_invalid_step_number_raises(self):
        yaml_text = """steps:
  - action: "Step 1"
    status: pending
"""
        with pytest.raises(ValueError, match="Could not find status field for step 99"):
            replace_step_status(yaml_text, 99, "done")


@pytest.mark.unit
class TestGetStepMetadata:
    """Test step metadata extraction from checklist."""

    @pytest.fixture
    def sample_checklist(self, tmp_path):
        """Create a sample checklist YAML file."""
        checklist_path = tmp_path / "test-checklist.yaml"
        content = """feature: test-feature
artifact_class: product
steps:
  - action: "Planning step"
    status: pending
    codecgc:
      task_summary: "Plan the feature"

  - action: "Backend implementation"
    status: pending
    codecgc:
      kind: backend
      task_id: backend-task
      task_summary: "Implement backend"
      target_paths: ["src/api/"]
      timeout_seconds: 300

  - action: "Frontend implementation"
    status: done
    codecgc:
      kind: frontend
      task_id: frontend-task
      task_summary: "Implement frontend"
      target_paths: ["src/components/"]
"""
        checklist_path.write_text(content, encoding="utf-8")
        return checklist_path

    def test_get_metadata_for_planning_step(self, sample_checklist):
        metadata = get_step_metadata(sample_checklist, 1)
        assert metadata["step_number"] == 1
        assert metadata["executable"] is False
        assert metadata["task_summary"] == "Plan the feature"
        assert metadata["kind"] == ""
        assert metadata["target_paths"] == []

    def test_get_metadata_for_executable_backend_step(self, sample_checklist):
        metadata = get_step_metadata(sample_checklist, 2)
        assert metadata["step_number"] == 2
        assert metadata["executable"] is True
        assert metadata["task_id"] == "backend-task"
        assert metadata["task_summary"] == "Implement backend"
        assert metadata["kind"] == "backend"
        assert metadata["target_paths"] == ["src/api/"]
        assert metadata["timeout_seconds"] == 300

    def test_get_metadata_for_done_step(self, sample_checklist):
        metadata = get_step_metadata(sample_checklist, 3)
        assert metadata["step_number"] == 3
        assert metadata["executable"] is True
        assert metadata["task_id"] == "frontend-task"
        assert metadata["kind"] == "frontend"

    def test_get_metadata_invalid_step_number_raises(self, sample_checklist):
        with pytest.raises(ValueError, match="Step number must be between"):
            get_step_metadata(sample_checklist, 99)

    def test_get_metadata_zero_step_number_raises(self, sample_checklist):
        with pytest.raises(ValueError, match="Step number must be between"):
            get_step_metadata(sample_checklist, 0)


@pytest.mark.unit
class TestSelectNextExecutableStep:
    """Test next executable step selection logic."""

    @pytest.fixture
    def checklist_with_planning_blocker(self, tmp_path):
        """Checklist with a planning-only step blocking execution."""
        path = tmp_path / "blocked-checklist.yaml"
        content = """feature: blocked-feature
steps:
  - action: "Planning step"
    status: pending
    codecgc:
      task_summary: "Plan first"

  - action: "Executable step"
    status: pending
    codecgc:
      kind: backend
      target_paths: ["src/"]
      task_summary: "Implement"
"""
        path.write_text(content, encoding="utf-8")
        return path

    @pytest.fixture
    def checklist_with_executable_steps(self, tmp_path):
        """Checklist with executable steps ready."""
        path = tmp_path / "ready-checklist.yaml"
        content = """feature: ready-feature
steps:
  - action: "First task"
    status: done
    codecgc:
      kind: backend
      target_paths: ["src/api/"]
      task_summary: "Done task"

  - action: "Second task"
    status: pending
    codecgc:
      kind: frontend
      target_paths: ["src/ui/"]
      task_summary: "Next task"
      timeout_seconds: 180

  - action: "Third task"
    status: pending
    codecgc:
      kind: backend
      target_paths: ["src/db/"]
      task_summary: "Later task"
"""
        path.write_text(content, encoding="utf-8")
        return path

    def test_select_raises_when_planning_step_blocks(self, checklist_with_planning_blocker):
        with pytest.raises(ValueError, match="Planning-only step 1 must be resolved"):
            select_next_executable_step(checklist_with_planning_blocker)

    def test_select_returns_first_pending_executable(self, checklist_with_executable_steps):
        result = select_next_executable_step(checklist_with_executable_steps)
        assert result["step_number"] == 2
        assert result["task_summary"] == "Next task"
        assert result["kind"] == "frontend"
        assert result["target_paths"] == ["src/ui/"]
        assert result["timeout_seconds"] == 180

    def test_select_skips_done_steps(self, checklist_with_executable_steps):
        result = select_next_executable_step(checklist_with_executable_steps)
        # Should skip step 1 (done) and return step 2 (pending)
        assert result["step_number"] == 2

    @pytest.fixture
    def checklist_all_done(self, tmp_path):
        """Checklist with all steps completed."""
        path = tmp_path / "complete-checklist.yaml"
        content = """feature: complete-feature
steps:
  - action: "Task 1"
    status: done
    codecgc:
      kind: backend
      target_paths: ["src/"]
      task_summary: "Done"
"""
        path.write_text(content, encoding="utf-8")
        return path

    def test_select_raises_when_no_pending_steps(self, checklist_all_done):
        with pytest.raises(ValueError, match="No pending executable step remains"):
            select_next_executable_step(checklist_all_done)
