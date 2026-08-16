param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("JARVIS_OS_TWELVE_DATA_API_KEY", "JARVIS_OS_FMP_API_KEY")]
    [string] $Name
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $projectRoot "config\forex.env"
$secret = (Get-Clipboard -Raw).Trim()

if (
    $secret.Length -lt 16 -or
    $secret.Length -gt 256 -or
    $secret -match "[\r\n\x00]" -or
    $secret -notmatch "^[A-Za-z0-9._~-]+$"
) {
    throw "Clipboard does not contain a valid API key."
}

$lines = if (Test-Path -LiteralPath $target) {
    [System.Collections.Generic.List[string]]::new(
        [string[]](Get-Content -LiteralPath $target)
    )
} else {
    [System.Collections.Generic.List[string]]::new()
}

$replacement = "$Name=$secret"
$matched = $false
for ($index = 0; $index -lt $lines.Count; $index++) {
    if ($lines[$index] -match "^\s*#?\s*$([regex]::Escape($Name))\s*=") {
        if (-not $matched) {
            $lines[$index] = $replacement
            $matched = $true
        } else {
            $lines.RemoveAt($index)
            $index--
        }
    }
}
if (-not $matched) {
    $lines.Add($replacement)
}

$utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText(
    $target,
    (($lines -join [Environment]::NewLine) + [Environment]::NewLine),
    $utf8WithoutBom
)
Set-Clipboard -Value " "
Write-Output "saved:$Name;clipboard_secret_removed:true"
