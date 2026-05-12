$ErrorActionPreference = "Stop"

function Write-Approve {
    $payload = @{
        decision = "approve"
    } | ConvertTo-Json -Compress
    [Console]::Out.Write($payload)
    exit 0
}

function Write-Deny($reason) {
    $payload = @{
        decision = "deny"
        reason   = $reason
    } | ConvertTo-Json -Compress
    [Console]::Out.Write($payload)
    exit 0
}

$inputJson = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($inputJson)) {
    Write-Approve
}

$configuredPackageRoot = [Environment]::GetEnvironmentVariable("CODECGC_PACKAGE_ROOT")
if (-not [string]::IsNullOrWhiteSpace($configuredPackageRoot)) {
    $packageRoot = Resolve-Path $configuredPackageRoot
} else {
    $packageRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
}

$configuredWorkspaceRoot = [Environment]::GetEnvironmentVariable("CODECGC_WORKSPACE_ROOT")
if (-not [string]::IsNullOrWhiteSpace($configuredWorkspaceRoot)) {
    $workspaceRoot = Resolve-Path $configuredWorkspaceRoot
} else {
    $workspaceRoot = Resolve-Path (Get-Location)
}

$policyScript = Join-Path $packageRoot "scripts\codecgc_policy.py"
$routingFile = Join-Path $workspaceRoot "model-routing.yaml"
$mcpConfigFile = Join-Path $workspaceRoot ".mcp.json"

if (-not (Test-Path $policyScript)) {
    Write-Deny "CodeCGC: policy checker is missing: $policyScript"
}

$pythonCommand = [Environment]::GetEnvironmentVariable("CODECGC_PYTHON_COMMAND")
if ([string]::IsNullOrWhiteSpace($pythonCommand) -and (Test-Path $mcpConfigFile)) {
    try {
        $mcpConfig = Get-Content -Raw $mcpConfigFile | ConvertFrom-Json
        $pythonCommand = [string]$mcpConfig.mcpServers.codecgc.command
    } catch {
        $pythonCommand = ""
    }
}
if ([string]::IsNullOrWhiteSpace($pythonCommand)) {
    $pythonCommand = "python"
}

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $pythonCommand
$escapedPolicyScript = $policyScript.Replace('"', '\"')
$escapedRoutingFile = $routingFile.Replace('"', '\"')
$psi.Arguments = "`"$escapedPolicyScript`" --hook-check --actor claude --operation write --routing-file `"$escapedRoutingFile`""
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true

$process = [System.Diagnostics.Process]::Start($psi)
$process.StandardInput.Write($inputJson)
$process.StandardInput.Close()
$stdout = $process.StandardOutput.ReadToEnd()
$stderr = $process.StandardError.ReadToEnd()
$process.WaitForExit()

if ($process.ExitCode -ne 0) {
    $detail = if ([string]::IsNullOrWhiteSpace($stderr)) { $stdout } else { $stderr }
    Write-Deny "CodeCGC: policy checker failed. $detail"
}

if ([string]::IsNullOrWhiteSpace($stdout)) {
    Write-Approve
}

[Console]::Out.Write($stdout)
