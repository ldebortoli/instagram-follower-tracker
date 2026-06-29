<#
.SYNOPSIS
Construye y verifica el paquete autónomo de Windows sin usar Codex.

.DESCRIPTION
Crea un entorno virtual de build reutilizable, instala las dependencias,
ejecuta lint y tests, genera los ejecutables con PyInstaller, valida el
checksum y opcionalmente descomprime el paquete para probarlo.

.PARAMETER SkipInstall
No actualiza las dependencias del entorno de build existente.

.PARAMETER SkipTests
Omite ruff y pytest. No se recomienda para una Release.

.PARAMETER Extract
Descomprime el ZIP terminado dentro de release\test-current.

.PARAMETER RecreateEnvironment
Elimina y vuelve a crear .venv-build antes de comenzar.

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -Extract
#>

[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$SkipTests,
    [switch]$Extract,
    [switch]$RecreateEnvironment
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "Este script genera el paquete de Windows y debe ejecutarse en Windows."
}

$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$EnvironmentDirectory = Join-Path $Root ".venv-build"
$BuildPython = Join-Path $EnvironmentDirectory "Scripts\python.exe"
$ReleaseDirectory = Join-Path $Root "release"

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Falló el paso '$Label' (código $LASTEXITCODE)."
    }
}

Push-Location $Root
try {
    if ($RecreateEnvironment -and (Test-Path -LiteralPath $EnvironmentDirectory)) {
        $ResolvedEnvironment = [System.IO.Path]::GetFullPath($EnvironmentDirectory)
        if ([System.IO.Path]::GetDirectoryName($ResolvedEnvironment) -ne $Root) {
            throw "Ruta insegura para eliminar el entorno: $ResolvedEnvironment"
        }
        Write-Host "Eliminando entorno de build anterior: $ResolvedEnvironment"
        Remove-Item -LiteralPath $ResolvedEnvironment -Recurse -Force
    }

    if (-not (Test-Path -LiteralPath $BuildPython)) {
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
            throw "No se encontró Python en PATH. Instalá Python 3.11 o posterior."
        }
        Invoke-NativeStep "Crear entorno virtual .venv-build" {
            python -m venv $EnvironmentDirectory
        }
    }

    Invoke-NativeStep "Verificar Python 3.11 o posterior" {
        & $BuildPython -c "import sys; print(sys.version); raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    }

    if (-not $SkipInstall) {
        Invoke-NativeStep "Instalar o actualizar dependencias de build" {
            & $BuildPython -m pip install --disable-pip-version-check -e ".[dev,build-app]"
        }
    }

    if (-not $SkipTests) {
        Invoke-NativeStep "Ruff" {
            & $BuildPython -m ruff check .
        }
        Invoke-NativeStep "Tests" {
            & $BuildPython -m pytest --cov=seguidores --cov-report=term-missing
        }
    }

    Invoke-NativeStep "Construir ejecutables y paquete" {
        & $BuildPython packaging\build.py
    }

    $Archive = Get-ChildItem -LiteralPath $ReleaseDirectory -File -Filter "Seguidores-*-Windows-*.zip" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $Archive) {
        throw "El build terminó sin producir un ZIP de Windows."
    }

    $ChecksumPath = $Archive.FullName + ".sha256"
    if (-not (Test-Path -LiteralPath $ChecksumPath)) {
        throw "Falta el checksum esperado: $ChecksumPath"
    }
    $ExpectedHash = ((Get-Content -LiteralPath $ChecksumPath -Raw).Trim() -split "\s+")[0]
    $ActualHash = (Get-FileHash -LiteralPath $Archive.FullName -Algorithm SHA256).Hash
    if ($ExpectedHash.ToLowerInvariant() -ne $ActualHash.ToLowerInvariant()) {
        throw "El checksum del ZIP no coincide."
    }

    $Executable = $null
    if ($Extract) {
        $ExtractDirectory = Join-Path $ReleaseDirectory "test-current"
        if (Test-Path -LiteralPath $ExtractDirectory) {
            Remove-Item -LiteralPath $ExtractDirectory -Recurse -Force
        }
        Expand-Archive -LiteralPath $Archive.FullName -DestinationPath $ExtractDirectory -Force
        $Executable = Get-ChildItem -LiteralPath $ExtractDirectory -Recurse -File -Filter "seguidores-gui.exe" |
            Select-Object -First 1
    }

    Write-Host ""
    Write-Host "BUILD CORRECTO" -ForegroundColor Green
    Write-Host "ZIP: $($Archive.FullName)"
    Write-Host "SHA-256: $($ActualHash.ToLowerInvariant())"
    if ($null -ne $Executable) {
        Write-Host "Para probarlo: $($Executable.FullName)"
    }
}
finally {
    Pop-Location
}
