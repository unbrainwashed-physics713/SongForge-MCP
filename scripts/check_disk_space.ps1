# Checks free space on the drive this repo lives on before starting large
# downloads. This project hit 100% disk usage once already from exactly
# this checkpoint download (28GB) landing on an already-tight drive.
param(
    [int]$RequiredGB = 40
)

$drive = (Get-Item $PSScriptRoot).PSDrive.Name
$freeGB = [math]::Round((Get-PSDrive $drive).Free / 1GB, 1)

Write-Host "Drive $($drive): $freeGB GB free (need ~$RequiredGB GB)"

if ($freeGB -lt $RequiredGB) {
    Write-Host "Not enough free space."
    exit 1
}
exit 0
