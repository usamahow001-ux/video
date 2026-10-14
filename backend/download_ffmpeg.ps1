$ProgressPreference = 'SilentlyContinue'
$url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
$output = Join-Path (Get-Location) 'ffmpeg.zip'
Write-Host "Downloading FFmpeg from gyan.dev..."
Write-Host "Saving to: $output"
Invoke-WebRequest -Uri $url -OutFile $output -UseBasicParsing
Write-Host "Download complete!"
