param(
    [ValidateSet('Start', 'Stop', 'Status')]
    [string]$Action = 'Start',
    [string]$PostgresBin = 'C:\Program Files\PostgreSQL\18\bin',
    [int]$Port = 55432
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$local = Join-Path $root '.local'
$data = Join-Path $local 'pgdata'
$pwfile = Join-Path $local 'pg-password.txt'
$pgctl = Join-Path $PostgresBin 'pg_ctl.exe'
if ($Action -eq 'Status') {
    & $pgctl -D $data status
    exit $LASTEXITCODE
}
if ($Action -eq 'Stop') {
    & $pgctl -D $data -m fast -w stop
    exit $LASTEXITCODE
}
New-Item -ItemType Directory -Force $local | Out-Null
if (-not (Test-Path (Join-Path $data 'PG_VERSION'))) {
    if (-not (Test-Path $pwfile)) {
        [System.IO.File]::WriteAllText($pwfile, [guid]::NewGuid().ToString('N'))
    }
    & (Join-Path $PostgresBin 'initdb.exe') -D $data -U sitrap --auth=scram-sha-256 "--pwfile=$pwfile" --encoding=UTF8 --locale=C
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
& $pgctl -D $data status *> $null
if ($LASTEXITCODE) {
    & $pgctl -D $data -l (Join-Path $local 'postgres.log') -o "-h 127.0.0.1 -p $Port" -w start
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}
$env:PGPASSWORD = [System.IO.File]::ReadAllText($pwfile).Trim()
try {
    $exists = & (Join-Path $PostgresBin 'psql.exe') -h 127.0.0.1 -p $Port -U sitrap -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='sitrap'"
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    if ($exists -ne '1') {
        & (Join-Path $PostgresBin 'createdb.exe') -h 127.0.0.1 -p $Port -U sitrap sitrap
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }
    if (-not (Test-Path (Join-Path $root '.env'))) {
        $secret = 'dev-local-' + [guid]::NewGuid().ToString('N')
        $content = "DEBUG=True`nSECRET_KEY=$secret`nDATABASE_URL=postgres://sitrap:$($env:PGPASSWORD)@127.0.0.1:$Port/sitrap`n"
        [System.IO.File]::WriteAllText((Join-Path $root '.env'), $content)
    }
} finally {
    Remove-Item Env:PGPASSWORD
}
Write-Output "PostgreSQL local listo en 127.0.0.1:$Port. No se modificaron otros clusters."
