$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONUTF8 = '1'
python work/site_audit.py export --work-dir work --output-dir outputs/shiaarts-research
python work/site_audit.py review-export --work-dir work --output-dir outputs/shiaarts-research
python work/build_artist_skills.py --output outputs/shiaarts-skills
$destination = Join-Path $HOME '.codex\skills'
Copy-Item (Join-Path $root 'outputs\shiaarts-skills\shiaarts-graphic-designer') $destination -Recurse -Force
Get-ChildItem (Join-Path $root 'outputs\shiaarts-skills') -Directory -Filter 'shiaarts-artist-*' | ForEach-Object {
    Copy-Item $_.FullName $destination -Recurse -Force
}
Write-Output 'ShiaArts skills refreshed from the current corpus. Check outputs/shiaarts-research/coverage.json before claiming completion.'
