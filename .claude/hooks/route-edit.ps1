$ErrorActionPreference = "Stop"

function Write-Deny($reason) {
    $payload = @{
        decision = "deny"
        reason   = $reason
    } | ConvertTo-Json -Compress
    [Console]::Out.Write($payload)
    exit 0
}

function Write-Approve() {
    exit 0
}

$inputJson = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($inputJson)) {
    Write-Approve
}

$hookData = $inputJson | ConvertFrom-Json
$toolName = [string]$hookData.tool_name
if ($toolName -notin @("Edit", "Write")) {
    Write-Approve
}

$toolInput = $hookData.tool_input
$filePath = ""

if ($toolInput.PSObject.Properties.Name -contains "file_path") {
    $filePath = [string]$toolInput.file_path
} elseif ($toolInput.PSObject.Properties.Name -contains "path") {
    $filePath = [string]$toolInput.path
}

if ([string]::IsNullOrWhiteSpace($filePath)) {
    Write-Approve
}

$normalized = $filePath.Replace("\", "/").ToLower()

$backendHints = @(
    "/apps/api/",
    "/server/",
    "/src/server/",
    "/src/services/",
    "/src/repositories/",
    "/backend/"
)

$frontendHints = @(
    "/apps/web/",
    "/src/components/",
    "/src/pages/",
    "/src/app/",
    "/src/styles/",
    "/web/",
    "/frontend/"
)

$sharedHints = @(
    "/packages/shared/",
    "/src/shared/",
    "/src/lib/",
    "/src/types/"
)

foreach ($hint in $backendHints) {
    if ($normalized.Contains($hint)) {
        Write-Deny "CodeCGC: backend path is blocked for direct Claude editing; use Codex MCP."
    }
}

foreach ($hint in $frontendHints) {
    if ($normalized.Contains($hint)) {
        Write-Deny "CodeCGC: frontend path is blocked for direct Claude editing; use Gemini MCP."
    }
}

foreach ($hint in $sharedHints) {
    if ($normalized.Contains($hint)) {
        Write-Deny "CodeCGC: shared path is blocked for direct editing; split the task first."
    }
}

Write-Approve
