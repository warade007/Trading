$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        py -3.13 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & .\.venv\Scripts\python.exe scripts/security_keys.py init
    if ($LASTEXITCODE -ne 0) { throw 'Local security key initialization failed.' }
    New-Item -ItemType Directory -Path data -Force | Out-Null
    & .\.venv\Scripts\python.exe manage.py migrate
    if ($LASTEXITCODE -ne 0) { throw 'Migrations failed.' }
    & .\.venv\Scripts\python.exe manage.py load_demo
    if ($LASTEXITCODE -ne 0) { throw 'Demo import failed.' }
    & .\.venv\Scripts\python.exe manage.py check
    if ($LASTEXITCODE -ne 0) { throw 'Django checks failed.' }
    Write-Output 'Ready: .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001 --noreload'
} finally { Pop-Location }
