$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'bridge.py') @args
exit $LASTEXITCODE
