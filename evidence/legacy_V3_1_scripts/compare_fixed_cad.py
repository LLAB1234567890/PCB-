from pathlib import Path
import FreeCAD as A,Part,json
F=Path(__file__).resolve().parents[1];B=F/'evidence/baseline_mechanical';M=F/'mechanical';rows=[]
for name in ['PA12_Main_and_pods.step',*[f'Lid_{x}.step' for x in ['OPEN','CLOSE','STOP','ESTOP','SET']]]:
 a=Part.Shape();a.read(str(B/name));b=Part.Shape();b.read(str(M/name))
 dv=a.cut(b).Volume+b.cut(a).Volume
 row={'file':name,'baseline_volume_mm3':a.Volume,'final_volume_mm3':b.Volume,'symmetric_difference_mm3':dv,'baseline_valid':a.isValid(),'final_valid':b.isValid(),'solid_counts':[len(a.Solids),len(b.Solids)],'bounding_box_delta_mm':max(abs(getattr(a.BoundBox,k)-getattr(b.BoundBox,k)) for k in ['XMin','XMax','YMin','YMax','ZMin','ZMax'])};rows.append(row)
 assert row['baseline_valid'] and row['final_valid'] and dv<1e-5 and row['bounding_box_delta_mm']<1e-6,row
out={'fixed_case_and_button_pods_and_supports_unchanged':True,'method':'OpenCASCADE STEP solid subtraction both directions, volumes/bounds/solids; semantic geometry comparison rather than timestamp-bearing STEP file hashes. All dimensions mm.','objects':rows,'source_pcb_sha256':json.loads((M/'geometry_validation.json').read_text(encoding='utf8'))['source_pcb_sha256']}
(F/'validation/CAD_fixed_geometry_parity.json').write_text(json.dumps(out,indent=2),encoding='utf8');print('Protected CAD geometry parity PASS',len(rows),'STEP solids')
