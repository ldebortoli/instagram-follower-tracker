param(
    [string]$EnvironmentFile = "apps\jo-bot\.env.local",
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
Set-Location $Root

if ($InstallDependencies) {
    python -m pip install -e ".[bot]"
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron instalar las dependencias de Jo Bot."
    }
}

$EnvironmentPath = Join-Path $Root $EnvironmentFile
if (-not (Test-Path -LiteralPath $EnvironmentPath)) {
    throw "Falta $EnvironmentPath. Copiá apps\jo-bot\.env.example y configurá JO_BOT_ADMIN_USER_IDS."
}

Get-Content -LiteralPath $EnvironmentPath -Encoding UTF8 | ForEach-Object {
    $Line = $_.Trim()
    if (-not $Line -or $Line.StartsWith("#")) {
        return
    }
    $Parts = $Line.Split("=", 2)
    if ($Parts.Count -ne 2 -or -not $Parts[0].Trim()) {
        throw "Línea inválida en ${EnvironmentPath}: $Line"
    }
    Set-Item -Path "Env:$($Parts[0].Trim())" -Value $Parts[1].Trim()
}

Write-Host "Iniciando Jo Bot. Cerralo con Ctrl+C."
python -m jo_bot
exit $LASTEXITCODE
