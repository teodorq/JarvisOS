from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = (ROOT / "tools" / "audit_azure_guardrails.ps1").read_text(
    encoding="utf-8"
)
INSTALLER = (
    ROOT / "tools" / "install_azure_guardrail_audit.ps1"
).read_text(encoding="utf-8")
README = (ROOT / "infra" / "azure" / "README.md").read_text(
    encoding="utf-8"
)


def test_audit_covers_security_cost_identity_and_runtime() -> None:
    required = (
        "storage_shared_key_enabled",
        "storage_public_blob_enabled",
        "Storage Table Data Contributor",
        "Storage Queue Data Contributor",
        "Storage Queue Data Message Processor",
        "Container Apps Contributor",
        '"github-$branch"',
        '@("main", "develop")',
        "budget_profile_drift",
        "50,80,100",
        "remote_access_verified",
        "azure_queue",
    )
    for marker in required:
        assert marker in AUDIT


def test_audit_emits_only_a_safe_summary() -> None:
    assert "contactEmails" in AUDIT
    assert "teodorq7" not in AUDIT
    assert "clientSecret" not in AUDIT
    assert "api-token" not in AUDIT
    assert "azure_guardrail_audit.jsonl" in AUDIT
    assert "Write-SafeAuditResult -Result $safeResult" in AUDIT
    assert "Write-Output $raw" not in AUDIT
    assert "Add-Content -LiteralPath $logPath -Value $line" in AUDIT
    assert '("audit_execution_failed_" + $currentStage)' in AUDIT


def test_audit_is_local_weekly_and_hidden() -> None:
    assert 'taskName = "JARVIS OS Azure Guardrail Audit"' in INSTALLER
    assert "New-ScheduledTaskTrigger -Weekly" in INSTALLER
    assert "-DaysOfWeek Monday" in INSTALLER
    assert '-At "09:00"' in INSTALLER
    assert "-WindowStyle Hidden" in INSTALLER
    assert "StartWhenAvailable" in INSTALLER
    assert "Start-ScheduledTask -TaskName $taskName" in INSTALLER
    assert "Local Azure guardrail audit" in README
    assert "live authentication and budget documents stay" in README
