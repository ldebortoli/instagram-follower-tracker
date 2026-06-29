<# Wrapper estable para el build de la aplicación de escritorio. #>

[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$SkipTests,
    [switch]$Extract,
    [switch]$RecreateEnvironment,
    [switch]$PushCode,
    [string]$CommitMessage
)

$DesktopBuild = Join-Path $PSScriptRoot "..\apps\desktop\scripts\build-windows.ps1"
& $DesktopBuild @PSBoundParameters
exit $LASTEXITCODE
