from pathlib import Path
import pcbnew as p, json,sys,hashlib
file=Path(sys.argv[1]);patch=Path(sys.argv[2]);b=p.LoadBoard(str(file));d=json.loads(patch.read_text(encoding='utf8'));ret=[]
xy=lambda a:p.VECTOR2I(*(round(v*1e6) for v in a))
fps={f.GetReference():f for f in b.GetFootprints()}
old={t.m_Uuid.AsString():t for t in b.GetTracks()};nets=b.GetNetsByName();uuid_map={}
log={'before_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'removed':[],'added':[],'placements':d.get('placements',{})}
for uid,pts in d.get('zone_outlines',{}).items():
 z=next(z for z in b.Zones() if z.m_Uuid.AsString()==uid);o=p.SHAPE_POLY_SET();o.NewOutline()
 for x,y in pts:o.Append(round(x*1e6),round(y*1e6))
 z.SetOutline(o);ret.append(o)
log['zone_outlines']=d.get('zone_outlines',{})
log['zones_added']=[]
for a in d.get('zones_add',[]):
 z=p.ZONE(b);z.SetLayer(p.F_Cu if a['side']=='top' else p.B_Cu);z.SetNet(nets[a['net']]);z.SetAssignedPriority(a.get('priority',100));z.SetLocalClearance(round(a.get('clearance',.25)*1e6));z.SetMinThickness(round(a.get('minimum_thickness',.1)*1e6));z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS)
 o=p.SHAPE_POLY_SET();o.NewOutline()
 for x,y in a['outline']:o.Append(round(x*1e6),round(y*1e6))
 z.SetOutline(o);b.Add(z);ret.extend([z,o]);actual_uuid=z.m_Uuid.AsString()
 if a.get('uuid'):uuid_map[actual_uuid]=a['uuid']
 log['zones_added'].append(a|{'uuid':a.get('uuid',actual_uuid)})
for ref,pose in d.get('placements',{}).items():
 f=fps[ref];f.SetPosition(xy(pose[:2]));f.SetOrientationDegrees(pose[2])
for ref,pose in d.get('silk_refs',{}).items():
 f=fps[ref].Reference();f.SetPosition(xy(pose[:2]));f.SetTextAngle(p.EDA_ANGLE(pose[2],p.DEGREES_T))
log['silk_refs']=d.get('silk_refs',{})
for uid in d.get('remove',[]):
 assert uid in old,uid
 t=old[uid];log['removed'].append({'uuid':uid,'net':t.GetNetname()});b.Remove(t);ret.append(t)
for a in d.get('items',[]):
 if a['type']=='segment':
  t=p.PCB_TRACK(b);t.SetStart(xy(a['a']));t.SetEnd(xy(a['b']));t.SetWidth(round(a['width']*1e6));t.SetLayer(p.F_Cu if a['side']=='top' else p.B_Cu)
 else:
  t=p.PCB_VIA(b);t.SetPosition(xy(a['xy']));t.SetWidth(round(a.get('diameter',.6)*1e6));t.SetDrill(round(a.get('drill',.3)*1e6));t.SetViaType(p.VIATYPE_THROUGH);t.SetLayerPair(p.F_Cu,p.B_Cu)
 actual_uuid=t.m_Uuid.AsString()
 if a.get('uuid'):uuid_map[actual_uuid]=a['uuid']
 t.SetNet(nets[a['net']]);b.Add(t);ret.append(t);log['added'].append(a|{'uuid':a.get('uuid',actual_uuid)})
before={t.m_Uuid.AsString():t.GetNetname() for t in b.GetTracks()};b.BuildConnectivity();ok=p.ZONE_FILLER(b).Fill(b.Zones());after={t.m_Uuid.AsString():t.GetNetname() for t in b.GetTracks()}
assert before==after,'Connectivity reassigned a net'
p.SaveBoard(str(file),b)
if uuid_map:
 native=file.read_text(encoding='utf8')
 for old_uuid,new_uuid in uuid_map.items():
  assert native.count(old_uuid)==1 and new_uuid not in native
  native=native.replace(old_uuid,new_uuid)
 file.write_text(native,encoding='utf8')
log.update(after_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),fill_return=bool(ok),net_reassignment=[])
patch.with_suffix('.applied.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf8')
print('Patch saved:',len(log['removed']),'removed,',len(log['added']),'added,',len(log['placements']),'placements')
