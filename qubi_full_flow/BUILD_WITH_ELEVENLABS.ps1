$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

foreach ($tool in @('python', 'ffmpeg', 'ffprobe')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Missing $tool. Install Python 3 and FFmpeg, then rerun this script."
    }
}

python -c "import PIL" 2>$null
if ($LASTEXITCODE -ne 0) { python -m pip install Pillow }

$secureKey = Read-Host 'ElevenLabs API key' -AsSecureString
$plainKey = [System.Net.NetworkCredential]::new('', $secureKey).Password
try {
    $env:ELEVENLABS_API_KEY = $plainKey
    $env:QUBI_PREVIEW_NO_NEW_VOICE = '0'
    python render_extra_questions_v8.py
    if ($LASTEXITCODE -ne 0) { throw 'Question render failed.' }
    python build_episode_v8.py
    if ($LASTEXITCODE -ne 0) { throw 'Video build failed; inspect elevenlabs_cache/v8_extra/timing_report.json.' }
    Write-Host 'Final video: ' (Join-Path (Split-Path $PSScriptRoot -Parent) 'Qubi_Episode_01_Seven_Questions_Final.mp4')
}
finally {
    Remove-Item Env:ELEVENLABS_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:QUBI_PREVIEW_NO_NEW_VOICE -ErrorAction SilentlyContinue
    $plainKey = $null
    $secureKey = $null
}
