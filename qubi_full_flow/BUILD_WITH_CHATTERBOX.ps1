param([switch]$Build)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

foreach ($tool in @('ffmpeg', 'ffprobe')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Missing $tool. Install FFmpeg before running the build."
    }
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    $basePython = 'py'
    $baseArgs = @('-3.12')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $basePython = 'python'
    $baseArgs = @()
} else {
    throw 'Python 3.12.10 is required and was not found.'
}
$version = & $basePython @baseArgs -c 'import sys; print(sys.version.split()[0])'
if ($LASTEXITCODE -ne 0 -or $version -ne '3.12.10') {
    throw "This build uses Python 3.12.10; found $version. Check the Python installation or PATH."
}

if (-not (Test-Path '.venv312/Scripts/python.exe')) {
    & $basePython @baseArgs -m venv .venv312
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python 3.12 environment.' }
}
$py = Join-Path $PSScriptRoot '.venv312/Scripts/python.exe'
$savedErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $py -c 'import chatterbox, PIL' 2>$null
$importExitCode = $LASTEXITCODE
$ErrorActionPreference = $savedErrorActionPreference
if ($importExitCode -ne 0) {
    # resemble-perth 1.0.1 still imports pkg_resources, removed in newer setuptools.
    & $py -m pip install 'setuptools==80.9.0' chatterbox-tts Pillow
    if ($LASTEXITCODE -ne 0) { throw 'Cannot install Chatterbox; check internet access and Python version.' }
}

if (-not $Build) {
    & $py build_episode_chatterbox.py --sample
    if ($LASTEXITCODE -ne 0) { throw 'Voice sample failed.' }
    Write-Host 'Listen to chatterbox_cache/takes/greeting.wav. If this voice suits Qubi, run: .\BUILD_WITH_CHATTERBOX.ps1 -Build'
    exit 0
}

& $py render_extra_questions_v8.py
if ($LASTEXITCODE -ne 0) { throw 'Question rendering failed.' }
& $py -c 'import build_episode_v8; build_episode_v8.visuals()'
if ($LASTEXITCODE -ne 0) { throw 'Episode visual rendering failed.' }
& $py build_episode_chatterbox.py --build
if ($LASTEXITCODE -ne 0) { throw 'Audio build failed. Inspect chatterbox_cache/timing_report.json.' }
Write-Host 'Final video:' (Join-Path (Split-Path $PSScriptRoot -Parent) 'Qubi_Episode_01_Seven_Questions_Chatterbox.mp4')
