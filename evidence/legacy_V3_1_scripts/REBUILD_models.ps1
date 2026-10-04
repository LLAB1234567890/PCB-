param([string]$KiCadPython='C:\KiCad\bin\python.exe',[string]$AnalysisPython='python',[string]$FreeCADPython='B:\FreeCAD\bin\python.exe')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
function Invoke-Checked([string]$Executable,[string[]]$TaskArgs) { & $Executable @TaskArgs; if ($LASTEXITCODE -ne 0) { throw "Model command failed: $Executable" } }
Invoke-Checked $KiCadPython @((Join-Path $PSScriptRoot 'export_copper.py'),(Join-Path $taskRoot 'project/CurtainDrive_V3_1.kicad_pcb'),(Join-Path $taskRoot 'validation/routing'))
Invoke-Checked $KiCadPython @((Join-Path $PSScriptRoot 'export_model_geometry.py'))
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'bare_support_fixed.py'))
Invoke-Checked $FreeCADPython @((Join-Path $PSScriptRoot 'build_v3_enclosure.py'))
Invoke-Checked $FreeCADPython @((Join-Path $PSScriptRoot 'validate_cad_exports.py'))
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'run_thermal_v3.py'),(Join-Path $taskRoot 'thermal'))
Write-Output 'Models rebuilt. Refresh electrical, manufacturing, visual and source-hash validation for this version.'
