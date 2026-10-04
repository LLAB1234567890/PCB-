param([string]$KiCadCLI='C:\KiCad\bin\kicad-cli.exe',[string]$AnalysisPython='python')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskPCB=Join-Path $taskRoot 'project/CurtainDrive_V3_1.kicad_pcb'
$taskOut=Join-Path $taskRoot 'manufacturing/Gerber/'
function Invoke-Checked([string]$Executable,[string[]]$TaskArgs) { & $Executable @TaskArgs; if ($LASTEXITCODE -ne 0) { throw "Command failed: $Executable" } }
Invoke-Checked $KiCadCLI @('pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,B.Paste,Edge.Cuts','--use-drill-file-origin','--disable-aperture-macros','--precision','6','--output',$taskOut,$taskPCB)
Invoke-Checked $KiCadCLI @('pcb','export','drill','--format','excellon','--drill-origin','plot','--excellon-units','mm','--excellon-separate-th','--generate-map','--map-format','pdf','--generate-report','--output',$taskOut,$taskPCB)
Invoke-Checked $KiCadCLI @('pcb','export','pos','--format','csv','--units','mm','--side','both','--use-drill-file-origin','--smd-only','--exclude-fp-th','--exclude-dnp','--output',(Join-Path $taskRoot 'manufacturing/KiCad_SMT_positions.csv'),$taskPCB)
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'manufacturing_verify.py'))
Write-Output 'Gerber/Excellon/BOM/CPL exported and independently parsed against current native copper and netlist. Stock-library pin1/polarity still needs order preview.'
