<#
.SYNOPSIS
Construye y verifica el paquete autónomo de Windows sin usar Codex.

.DESCRIPTION
Crea un entorno virtual de build reutilizable, instala las dependencias,
ejecuta lint y tests, genera los ejecutables con PyInstaller, valida el
checksum, opcionalmente descomprime el paquete para probarlo y puede subir
el código validado a la rama actual de GitHub.

.PARAMETER SkipInstall
No actualiza las dependencias del entorno de build existente.

.PARAMETER SkipTests
Omite ruff y pytest. No se recomienda para una Release.

.PARAMETER Extract
Descomprime el ZIP terminado dentro de release\test-current.

.PARAMETER RecreateEnvironment
Elimina y vuelve a crear .venv-build antes de comenzar.

.PARAMETER PushCode
Después de un build correcto, ejecuta git add, crea un commit si hay cambios
y sube la rama actual al remote origin.

.PARAMETER CommitMessage
Mensaje para el commit creado con PushCode. Si se omite, usa la versión de
pyproject.toml para generar uno.

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -Extract

.EXAMPLE
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -Extract -PushCode
#>

[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$SkipTests,
    [switch]$Extract,
    [switch]$RecreateEnvironment,
    [switch]$PushCode,
    [string]$CommitMessage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

if ($env:OS -ne "Windows_NT") {
    throw "Este script genera el paquete de Windows y debe ejecutarse en Windows."
}

$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\.."))
$EnvironmentDirectory = Join-Path $Root ".venv-build"
$BuildPython = Join-Path $EnvironmentDirectory "Scripts\python.exe"
$ReleaseDirectory = Join-Path $Root "release"
$LogDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "Seguidores-build"
$LogPath = Join-Path $LogDirectory "build-latest.log"
$PromptPath = Join-Path $LogDirectory "PROMPT-build-latest.txt"
$PushBranch = $null
$PushedCommit = $null
$CurrentStep = "Inicialización"
$Failure = $null
$LocationPushed = $false
$TranscriptStarted = $false

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
foreach ($PreviousDiagnostic in ($LogPath, $PromptPath)) {
    if (Test-Path -LiteralPath $PreviousDiagnostic) {
        Remove-Item -LiteralPath $PreviousDiagnostic -Force
    }
}

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    $script:CurrentStep = $Label
    Write-Host ""
    Write-Host "==> $Label" -ForegroundColor Cyan
    # Windows PowerShell 5.1 can turn the first stderr line from Python into a
    # terminating error when ErrorActionPreference is Stop. Temporarily merge
    # stderr into stdout so the complete traceback reaches the transcript.
    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Command 2>&1 | ForEach-Object { Write-Host $_ }
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    if ($ExitCode -ne 0) {
        throw "Falló el paso '$Label' (código $ExitCode)."
    }
    $script:CurrentStep = $null
}

function Stop-PreviousSeguidoresBuilds {
    $RepositoryPrefix = $Root.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
        [System.IO.Path]::DirectorySeparatorChar
    $RunningBuilds = @(
        Get-Process -Name "seguidores", "seguidores-gui" -ErrorAction SilentlyContinue |
            Where-Object {
                try {
                    $ExecutablePath = $_.Path
                    -not [string]::IsNullOrWhiteSpace($ExecutablePath) -and
                        $ExecutablePath.StartsWith(
                            $RepositoryPrefix,
                            [System.StringComparison]::OrdinalIgnoreCase
                        )
                }
                catch {
                    $false
                }
            }
    )
    if ($RunningBuilds.Count -eq 0) {
        return
    }

    foreach ($Process in $RunningBuilds) {
        Write-Host "Cerrando ejecutable anterior: $($Process.Path) (PID $($Process.Id))"
        if ($Process.MainWindowHandle -ne 0) {
            $null = $Process.CloseMainWindow()
        }
    }
    Start-Sleep -Milliseconds 1500

    foreach ($Process in $RunningBuilds) {
        try {
            if (-not $Process.HasExited) {
                Write-Host "El proceso $($Process.Id) no cerró normalmente; se finalizará."
                Stop-Process -InputObject $Process -Force -ErrorAction Stop
            }
        }
        catch [System.InvalidOperationException] {
            # El proceso terminó entre la consulta y la comprobación.
        }
    }
}

