param(
 [string]$KiCadCLI='C:\KiCad\bin\kicad-cli.exe',
 [string]$KiCadPython='C:\KiCad\bin\python.exe',
 [string]$AnalysisPython='python',
 [string]$ReportPython='python',
 [string]$FreeCADPython='B:\FreeCAD\bin\python.exe'
)
$ErrorActionPreference='Stop'
$env:PYTHONIOENCODING='utf-8'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskRouting=Join-Path $taskRoot 'validation/routing'
$taskPCB=Join-Path $taskRoot 'project/CurtainDrive_V3_1.kicad_pcb'
$taskSCH=Join-Path $taskRoot 'project/CurtainDrive_V3_1.kicad_sch'
function Invoke-Checked([string]$Executable,[string[]]$TaskArgs) { & $Executable @TaskArgs; if ($LASTEXITCODE -ne 0) { throw "Failed: $Executable $($TaskArgs[0])" } }
Invoke-Checked $KiCadCLI @('sch','export','netlist','--format','kicadxml','--output',(Join-Path $taskRouting 'schematic.net'),$taskSCH)
Invoke-Checked $KiCadCLI @('sch','erc','--format','json','--output',(Join-Path $taskRoot 'validation/SCH_R1_ERC.json'),$taskSCH)
Invoke-Checked $KiCadCLI @('pcb','drc','--format','json','--schematic-parity','--output',(Join-Path $taskRoot 'validation/PCB_R1_DRC.json'),$taskPCB)
Invoke-Checked $KiCadCLI @('sch','export','pdf','--output',(Join-Path $taskRoot 'schematic/CurtainDrive_V3_1.pdf'),$taskSCH)
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'review_erc_categories.py'),'--cli',$KiCadCLI)
Invoke-Checked $KiCadPython @((Join-Path $PSScriptRoot 'inventory.py'),$taskPCB,$taskRouting)
Invoke-Checked $KiCadPython @((Join-Path $PSScriptRoot 'export_copper.py'),$taskPCB,$taskRouting)
Invoke-Checked $KiCadPython @((Join-Path $PSScriptRoot 'export_placement.py'),$taskPCB,$taskRouting)
Invoke-Checked $KiCadPython @((Join-Path $PSScriptRoot 'audit_native.py'),(Join-Path $taskRoot 'project'),$taskRouting)
Invoke-Checked $KiCadPython @((Join-Path $PSScriptRoot 'silk_review.py'))
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'copper_gate.py'),$taskRouting)
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'physical_paths.py'),$taskRouting)
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'fault_model_v31.py'))
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'return_comparison.py'))
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'dc_sheet_model.py'))
& (Join-Path $PSScriptRoot 'REBUILD_models.ps1') -KiCadPython $KiCadPython -AnalysisPython $AnalysisPython -FreeCADPython $FreeCADPython
Invoke-Checked $FreeCADPython @((Join-Path $PSScriptRoot 'compare_fixed_cad.py'))
& (Join-Path $PSScriptRoot 'Rebuild_manufacture.ps1') -KiCadCLI $KiCadCLI -AnalysisPython $AnalysisPython
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'formal_reviews.py'))
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'report_assets.py'))
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'render_final_figures.py'))
Invoke-Checked $AnalysisPython @((Join-Path $PSScriptRoot 'author_report.py'))
Invoke-Checked $ReportPython @((Join-Path $PSScriptRoot 'build_engineering_pdf.py'))
& (Join-Path $PSScriptRoot 'Check_design.ps1') -KiCadCLI $KiCadCLI
Write-Output 'Rebuilt checks/models/manufacturing/report. Render and visually review all four PDFs, refresh PDF QA and production ZIP, then run offline_acceptance.py. This command does not issue a new release or execute physical tests.'
