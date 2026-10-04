"""Branch-aware octilinear simplification. Every old side contact is an invariant.
No new arbitrary-angle trunks; actual reference geometry is screened before patch.
"""
from pathlib import Path
import sys,json,math,collections
import numpy as np
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from shapely.strtree import STRtree
V=Path(sys.argv[1]);O=Path(sys.argv[2]);selected=set(sys.argv[3].split(',')) if len(sys.argv)>3 else None;D=json.loads((V/'copper_geometry.json').read_text(encoding='utf8'));F=D['features']
M=json.loads((V/'placement_geometry.json').read_text(encoding='utf8'));board=Polygon(D['board_outline']).buffer(-.501);keep={s:[Polygon(q['pts']) for q in M['keepouts'] if q['tracks'] and s in q['layers']] for s in ['top','bottom']}
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=32) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=64)
G=[shape(f) for f in F];trees={s:STRtree([G[i] for i,f in enumerate(F) if f['side']==s and (not f['key'].startswith('zone:') or f['net'].startswith('CASE'))]) for s in ['top','bottom']};ids={s:[i for i,f in enumerate(F) if f['side']==s and (not f['key'].startswith('zone:') or f['net'].startswith('CASE'))] for s in trees}
same={};ground=unary_union([g for f,g in zip(F,G) if f['net']=='GND']);groups=collections.defaultdict(list);new_foreign=[];remove=[];items=[];reports=[];rejected=[]
for i,f in enumerate(F):
 if f['kind']=='track' and f['net'] not in ['GND','CASE_U1','CASE_U11','CASE_U33'] and (selected is None or f['net'] in selected):groups[(f['net'],f['side'],f['width'])].append(i)
def nm(xy):return tuple(round(x*1e6) for x in xy)
def mm(pt):return tuple(x/1e6 for x in pt)
def octo(a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];ax,ay=abs(dx),abs(dy)
 if not dx or not dy or ax==ay:return [[a,b]]
 sx=1 if dx>0 else -1;sy=1 if dy>0 else -1
 if ax>ay:return [[a,(a[0]+sx*ay,b[1]),b],[a,(b[0]-sx*ay,a[1]),b]]
 return [[a,(b[0],a[1]+sy*ax),b],[a,(a[0],b[1]-sy*ax),b]]
def reference_max(g):
 if g.geom_type=='LineString':pp=[]
 else:return 0
 for aa,bb in zip(g.coords,g.coords[1:]):
  L=math.dist(aa,bb);N=max(2,math.ceil(L/.25));pp.extend((aa[0]+(bb[0]-aa[0])*k/N,aa[1]+(bb[1]-aa[1])*k/N) for k in range(N+1))
 return max((ground.distance(Point(p)) for p in pp),default=0)
def clear(poly,net,side):
 if not board.covers(poly) or any(poly.intersects(q) for q in keep[side]):return False
 for k in trees[side].query(poly.buffer(.251)):
  i=ids[side][int(k)];f=F[i]
  if f['net']==net:continue
  margin=.249 if f['net'].startswith('CASE') else .203
  if poly.distance(G[i])<margin:return False
 return not any(n!=net and s==side and poly.distance(g)<.203 for n,s,g in new_foreign)
def keeps_branch_ends(old,new,contacts):
 for k in contacts:
  if F[k]['kind']=='track':
   for pt in [F[k]['a'],F[k]['b']]:
    q=Point(pt)
    if old.buffer(1e-9).covers(q) and not new.buffer(1e-9).covers(q):return False
 return True
