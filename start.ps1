param([switch]$LexicalOnly, [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22+ first.' }
uv sync --frozen
if ($LASTEXITCODE) { throw 'Python dependency installation failed.' }
Push-Location frontend
try {
    npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE) { throw 'Frontend dependency installation failed.' }
    npm.cmd run build
    if ($LASTEXITCODE) { throw 'Frontend build failed.' }
} finally { Pop-Location }
if ($LexicalOnly) {
    $env:SEMANTIC_SEARCH = 'false'
    uv run python -m ingestion.cli index --lexical-only
} else {
    $env:SEMANTIC_SEARCH = 'true'
    uv run python -m ingestion.cli index
}
if ($LASTEXITCODE) { throw 'Index preparation failed. Try -LexicalOnly for the fallback demo.' }
Write-Host "Astana Walk: http://127.0.0.1:$Port"
uv run uvicorn backend.main:app --host 127.0.0.1 --port $Port --no-access-log
