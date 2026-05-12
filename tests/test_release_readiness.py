from audit_codecgc_package_runtime import build_runtime_requirement_set
from audit_codecgc_release_readiness import RELEASE_PROBE_ROOT_ENV
from audit_codecgc_release_readiness import collect_install_probe


def test_release_readiness_probe_installs_into_configured_temp_root(monkeypatch, tmp_path):
    monkeypatch.setenv(RELEASE_PROBE_ROOT_ENV, str(tmp_path))

    result = collect_install_probe()

    assert result["mode"] == "temporary-project-install"
    assert result["workspace"].startswith(str(tmp_path))
    assert result["install_status"]["summary"]["project_ready"] is True
    assert result["doctor_status"]["summary"]["ready"] is True


def test_package_runtime_audit_requires_project_policy_templates():
    required_paths = build_runtime_requirement_set()["required_paths"]

    assert "codecgc/templates/project/claude/settings.local.json" in required_paths
    assert "codecgc/templates/project/codex/codecgcrc.json" in required_paths
    assert "codecgc/templates/project/gemini/policies/codecgc-policy.toml" in required_paths