for (net,side,width),ii in groups.items():
 nodes=collections.defaultdict(list)
 for i in ii:
  for pt in [F[i]['a'],F[i]['b']]:nodes[nm(pt)].append(i)
 anchor=set();padvia=[i for i,f in enumerate(F) if f['net']==net and f['side']==side and f['kind']!='track' and not f['key'].startswith('zone:')]
 for pt,ee in nodes.items():
  pp=Point(mm(pt))
  if len(ee)!=2 or any(G[i].distance(pp)<=width/2+.001 for i in padvia):anchor.add(pt);continue
  # Geometric side branches are validated over the entire old union below.
  # Nearby consecutive micro-segments must not be mistaken for T branches.
 visited=set()
 for start in sorted(anchor):
  for first in nodes[start]:
   if first in visited:continue
   edges=[];pts=[start];cur=start;edge=first
   while edge not in visited:
    visited.add(edge);edges.append(edge);f=F[edge];a,b=nm(f['a']),nm(f['b']);nxt=b if a==cur else a;pts.append(nxt)
    if nxt in anchor:break
    more=[j for j in nodes[nxt] if j!=edge]
    if not more:break
    cur=nxt;edge=more[0]
   if len(edges)<2:continue
   oldline=LineString([mm(p) for p in pts]);old=unary_union([G[i] for i in edges]);oldlen=oldline.length
   # All same-net conductors touching any point of the old path, including pads,
   # vias, alternate-width tracks and interior T-branches, are frozen contacts.
   contacts=[i for i,f in enumerate(F) if f['side']==side and f['net']==net and i not in edges and not f['key'].startswith('zone:') and old.distance(G[i])<1e-6]
   # Dynamic programming preserves necessary obstacles/contacts while shortening
   # local staircases. Whole-chain straightening alone misses dense-board cleanup.
   count=len(pts);score=[float('inf')]*count;score[0]=0;back={}
   for i in range(count-1):
    if score[i]==float('inf'):continue
    oldedge=math.dist(mm(pts[i]),mm(pts[i+1]));fallback=score[i]+oldedge+.03
    if fallback<score[i+1]:score[i+1]=fallback;back[i+1]=(i,[pts[i],pts[i+1]])
    ends=sorted(set(list(range(i+2,min(count,i+14)))+[count-1]),reverse=True)
    for j in ends:
     if j<=i+1:continue
     oldchunk=LineString([mm(p) for p in pts[i:j+1]]);oldpoly=oldchunk.buffer(width/2,quad_segs=32);oldll=oldchunk.length
     wanted=[k for k in contacts if oldpoly.distance(G[k])<1e-6]
     for proposed in octo(pts[i],pts[j]):
      pl=LineString([mm(p) for p in proposed]);poly=pl.buffer(width/2,quad_segs=32);value=score[i]+pl.length+.03*(len(proposed)-1)
      if value>=score[j]-1e-6 or pl.length>oldll+1e-6:continue
      if not clear(poly,net,side):continue
      lost=[F[k]['key'] for k in wanted if poly.distance(G[k])>1e-6]
      if lost:
       rejected.append({'net':net,'old_uuids':[F[k]['key'] for k in edges[i:j]],'reason':'lost fixed side contact','contacts':lost});continue
      if not keeps_branch_ends(oldpoly,poly,wanted):continue
      if reference_max(pl)>reference_max(oldchunk)+.03:continue
      score[j]=value;back[j]=(i,proposed)
   pp=[];j=count-1
   while j:
    i,path=back[j];pp.append(path);j=i
   points=[]
   for path in pp[::-1]:points+=path if not points else path[1:]
   if points==pts:continue
   pl=LineString([mm(p) for p in points]);poly=pl.buffer(width/2,quad_segs=32);ll=pl.length
   if len(points)-1>=len(edges) and oldlen-ll<1e-6:continue
   # Whole path remains connected and all fixed external contacts are verified again.
   if any(poly.distance(G[k])>1e-6 for k in contacts):continue
   if not keeps_branch_ends(old,poly,contacts):continue
   remove.extend(F[i]['key'] for i in edges)
   new=[{'type':'segment','net':net,'side':side,'width':width,'a':list(mm(a)),'b':list(mm(b))} for a,b in zip(points,points[1:]) if a!=b];items+=new;new_foreign.append((net,side,poly))
   reports.append({'net':net,'side':side,'old_uuids':[F[i]['key'] for i in edges],'old_segments':len(edges),'new_segments':len(new),'before_mm':oldlen,'after_mm':ll,'preserved_side_contacts':[F[i]['key'] for i in contacts],'reference_screen':'no >0.03mm increase in maximum distance to actual GND union; final fill/root check still required'})
O.write_text(json.dumps({'remove':remove,'items':items,'chains':reports,'rejected_side_contact_loss':rejected,'method':'Integer-nanometre H/V/45 alternatives; all old actual copper side contacts retained; width unchanged; foreign copper/CASE and GND reference screening'},ensure_ascii=False,indent=2),encoding='utf8')
print('Branch-safe chains',len(reports),'remove',len(remove),'add',len(items),'mm saved',sum(a['before_mm']-a['after_mm'] for a in reports),'lost-contact alternatives rejected',len(rejected))
