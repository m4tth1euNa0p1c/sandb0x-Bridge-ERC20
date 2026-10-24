param(
    [ValidateSet('local-fast', 'local-besu')]
    [string]$Profile = 'local-fast',
    [ValidatePattern('^[a-z0-9-]+$')]
    [string]$Name = 'grafana'
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$browserCandidates = @(
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
    'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
)
$browserPath = $browserCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $browserPath) { throw 'Aucun Chrome/Edge local disponible pour la capture.' }
$captureRoot = Join-Path $projectRoot '.local'
$capturePath = Join-Path $captureRoot ($Name + '.png')
if (Test-Path -LiteralPath $capturePath) { throw 'Ce nom de capture existe déjà ; choisir un autre -Name pour préserver la preuve.' }
$profilePath = Join-Path $captureRoot ('visual-browser/' + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $profilePath -Force)
$port = if ($Profile -eq 'local-fast') { 13000 } else { 13001 }
$targetUrl = "http://127.0.0.1:$port/d/t3l4n-bridge"
$arguments = @(
    '--headless=new', '--disable-gpu', '--disable-background-networking', '--disable-sync',
    '--disable-extensions', '--disable-default-apps', '--disable-component-update',
    '--metrics-recording-only', '--no-first-run', '--no-default-browser-check',
    '--disable-features=MediaRouter', '--hide-scrollbars', '--window-size=1440,1900',
    '--virtual-time-budget=20000', "--user-data-dir=$profilePath", "--screenshot=$capturePath", $targetUrl
)
$startedUtc = [DateTime]::UtcNow.ToString('o')
$process = Start-Process -FilePath $browserPath -ArgumentList $arguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $captureRoot ($Name + '-browser.stdout.log')) `
    -RedirectStandardError (Join-Path $captureRoot ($Name + '-browser.stderr.log'))
# Conserver le handle avant l'attente : PowerShell 5 peut sinon perdre ExitCode.
$null = $process.Handle
if (-not $process.WaitForExit(90000)) {
    # Ne termine que le processus exact créé ci-dessus, jamais les navigateurs personnels.
    $process.Kill()
    throw 'Capture headless expirée après 90 secondes.'
}
$process.Refresh()
$report = [ordered]@{
    utc = $startedUtc
    profile = $Profile
    url = $targetUrl
    browser = $browserPath
    browser_version = (Get-Item -LiteralPath $browserPath).VersionInfo.ProductVersion
    isolated_profile = $profilePath
    command_arguments = $arguments
    exit_code = $process.ExitCode
    screenshot = $capturePath
    visual_review = 'À effectuer séparément ; un fichier PNG ne vaut pas inspection.'
}
if (Test-Path -LiteralPath $capturePath) { $report['screenshot_sha256'] = (Get-FileHash -LiteralPath $capturePath -Algorithm SHA256).Hash.ToLowerInvariant() }
$report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $captureRoot ($Name + '-capture.json')) -Encoding UTF8
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $capturePath)) { throw "Le navigateur n'a pas produit de capture valide." }
Write-Output $capturePath
