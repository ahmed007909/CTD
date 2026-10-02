$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn news_engine.api:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers --limit-concurrency 32 --backlog 64 --timeout-keep-alive 5 --ws-max-size 4096 --ws-max-queue 4
