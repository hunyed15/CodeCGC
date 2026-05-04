"""Tests for route_codecgc_workflow.py - workflow routing decisions."""
import pytest
from pathlib import Path
from route_codecgc_workflow import (
    first_pending_step_is_not_executable,
    parse_review_metadata,
)


@pytest.mark.unit
class TestFirstPendingStepIsNotExecutable:
    """Test the fixed logic that scans for first pending step."""

    @pytest.fixture
    def checklist_step1_done_step2_planning(self, tmp_path):
        """Step 1 is done, step 2 is pending but planning-only."""
        path = tmp_path / "test-checklist.yaml"
        content = """feature: test
steps:
  - action: "First task"
    status: done
    codecgc:
      kind: backend
      target_paths: ["src/"]
      task_summary: "Completed"

  - action: "Planning task"
    status: pending
    codecgc:
      task_summary: "Need to plan"

  - action: "Implementation task"
    status: pending
    codecgc:
      kind: backend
      target_paths: ["src/api/"]
      task_summary: "Ready to implement"
"""
        path.write_text(content, encoding="utf-8")
        return path

    @pytest.fixture
    def checklist_first_pending_is_executable(self, tmp_path):
        """First pending step is executable."""
        path = tmp_path / "executable-checklist.yaml"
        content = """feature: test
steps:
  - action: "Done task"
    status: done
    codecgc:
      kind: backend
      target_paths: ["src/"]
      task_summary: "Completed"

  - action: "Next task"
    status: pending
    codecgc:
      kind: frontend
      target_paths: ["src/ui/"]
      task_summary: "Ready"
"""
        path.write_text(content, encoding="utf-8")
        return path

    @pytest.fixture
    def checklist_no_steps(self, tmp_path):
        """Checklist without steps section."""
        path = tmp_path / "no-steps.yaml"
        content = """feature: test
artifact_class: product
"""
        path.write_text(content, encoding="utf-8")
        return path

    def test_returns_true_when_first_pending_is_planning_only(
        self, checklist_step1_done_step2_planning
    ):
        """Should detect that step 2 (first pending) is not executable."""
        is_blocked, metadata = first_pending_step_is_not_executable(
            checklist_step1_done_step2_planning
        )
        assert is_blocked is True
        assert metadata is not None
        assert metadata["step_number"] == 2
        assert metadata["executable"] is False

    def test_returns_false_when_first_pending_is_executable(
        self, checklist_first_pending_is_executable
    ):
        """Should detect that step 2 (first pending) is executable."""
        is_blocked, metadata = first_pending_step_is_not_executable(
            checklist_first_pending_is_executable
        )
        assert is_blocked is False
        assert metadata is not None
        assert metadata["step_number"] == 2
        assert metadata["executable"] is True

    def test_returns_false_when_no_steps_section(self, checklist_no_steps):
        """Should return False when checklist has no steps."""
        is_blocked, metadata = first_pending_step_is_not_executable(checklist_no_steps)
        assert is_blocked is False
        assert metadata is None

    @pytest.fixture
    def checklist_all_done(self, tmp_path):
        """All steps are done."""
        path = tmp_path / "all-done.yaml"
        content = """feature: test
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

    def test_returns_false_when_no_pending_steps(self, checklist_all_done):
        """Should return False when all steps are done."""
        is_blocked, metadata = first_pending_step_is_not_executable(checklist_all_done)
        assert is_blocked is False
        assert metadata is None


@pytest.mark.unit
class TestParseReviewMetadata:
    """Test review metadata extraction from acceptance/fix-note markdown."""

    def test_parse_accepted_review_chinese(self):
        """Parse Chinese format accepted review."""
        markdown = """# 审核结果

- 审核决策: accepted
- 审核步骤序号: 3
- 审核时间: 2026-05-04T10:30:00Z

## 范围核查
通过
"""
        metadata = parse_review_metadata(markdown)
        assert metadata["decision"] == "accepted"
        assert metadata["step_number"] == 3

    def test_parse_changes_requested_review_english(self):
        """Parse English format changes-requested review."""
        markdown = """# Review Result

- Review decision: changes-requested
- Reviewed step_number: 5
- Review timestamp: 2026-05-04T10:30:00Z

## Scope Check
Failed
"""
        metadata = parse_review_metadata(markdown)
        assert metadata["decision"] == "changes-requested"
        assert metadata["step_number"] == 5

    def test_parse_review_missing_step_number(self):
        """Should return 0 for step_number when not found."""
        markdown = """# Review Result

- Review decision: accepted
- Review timestamp: 2026-05-04T10:30:00Z
"""
        metadata = parse_review_metadata(markdown)
        assert metadata["decision"] == "accepted"
        assert metadata["step_number"] == 0

    def test_parse_review_missing_decision(self):
        """Should return empty string for decision when not found."""
        markdown = """# Review Result

- Reviewed step_number: 2
- Review timestamp: 2026-05-04T10:30:00Z
"""
        metadata = parse_review_metadata(markdown)
        assert metadata["decision"] == ""
        assert metadata["step_number"] == 2

    def test_parse_empty_markdown(self):
        """Should handle empty input gracefully."""
        metadata = parse_review_metadata("")
        assert metadata["decision"] == ""
        assert metadata["step_number"] == 0

    def test_parse_review_with_mixed_format(self):
        """Should handle mixed Chinese/English format."""
        markdown = """# 审核结果

- Review decision: accepted
- 审核步骤序号: 7
"""
        metadata = parse_review_metadata(markdown)
        assert metadata["decision"] == "accepted"
        assert metadata["step_number"] == 7
