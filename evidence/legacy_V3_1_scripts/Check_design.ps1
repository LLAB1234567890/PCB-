param([string]$KiCadCLI='C:\KiCad\bin\kicad-cli.exe')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskChecks=Join-Path $taskRoot 'validation/recheck'
New-Item -ItemType Directory -Force -Path $taskChecks | Out-Null
& $KiCadCLI sch erc --format json --output (Join-Path $taskChecks 'ERC.json') (Join-Path $taskRoot 'project/CurtainDrive_V3_1.kicad_sch')
if ($LASTEXITCODE -ne 0) { throw 'ERC command failed' }
& $KiCadCLI pcb drc --format json --schematic-parity --output (Join-Path $taskChecks 'DRC.json') (Join-Path $taskRoot 'project/CurtainDrive_V3_1.kicad_pcb')
if ($LASTEXITCODE -ne 0) { throw 'DRC command failed' }
$taskERC=Get-Content -LiteralPath (Join-Path $taskChecks 'ERC.json') -Raw | ConvertFrom-Json
$taskDRC=Get-Content -LiteralPath (Join-Path $taskChecks 'DRC.json') -Raw | ConvertFrom-Json
$taskERCCount=(@($taskERC.sheets | ForEach-Object { $_.violations }) | Where-Object { $null -ne $_ }).Count
if ($taskERCCount -ne 0 -or @($taskDRC.violations).Count -ne 0 -or @($taskDRC.unconnected_items).Count -ne 0 -or @($taskDRC.schematic_parity).Count -ne 0) { throw 'Native rule/parity findings exist; inspect JSON. Command success does not mean zero findings.' }
Write-Output 'Native configured ERC, DRC, unconnected and schematic parity findings are zero. Product and physical acceptance are separate.'
