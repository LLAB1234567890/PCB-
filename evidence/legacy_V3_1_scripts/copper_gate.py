from pathlib import Path
import json,collections,sys,math
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.affinity import rotate
V=Path(sys.argv[1]);D=json.loads((V/'copper_geometry.json').read_text(encoding='utf8'));F=D['features']
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=32) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=64).difference(Point(f['xy']).buffer(f['drill_radius'],quad_segs=64))
G=[shape(f) for f in F];parent=list(range(len(F)));bykey=collections.defaultdict(list)
for i,f in enumerate(F):bykey[f['key']].append(i)
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
def join(a,b):parent[root(b)]=root(a)
for key in D['plated_bridges']:
 ii=bykey[key]
 for i in ii[1:]:join(ii[0],i)
shorts=[];tol=1e-6
for side in ['top','bottom']:
 ids=[i for i,f in enumerate(F) if f['side']==side];tree=STRtree([G[i] for i in ids])
 for a,i in enumerate(ids):
  for kk in tree.query(G[i].buffer(tol)):
   j=ids[int(kk)]
   if j<=i or G[i].distance(G[j])>tol:continue
   if F[i]['net']==F[j]['net']:join(i,j)
   else:shorts.append({'a':F[i]['key'],'b':F[j]['key'],'net_a':F[i]['net'],'net_b':F[j]['net'],'side':side,'distance_mm':G[i].distance(G[j])})
netpads=collections.defaultdict(set)
for p in D['parts']:
 for q in p['pads']:
  if q['net'] and not q['net'].startswith('unconnected-'):netpads[q['net']].add(p['ref']+'.'+q['pin'])
opens=[]
for net,keys in netpads.items():
 group=collections.defaultdict(list)
 for key in keys:
  rr={root(i) for i in bykey[key]}
  if len(rr)!=1:opens.append({'net':net,'within_pad':key,'roots':list(rr)})
  for r in rr:group[r].append(key)
 if len(group)>1:opens.append({'net':net,'groups':list(group.values())})
def drill(q):
 dx,dy=q['drill'];x,y=q['xy'];off=[(dx-dy)/2,0] if dx>=dy else [0,(dy-dx)/2]
 return rotate(LineString([(x-off[0],y-off[1]),(x+off[0],y+off[1])]).buffer(min(dx,dy)/2,quad_segs=64),-q['angle'],origin=q['xy'])
areas={};floating={};root_summary={}
for net,anchor in [('GND','J1.2'),('CASE_U1','U1.4'),('CASE_U11','U11.4'),('CASE_U33','U33.4')]:
 rr=root(bykey[anchor][0]);areas[net]={};floating[net]={};root_summary[net]={'anchor':anchor,'anchored_pads':[k for k in netpads[net] if all(root(i)==rr for i in bykey[k])]}
 holes=unary_union([drill(q) for p in D['parts'] for q in p['pads'] if max(q['drill'])>0]+[Point(f['xy']).buffer(f['drill_radius'],quad_segs=64) for f in F if f['kind']=='circle' and f['side']=='top'])
 for side in ['top','bottom']:
  main=unary_union([G[i] for i,f in enumerate(F) if f['net']==net and f['side']==side and root(i)==rr]).difference(holes)
  floats=unary_union([G[i] for i,f in enumerate(F) if f['net']==net and f['side']==side and root(i)!=rr]).difference(holes)
  areas[net][side]=main.area;floating[net][side]=floats.area
all_orphans=[]
for i,f in enumerate(F):
 if f['kind'] not in ['track','circle']:continue
 if not any(root(j)==root(i) for k in netpads.get(f['net'],[]) for j in bykey[k]):all_orphans.append({'key':f['key'],'net':f['net'],'side':f['side']})
out={'source_pcb_sha256':D['source_pcb_sha256'],'join_tolerance_mm':tol,'pad_polygon_max_error_mm':.001,'method':'Independent Shapely track capsules / actual native pad and fill polygons, explicit plated bridges. 1nm join tolerance. Area counts only anchor-connected copper, with every drill/slot removed. Native DRC supplies separate exact rule-engine evidence.','shorts':shorts,'opens':opens,'required_unique_pad_count':sum(map(len,netpads.values())),'anchored_area_mm2':areas,'floating_area_mm2':floating,'anchors':root_summary,'orphan_conductors':all_orphans}
(V/'copper_gate.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:out[k] for k in ['source_pcb_sha256','shorts','opens','anchored_area_mm2','floating_area_mm2']},ensure_ascii=False));assert not shorts and not opens
