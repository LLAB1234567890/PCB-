"""Build and verify a fabrication ZIP from final source-parsed manufacturing files."""
from pathlib import Path
import json,hashlib,zipfile,datetime
F=Path(__file__).resolve().parents[1];G=F/'manufacturing/Gerber';V=F/'validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
c=json.loads((V/'CONSISTENCY_R2_manufacturing.json').read_text(encoding='utf8'))
assert c['source_pcb_sha256']==sha(F/'project/CurtainDrive_V3_2_2L.kicad_pcb') and not c['issues']
extensions={'.gtl','.gbl','.gts','.gbs','.gto','.gbo','.gtp','.gbp','.gm1','.drl','.gbrjob'}
files=sorted(p for p in G.iterdir() if p.is_file() and p.suffix.lower() in extensions)
assert len(files)==12 and sum(p.suffix=='.drl' for p in files)==2
assert all(c['file_sha256'][p.name]==sha(p) for p in files)
target=F/'manufacturing/CurtainDrive_V3_2_2L_Gerber.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in files:z.write(p,p.name)
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None and sorted(z.namelist())==sorted(p.name for p in files)
 assert all(hashlib.sha256(z.read(p.name)).hexdigest()==sha(p) for p in files)
proof={'source_pcb_sha256':c['source_pcb_sha256'],'zip_sha256':sha(target),'members':{p.name:sha(p) for p in files},'CRC':True,'member_byte_hashes_equal_source':True,'generated_local':datetime.datetime.now().isoformat(timespec='seconds')}
(V/'FABRICATION_ZIP_validation.json').write_text(json.dumps(proof,indent=2),encoding='utf8');print('Fabrication ZIP CRC/members/byte-hashes PASS',len(files),'members')
