"""Re-enable every ignored ERC category in a disposable exact project copy."""
from pathlib import Path
import tempfile,json,shutil,subprocess,hashlib,collections,argparse
F=Path(__file__).resolve().parents[1];V=F/'validation';P=F/'project'
a=argparse.ArgumentParser();a.add_argument('--cli',default=r'C:\KiCad\bin\kicad-cli.exe');args=a.parse_args()
scratch=Path(tempfile.mkdtemp(prefix='erc_all_',dir=V)).resolve()
assert scratch.is_relative_to(V.resolve())
try:
 shutil.copytree(P,scratch/'project');pro=scratch/'project/CurtainDrive_V3_2_2L.kicad_pro'
 d=json.loads(pro.read_text(encoding='utf8'));enabled=[]
 for key,val in d['erc']['rule_severities'].items():
  if val=='ignore':d['erc']['rule_severities'][key]='warning';enabled.append(key)
 pro.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
 subprocess.run([args.cli,'sch','erc','--format','json','--output',str(V/'SCH_R1_all_categories_review.json'),str(pro.with_suffix('.kicad_sch'))],check=True)
 data=json.loads((V/'SCH_R1_all_categories_review.json').read_text(encoding='utf8'))
 vv=[q for sheet in data['sheets'] for q in sheet['violations']]
 assert not [q for q in vv if q['severity']=='error'],vv
 assert collections.Counter(q['type'] for q in vv)=={'four_way_junction':10,'single_global_label':21},'Changed drawing findings require renewed individual review.'
 ctx={'source_schematic_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in P.glob('*.kicad_sch')},'reenabled_categories':enabled,'errors':0,'warning_count':len(vv),'unchanged_31_style_warning_family':True}
 (V/'SCH_R1_all_categories_context.json').write_text(json.dumps(ctx,indent=2),encoding='utf8')
 print('All ERC categories: 0 errors;31 individually reviewed style findings.')
finally:
 assert scratch.is_relative_to(V.resolve()) and scratch.parent==V.resolve()
 shutil.rmtree(scratch)
