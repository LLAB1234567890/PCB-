"""Close a frozen package, mirror into two NEW folders, verify ZIP by extraction."""
from pathlib import Path
import argparse,json,hashlib,shutil,zipfile,tempfile,datetime
F=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('--primary',default=r'A:\备份KidCad_10_2-14-10\CurtainDrive_V3_2_2L');a.add_argument('--backup',default=r'C:\Users\AAA\Documents\Codex\2026-09-30\eda\outputs\CurtainDrive_V3_2_2L');args=a.parse_args()
targets=[Path(args.primary).resolve(),Path(args.backup).resolve()]
assert targets[0]!=targets[1] and all(t.name=='CurtainDrive_V3_2_2L' and not t.exists() for t in targets),'Both named target folders must be NEW; existing work is never replaced.'
assert all(not t.is_relative_to(F) and not F.is_relative_to(t) for t in targets)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024):h.update(b)
 return h.hexdigest()
def inventory(root):return {p.relative_to(root).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file()}
now=datetime.datetime.now().isoformat(timespec='seconds');closure=json.loads((F/'validation/OFFLINE_RELEASE_ACCEPTANCE.json').read_text(encoding='utf8'))
assert closure['physical_acceptance']=='NOT_EXECUTED' and closure['state']=='OFFLINE_ENGINEERING_AND_MANUFACTURING_REVIEW_COMPLETE_WITH_RECORDED_LIMITS'
for name,digest in closure['dependency_sha256'].items():assert sha(F/name)==digest,('Source dependency changed after offline closure',name)
assert not list(F.rglob('__pycache__')) and not list(F.rglob('*.FCBak')) and not list((F/'project').glob('*.kicad_prl'))
# Independently recheck full original intake and the separate recoverable backup.
original=json.loads((F/'evidence/baseline_manifest.json').read_text(encoding='utf8'));src=Path(original['source']);saved=Path(original['backup'])
record0=inventory(src);record1=inventory(saved)
session_only=lambda name: name.endswith('.kicad_prl') or (Path(name).name.startswith('~') and name.endswith('.lck'))
saved_source={name:value for name,value in record0.items() if not session_only(name)}
initial_saved={name:value for name,value in original['files'].items() if not session_only(name)}
assert saved_source==initial_saved and record1==original['files'],'Saved engineering source or its complete backup changed; resolve provenance before delivery.'
session_changes={name:{'initial':original['files'].get(name),'current':record0.get(name)} for name in original['files'].keys()|record0.keys() if original['files'].get(name)!=record0.get(name)}
assert all(session_only(name) for name in session_changes)
backproof={'source_directory':str(src),'backup_directory':str(saved),'original_backup_files':len(record1),'current_source_files':len(record0),'original_backup_bytes':sum(x['bytes'] for x in record1.values()),'complete_backup_all_file_hashes_equal_original_manifest':True,'all_saved_engineering_source_files_equal_original_manifest':True,'KiCad_session_only_differences':session_changes,'session_note':'Only KiCad UI state / volatile editor lock may differ. Never overwrite the current editor session or mistake these changes for PCB/schematic modifications.'}
records=inventory(F);records.pop('file_manifest.json',None)
manifest={'revision':'V3.1','generated_local':now,'source_pcb_sha256':closure['source_pcb_sha256'],'files':records,'excluded_self':'file_manifest.json; a manifest cannot include its own hash.'}
(F/'file_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');records=inventory(F)
for t in targets:
 t.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(F,t)
 assert inventory(t)==records,('Mirror byte difference',t)
zipname='CurtainDrive_V3_2_2L_完整工程.zip';archives=[t.parent/zipname for t in targets]
assert all(not p.exists() for p in archives),'Existing archive is never overwritten.'
with zipfile.ZipFile(archives[0],'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 for rel in records:z.write(targets[0]/rel,'CurtainDrive_V3_2_2L/'+rel)
shutil.copy2(archives[0],archives[1]);ziphash=sha(archives[0]);assert sha(archives[1])==ziphash
verification_root=Path(tempfile.mkdtemp(prefix='v31_archive_readback_',dir=F.parent)).resolve()
assert verification_root.is_relative_to(F.parent.resolve()) and verification_root.parent==F.parent.resolve()
with zipfile.ZipFile(archives[0]) as z:
 assert z.testzip() is None
 expected={'CurtainDrive_V3_2_2L/'+rel for rel in records};assert set(z.namelist())==expected and len(z.infolist())==len(expected)
 for name in z.namelist():
  destination=(verification_root/name).resolve();assert destination.is_relative_to(verification_root) and not Path(name).is_absolute()
 z.extractall(verification_root)
assert inventory(verification_root/'CurtainDrive_V3_2_2L')==records,'Extracted file hashes do not match frozen complete package.'
proof={'revision':'V3.1','generated_local':datetime.datetime.now().isoformat(timespec='seconds'),'state':closure['state'],'physical_acceptance':'NOT_EXECUTED','source_pcb_sha256':closure['source_pcb_sha256'],'source_schematic_sha256':closure['source_schematic_sha256'],'primary_directory':str(targets[0]),'identical_backup_directory':str(targets[1]),'relative_file_hashes_equal':True,'file_count':len(records),'uncompressed_bytes':sum(x['bytes'] for x in records.values()),'package_manifest_sha256':sha(F/'file_manifest.json'),'archives':[str(p) for p in archives],'archive_bytes':archives[0].stat().st_size,'archive_sha256':ziphash,'CRC_PASS':True,'ZIP_exact_member_count':len(records),'ZIP_members_match_closed_package':True,'ZIP_extracted_file_hashes_match':True,'extraction_validation_directory':str(verification_root),'preserved_V3_full_source_and_backup':backproof,'proof_location_reason':'Sibling proof excluded from archive to avoid recursive/self-referential ZIP hashes. Closed package and its manifest are complete.'}
for t in targets:
 q=t.parent/'CurtainDrive_V3_2_2L_delivery_validation.json';assert not q.exists();q.write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(proof,ensure_ascii=False,indent=2))
