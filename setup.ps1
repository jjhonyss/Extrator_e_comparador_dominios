$ErrorActionPreference = "Stop"

$Python = "$env:LocalAppData\Programs\Python\Python311\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

if (-not (Test-Path -LiteralPath ".venv")) {
    & $Python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\pip.exe" install -r requirements.txt

"Ambiente configurado. Execute: .\.venv\Scripts\python.exe app.py"
