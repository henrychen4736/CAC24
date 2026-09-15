# One-command setup for Windows (PowerShell). Finds Python and runs bootstrap.py,
# which checks your tools and sets up the backend and the app.
#
#   .\setup.ps1            set everything up
#   .\setup.ps1 --run      ...then start the server and launch the app
#   .\setup.ps1 --help     all options
#
# If scripts are blocked on your machine, run setup.cmd instead (or double-click it).

Set-Location -Path $PSScriptRoot
$bootstrap = Join-Path $PSScriptRoot 'bootstrap.py'

# 'py' is the official Python launcher; plain 'python' may be the Microsoft Store stub, so test each one.
$candidates = @(@('py', '-3.12'), @('py', '-3.11'), @('py', '-3'), @('python'), @('python3'))
foreach ($candidate in $candidates) {
    $exe = $candidate[0]
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $prefix = @($candidate | Select-Object -Skip 1)
    & $exe @prefix -c 'import sys; sys.exit(sys.version_info < (3, 8))' *> $null
    if ($LASTEXITCODE -eq 0) {
        & $exe @prefix $bootstrap @args
        exit $LASTEXITCODE
    }
}

Write-Host 'Python 3 is required. Install Python 3.12 from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and re-run.' -ForegroundColor Red
exit 1
