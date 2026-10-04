"""Replay the accepted changes into a NEW explicitly named directory, never the project."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess,sys,collections
from sx import parse,dump
F=Path(__file__).resolve().parents[1];a=argparse.ArgumentParser();a.add_argument('--output',required=True);a=a.parse_args();out=Path(a.output).resolve()
assert not out.exists(),'Choose a new directory; no existing project is overwritten.'
assert not out.is_relative_to((F/'project').resolve())
source=F/'evidence/baseline_project/CurtainDrive_V3.kicad_pcb';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source)=='46f10d5db1eadab9c5d524b781945b204c26d077fb969e462897530ded63045b'
out.mkdir(parents=True);pcb=out/source.name;shutil.copy2(source,pcb);steps=[]
for row in json.loads((F/'evidence/accepted_sequence.json').read_text(encoding='utf8')):
 d=json.loads((F/'evidence/accepted_patches'/row['file']).read_text(encoding='utf8'));patch={'remove':[r['uuid'] for r in d['removed']],'items':d['added'],'placements':d.get('placements',{}),'silk_refs':d.get('silk_refs',{}),'zone_outlines':d.get('zone_outlines',{}),'zones_add':d.get('zones_added',[])}
 pf=out/row['file'].replace('.applied.json','.replay.json');pf.write_text(json.dumps(patch,indent=2),encoding='utf8')
 with (out/(pf.stem+'.log')).open('w',encoding='utf8') as log:subprocess.run([sys.executable,str(F/'scripts/board_ops.py'),str(pcb),str(pf)],check=True,stdout=log,stderr=log)
 steps.append({'accepted_log':row['file'],'replay_sha256':sha(pcb),'historical_saved_sha256':row['after'],'note':'Intermediate line endings may differ because deterministic UUID text substitution uses platform-native newlines; final versioned file is compared byte-for-byte.'})
s=pcb.read_text(encoding='utf8').replace('CurtainDrive_V3','CurtainDrive_V3_2_2L').replace('CurtainDriveV3','CurtainDriveV3_2_2L').replace('(rev "V2.3")','(rev "V3.1")')
s=s.replace('(property "DESIGN_REVISION" "V2.3")','(property "DESIGN_REVISION" "V3.1")').replace('(date "2026-10-02")','(date "2026-10-03")')
def chunks(s):
 depth=0;quote=False;escape=False;start=None;out=[]
 for i,c in enumerate(s):
  if quote:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c=='"':quote=False
   continue
  if c=='"':quote=True;continue
  if c=='(':
   depth+=1
   if depth==2:start=i
  elif c==')':
   if depth==2:out.append(s[start:i+1])
   depth-=1
 return out
# Native SaveBoard sorts newly created objects by temporary UUID before the
# deterministic UUID substitution. Preserve the frozen object's serialization
# order using checksums only; this manifest contains no geometry or source text.
pool=collections.defaultdict(list)
for chunk in chunks(s):pool[hashlib.sha256(dump(parse(chunk)).encode('utf8')).hexdigest()].append(chunk)
order=json.loads((F/'evidence/native_serialization_order.json').read_text(encoding='utf8'))['top_level_object_semantic_sha256']
reordered=[]
for key in order:reordered.append(pool[key].pop())
assert not any(pool.values()),'Unexpected geometry or metadata object'
s='(kicad_pcb\n'+''.join('\t'+q+'\n' for q in reordered)+')\n'
final=out/'CurtainDrive_V3_2_2L.kicad_pcb';final.write_text(s,encoding='utf8');expected=sha(F/'project/CurtainDrive_V3_2_2L.kicad_pcb')
result={'source_baseline_sha256':sha(source),'final_expected_sha256':expected,'replay_final_sha256':sha(final),'byte_identical_final':sha(final)==expected,'steps':steps,'output':str(out),'ordering_manifest':'Object semantic hashes only, preserving SaveBoard UUID ordering; no final geometry copied into replay.'}
(out/'replay_validation.json').write_text(json.dumps(result,indent=2),encoding='utf8');assert result['byte_identical_final'],result
print('Accepted sequence replay final byte-for-byte PASS',expected)
