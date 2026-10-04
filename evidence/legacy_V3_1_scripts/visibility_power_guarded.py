from pathlib import Path
import json,math,sys,heapq,collections,time
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
V=Path(sys.argv[1]);job=json.loads(Path(sys.argv[2]).read_text(encoding='utf8'));out=Path(sys.argv[3]);D=json.loads((V/'copper_geometry.json').read_text(encoding='utf8'));M=json.loads((V/'placement_geometry.json').read_text(encoding='utf8'))
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=32) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=64)
F=[(f,shape(f)) for f in D['features']];P={p['ref']+'.'+q['pin']:q for p in D['parts'] for q in p['pads'] if q['net']};outline=Polygon(job['outline']);patch=[];removed=[];logs=[]
critical=unary_union([LineString([f['a'],f['b']]) for f,g in F if f['kind']=='track' and f['net'] in job['guard_nets']]).buffer(job['guard_radius_mm'])
guard={s:unary_union([g for f,g in F if f['net']=='GND' and f['side']==s]).intersection(critical) for s in ['top','bottom']}
for rr in job['routes']:
 net=rr['net'];own=[f for f,g in F if f['net']==net and f['kind'] in ['track','circle']];remove=list({f['key'] for f in own});removed+=remove
 obs={s:[(f,g) for f,g in F if f['side']==s and f['net']!=net and (not f['key'].startswith('zone:') or f['net'].startswith('CASE'))] for s in ['top','bottom']};trees={s:STRtree([g for f,g in obs[s]]) for s in obs};forbidden={s:[Polygon(q['pts']) for q in M['keepouts'] if s in q['layers'] and q['tracks']]+[box(88,64,194,138).difference(outline.buffer(-.5001))] for s in obs}
 pos=set()
 for f in own:
  if f['kind']=='track':pos.update([tuple(f['a']),tuple(f['b'])])
  else:pos.add(tuple(f['xy']))
 for k in [rr['from'],rr['to']]:pos.add(tuple(P[k]['xy']))
 pos=sorted(pos);N=len(pos);edges=collections.defaultdict(list);orig=[]
 # Existing legal edges form a recoverable fallback. Their widths may be increased
 # only after new exact geometry tests; existing side contacts remain copper contacts.
 existing_bridge={tuple(f['xy']) for f in own if f['kind']=='circle'}|{tuple(P[k]['xy']) for k in [rr['from'],rr['to']] if len(P[k]['sides'])==2}
 idx={a:i for i,a in enumerate(pos)}
 def maxwidth(a,b,s):
  line=LineString([a,b]);closest=2
  for i in trees[s].query(line.buffer(.8)):
   f,g=obs[s][int(i)];closest=min(closest,line.distance(g))
  for g in forbidden[s]:closest=min(closest,line.distance(g))
  # Keep critical baseline GND and its0.25mm zone clearance, without freezing all GND.
  closest=min(closest,line.distance(guard[s])-.05)
  return next((w for w in [1.,.9,.8,.6,.5,.4,.3,.25,.2] if closest-w/2>=.201),None)
 def segments(a,b,s):
  L=math.dist(a,b);steps=max(1,math.ceil(L/1.5));pp=[tuple(round(a[k]+(b[k]-a[k])*i/steps,6) for k in [0,1]) for i in range(steps+1)];rows=[]
  for aa,bb in zip(pp,pp[1:]):
   w=maxwidth(aa,bb,s)
   if w is None:return None
   if rows and rows[-1]['width']==w:rows[-1]['b']=list(bb)
   else:rows.append({'type':'segment','net':net,'side':s,'width':w,'a':list(aa),'b':list(bb)})
  return rows
 def cost(rows):return sum(.01724*math.dist(a['a'],a['b'])/1000/(a['width']*.035) for a in rows)
 def add(i,j,s,rows,label):
  if not rows:return
  aa=i+N*(s=='bottom');bb=j+N*(s=='bottom');cc=cost(rows);edges[aa].append((bb,cc,rows,label));edges[bb].append((aa,cc,[r|{'a':r['b'],'b':r['a']} for r in rows[::-1]],label))
 for f in own:
  if f['kind']!='track':continue
  rows=segments(f['a'],f['b'],f['side'])
  if rows is None:rows=[{'type':'segment','net':net,'side':f['side'],'width':f['width'],'a':f['a'],'b':f['b'],'original_uuid':f['key']}]
  add(idx[tuple(f['a'])],idx[tuple(f['b'])],f['side'],rows,'existing geometry')
 # Join old overlapping/T contacts. The overlap is an existing metal contact and
 # does not create a new shortcut through foreign copper.
 for s in ['top','bottom']:
  gg=[(f,shape(f)) for f in own if f['side']==s];tr=STRtree([g for f,g in gg])
  for i,pt in enumerate(pos):
   gpt=Point(pt)
   for k in tr.query(gpt.buffer(.001)):
    f,g=gg[int(k)]
    if g.distance(gpt)>.001:continue
    if f['kind']=='track':
     for ep in [f['a'],f['b']]:
      j=idx[tuple(ep)]
      if i==j:continue
      rows=segments(pt,ep,s)
      if rows:add(i,j,s,rows,'existing side contact')
 for i,a in enumerate(pos):
  if a in existing_bridge:
   via=next((f for f in own if f['kind']=='circle' and tuple(f['xy'])==a),None)
   row=[{'type':'via','net':net,'xy':list(a),'diameter':2*via['radius'],'drill':2*via['drill_radius']}] if via else []
   edges[i].append((i+N,.001,row,'existing plated bridge'));edges[i+N].append((i,.001,row,'existing plated bridge'))
  for j in range(i+1,N):
   b=pos[j];dx,dy=b[0]-a[0],b[1]-a[1];adx,ady=abs(dx),abs(dy)
   # H/V/45 routes have two canonical elbow choices. No arbitrary-angle new trunk.
   pts=[]
   if min(adx,ady)<1e-7 or abs(adx-ady)<1e-7:pts=[None]
   elif adx>ady:pts=[(a[0]+math.copysign(ady,dx),b[1]),(b[0]-math.copysign(ady,dx),a[1])]
   else:pts=[(b[0],a[1]+math.copysign(adx,dy)),(a[0],b[1]-math.copysign(adx,dy))]
   for s in ['top','bottom']:
    best=None
    for m in pts:
     rows=segments(a,b,s) if m is None else (segments(a,m,s) or [])+(segments(m,b,s) or [])
     if m is not None and (not rows or rows[0]['a']!=list(a) or rows[-1]['b']!=list(b) or any(rows[k]['b']!=rows[k+1]['a'] for k in range(len(rows)-1))):continue
     if rows and (best is None or cost(rows)<cost(best)):best=rows
    if best:add(i,j,s,best,'octilinear shortcut/widened trunk')
 start=idx[tuple(P[rr['from']]['xy'])];end=idx[tuple(P[rr['to']]['xy'])];goals={end+N*(s=='bottom') for s in P[rr['to']]['sides']};q=[];dist={};prev={}
 for s in P[rr['from']]['sides']:ii=start+N*(s=='bottom');dist[ii]=0;heapq.heappush(q,(0,ii))
 while q:
  cc,i=heapq.heappop(q)
  if cc!=dist[i]:continue
  if i in goals:break
  for j,r,rows,label in edges[i]:
   value=cc+r
   if value<dist.get(j,1e10):dist[j]=value;prev[j]=(i,rows,label);heapq.heappush(q,(value,j))
 else:raise RuntimeError((net,'Visibility graph lost original fallback'))
 steps=[];v=i
 while v in prev:vv,rows,label=prev[v];steps.append((rows,label));v=vv
 rows=[a for pp,label in steps[::-1] for a in pp];used=[];seen=set()
 for a in rows:
  if a['type']=='via':
   k=tuple(a['xy'])
   if k in seen:continue
   seen.add(k)
  used.append(a)
 patch+=used;logs.append({'net':net,'from':rr['from'],'to':rr['to'],'trace_mm':sum(math.dist(a['a'],a['b']) for a in used if a['type']=='segment'),'resistance_20C':dist[i],'segments':sum(a['type']=='segment' for a in used),'vias':sum(a['type']=='via' for a in used),'edges_selected':[label for rows,label in steps[::-1]]})
 print(logs[-1],flush=True)
out.write_text(json.dumps({'remove':list(set(removed)),'items':patch,'routes':logs,'method':'Existing pad/via/track junctions with visibility shortcuts; same-net side contacts explicitly retained; octilinear new trunks; width selected per local exact immutable-copper clearance'},indent=2),encoding='utf8')
