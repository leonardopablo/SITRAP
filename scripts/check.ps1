$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
& $python manage.py check
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $python -m pytest @args
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $python -m ruff check .
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $python manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn
exit $LASTEXITCODE
