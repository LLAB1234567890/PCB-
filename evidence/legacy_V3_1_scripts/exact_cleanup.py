from pathlib import Path
import sys,json,math,collections
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union
from shapely.strtree import STRtree
V=Path(sys.argv[1]);O=Path(sys.argv[2]);D=json.loads((V/'copper_geometry.json').read_text(encoding='utf8'));F=D['features']
keep=set(r['old_uuid'] for r in json.loads(Path(sys.argv[3]).read_text(encoding='utf8'))['records']) if len(sys.argv)>3 else set()
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=64) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=64).difference(Point(f['xy']).buffer(f['drill_radius'],quad_segs=64))
G=[shape(f) for f in F];remove=[];items=[];records=[];removed_indices=set()
# A conductor strictly inside other explicit same-net metal can be removed
# without changing the copper union. Filled zones are deliberately excluded.
group=collections.defaultdict(list)
for i,f in enumerate(F):
 if not f['key'].startswith('zone:'):group[(f['net'],f['side'])].append(i)
for key,ii in group.items():
 tree=STRtree([G[i] for i in ii])
 for i in sorted([i for i in ii if F[i]['kind']=='track'],key=lambda i:G[i].area):
  if F[i]['key'] in keep:continue
  neighbors=[ii[int(k)] for k in tree.query(G[i]) if ii[int(k)]!=i and ii[int(k)] not in removed_indices]
  cover=unary_union([G[k] for k in neighbors])
  if cover.buffer(-.002).covers(G[i]):
   remove.append(F[i]['key']);removed_indices.add(i);records.append({'action':'remove_explicitly_covered_redundancy','old_uuids':[F[i]['key']],'net':F[i]['net'],'side':F[i]['side'],'coverage_proof':'entire track capsule inside other explicit same-net copper with2um inward margin; zones not used','covering_keys':[F[k]['key'] for k in neighbors]})
# Exact integer collinearity/interval union; this preserves mid-segment T
# connections, pads and via contacts, even when their old split vertex disappears.
lines=collections.defaultdict(list)
for i,f in enumerate(F):
 if f['kind']!='track' or i in removed_indices:continue
 a=tuple(round(v*1e6) for v in f['a']);b=tuple(round(v*1e6) for v in f['b']);dx,dy=b[0]-a[0],b[1]-a[1];gg=math.gcd(abs(dx),abs(dy))
 if not gg:continue
 dx//=gg;dy//=gg
 if dx<0 or dx==0 and dy<0:dx,dy=-dx,-dy
 c=dx*a[1]-dy*a[0];u=dx*a[0]+dy*a[1];v=dx*b[0]+dy*b[1]
 if u>v:u,v=v,u;a,b=b,a
 lines[(f['net'],f['side'],round(f['width']*1e6),dx,dy,c)].append((u,v,a,b,i))
for (net,side,width,dx,dy,c),rows in lines.items():
 rows.sort();blocks=[];start=0
 while start<len(rows):
  u,v,a,b,i=rows[start];members=[i];j=start+1
  while j<len(rows) and rows[j][0]<=v:
   uu,vv,aa,bb,k=rows[j];members.append(k)
   if vv>v:v,b=vv,bb
   j+=1
  if len(members)>1:
   uu=[F[k]['key'] for k in members];remove+=uu
   item={'type':'segment','net':net,'side':side,'width':width/1e6,'a':[x/1e6 for x in a],'b':[x/1e6 for x in b]};items.append(item)
   records.append({'action':'exact_collinear_coverage_union','old_uuids':uu,'net':net,'side':side,'new_geometry':item,'branch_proof':'Integer collinearity and interval union exactly preserve line coverage and width. No branch is represented only by a deleted endpoint.'})
  start=j
O.write_text(json.dumps({'remove':remove,'items':items,'records':records,'method':'Explicit copper containment and exact integer collinear interval union. No layer/name/value/pad/via changes.'},ensure_ascii=False,indent=2),encoding='utf8')
print('Exact cleanup',len(records),'actions,',len(remove),'removed,',len(items),'new segments')
