$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    "Ambiente virtual nao encontrado. Execute primeiro: .\setup.ps1"
    exit 1
}

Start-Process -FilePath $Python -ArgumentList (Join-Path $ProjectDir "app.py") -WorkingDirectory $ProjectDir
Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:5000"