Start-Transcript -LiteralPath $LogPath -Force | Out-Null
$TranscriptStarted = $true
try {
    Push-Location $Root
    $LocationPushed = $true
    Write-Host "Log de esta ejecución: $LogPath"

    if ($PushCode) {
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            throw "No se encontró Git en PATH; no se puede usar -PushCode."
        }
        $PushBranch = (& git branch --show-current).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($PushBranch)) {
            throw "No se pudo determinar la rama actual. Verificá que el repositorio no esté en detached HEAD."
        }
        & git remote get-url origin *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "No existe el remote 'origin'; no se puede subir el código."
        }
    }

    $CurrentStep = "Cerrar ejecutable anterior"
    Stop-PreviousSeguidoresBuilds

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
        & $BuildPython apps\desktop\packaging\build.py
    }

    $CurrentStep = "Validar paquete generado"
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
        $CurrentStep = "Extraer paquete para prueba"
        $ExtractDirectory = Join-Path $ReleaseDirectory "test-current"
        if (Test-Path -LiteralPath $ExtractDirectory) {
            Remove-Item -LiteralPath $ExtractDirectory -Recurse -Force
        }
        Expand-Archive -LiteralPath $Archive.FullName -DestinationPath $ExtractDirectory -Force
        $Executable = Get-ChildItem -LiteralPath $ExtractDirectory -Recurse -File -Filter "seguidores-gui.exe" |
            Select-Object -First 1
    }

    if ($PushCode) {
        $CurrentStep = "Publicar código en GitHub"
        $EffectiveCommitMessage = if ($null -eq $CommitMessage) { "" } else { $CommitMessage.Trim() }
        if ([string]::IsNullOrWhiteSpace($EffectiveCommitMessage)) {
            $ProjectConfig = Get-Content -LiteralPath (Join-Path $Root "pyproject.toml") -Raw
            $VersionMatch = [regex]::Match(
                $ProjectConfig,
                '(?m)^version\s*=\s*"([^"]+)"'
            )
            $EffectiveCommitMessage = if ($VersionMatch.Success) {
                "update Seguidores to $($VersionMatch.Groups[1].Value)"
            }
            else {
                "update Seguidores"
            }
        }

        $PendingChanges = & git status --porcelain --untracked-files=all
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudo consultar el estado de Git."
        }
        if ($PendingChanges) {
            Invoke-NativeStep "Preparar cambios para Git" {
                git add --all
            }
            Invoke-NativeStep "Crear commit de código" {
                git commit -m $EffectiveCommitMessage
            }
        }
        else {
            Write-Host "No hay cambios sin commit; se subirá el commit actual."
        }

        Invoke-NativeStep "Subir código a origin/$PushBranch" {
            git push --set-upstream origin $PushBranch
        }
        $PushedCommit = (& git rev-parse --short HEAD).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "El push terminó, pero no se pudo obtener el commit publicado."
        }
    }

    Write-Host ""
    $CurrentStep = $null
    Write-Host "BUILD CORRECTO" -ForegroundColor Green
    Write-Host "ZIP: $($Archive.FullName)"
    Write-Host "SHA-256: $($ActualHash.ToLowerInvariant())"
    if ($null -ne $Executable) {
        Write-Host "Para probarlo: $($Executable.FullName)"
    }
    if ($null -ne $PushedCommit) {
        Write-Host "Código subido: $PushBranch @ $PushedCommit"
    }
}
catch {
    $Failure = $_
    Write-Host ""
    Write-Host "BUILD FALLIDO" -ForegroundColor Red
    Write-Host "Paso: $CurrentStep" -ForegroundColor Red
    Write-Host ($Failure | Format-List * -Force | Out-String) -ForegroundColor Red
}
finally {
    if ($LocationPushed) {
        Pop-Location
    }
    if ($TranscriptStarted) {
        Stop-Transcript | Out-Null
    }
}

if ($null -ne $Failure) {
    $ParameterSummary = if ($PSBoundParameters.Count -eq 0) {
        "(sin parámetros)"
    }
    else {
        ($PSBoundParameters.GetEnumerator() | Sort-Object Key | ForEach-Object {
            "-$($_.Key) $($_.Value)"
        }) -join " "
    }
    $Commit = "desconocido"
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $CandidateCommit = (& git -C $Root rev-parse --short HEAD 2>$null).Trim()
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($CandidateCommit)) {
            $Commit = $CandidateCommit
        }
    }
    $ErrorSummary = $Failure.Exception.Message
    $Prompt = @"
Necesito que debuggees un fallo del script de build de Seguidores.

Paso que falló: $CurrentStep
Error final: $ErrorSummary
Commit local: $Commit
Parámetros usados: $ParameterSummary

Adjunto también el log completo ubicado originalmente en:
$LogPath

Revisá el log, determiná la causa raíz, corregí el proyecto y dejame el comando para volver a ejecutar el build.
"@
    Set-Content -LiteralPath $PromptPath -Value $Prompt -Encoding UTF8
    Write-Host ""
    Write-Host "Diagnóstico guardado." -ForegroundColor Yellow
    Write-Host "Log: $LogPath"
    Write-Host "Prompt listo para enviar a Codex: $PromptPath"
    Write-Host "Adjuntá ambos archivos en este chat."
    exit 1
}
