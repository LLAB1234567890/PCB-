from pathlib import Path
import json, math, collections, hashlib, heapq,sys
import numpy as np
import re
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from shapely.ops import nearest_points
from shapely import contains_xy
W=Path(sys.argv[1]);O=W
d=json.loads((W/'copper_geometry.json').read_text(encoding='utf8')); parts={p['ref']:p for p in d['parts']}
kinds={}
fs=d['features']; shapes=[]
for f in fs:
 if f['kind']=='polygon': g=Polygon(f['outline'],f['holes']); g=g if g.is_valid else g.buffer(0)
 elif f['kind']=='track': g=LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=16)
 else: g=Point(f['xy']).buffer(f['radius'],quad_segs=32).difference(Point(f['xy']).buffer(f['drill_radius'],quad_segs=32))
 shapes.append(g)
ground={side:unary_union([g for f,g in zip(fs,shapes) if f['net']=='GND' and f['side']==side]) for side in ['top','bottom']}
inventory=[]
for ref,p in sorted(parts.items(),key=lambda kv:re.sub(r'\d+',lambda m:m.group().zfill(4),kv[0])):
 inventory.append({'ref':ref,'value':p['value'],'mpn':p['mpn'],'kind':kinds.get(ref),'xy':[p['x'],p['y']],'pins':{x['pin']:x['net'] for x in p['pads']}})
(W/'functional_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf8')
print('PARTS')
for p in inventory:
 if p['ref'].startswith(('U','Q','F','D')): print(p['ref'],p['value'],p['xy'],p['pins'])
stats=collections.defaultdict(lambda:dict(length_mm=0,via_count=0,min_width_mm=100,opposite_gnd_within_1mm_length_mm=0,max_opposite_gnd_distance_mm=0,raw_opposite_gnd_length_mm=0,any_gnd_within_1mm_length_mm=0,max_any_gnd_distance_mm=0))
for f in fs:
 if f['kind']=='circle':stats[f['net']]['via_count']+=.5;continue
 if f['kind']!='track' or f['net']=='GND':continue
 a,b=np.array(f['a']),np.array(f['b']); L=float(np.linalg.norm(b-a));n=max(2,math.ceil(L/.25));mids=a+(b-a)*(np.arange(n)+.5)[:,None]/n
 g=ground['bottom' if f['side']=='top' else 'top']; ds=np.array([g.distance(Point(v)) for v in mids]);own=np.array([ground[f['side']].distance(Point(v)) for v in mids]);near=np.minimum(ds,own);s=stats[f['net']]
 s['length_mm']+=L;s['min_width_mm']=min(s['min_width_mm'],f['width']);s['raw_opposite_gnd_length_mm']+=float(np.sum(ds<.003))*L/n;s['opposite_gnd_within_1mm_length_mm']+=float(np.sum(ds<=1))*L/n;s['max_opposite_gnd_distance_mm']=max(s['max_opposite_gnd_distance_mm'],float(ds.max()))
 s['any_gnd_within_1mm_length_mm']+=float(np.sum(near<=1))*L/n;s['max_any_gnd_distance_mm']=max(s['max_any_gnd_distance_mm'],float(near.max()))
for n,s in stats.items():
 s['via_count']=int(s['via_count']);s['direct_reference_percent']=round(100*s['raw_opposite_gnd_length_mm']/s['length_mm'],1) if s['length_mm'] else None
 s['near_reference_1mm_percent']=round(100*s['opposite_gnd_within_1mm_length_mm']/s['length_mm'],1) if s['length_mm'] else None
 s['any_reference_1mm_percent']=round(100*s['any_gnd_within_1mm_length_mm']/s['length_mm'],1) if s['length_mm'] else None

# Track/pad/via graph: conservative DC forward resistance, no ground plane sheet model.
def route(net,frompad,topad):
 nodes=[];adj=[];ids={};padids=collections.defaultdict(list)
 def node(xy,side):
  key=(round(xy[0],5),round(xy[1],5),side)
  if key not in ids:ids[key]=len(nodes);nodes.append(key);adj.append([])
  return ids[key]
 def link(a,b,res,L=0):adj[a].append((b,res,L));adj[b].append((a,res,L))
 copper_rho=.01724 # ohm mm^2/m at20C
 for f in fs:
  if f['net']!=net:continue
  if f['kind']=='track':
   L=math.dist(f['a'],f['b']);a=node(f['a'],f['side']);b=node(f['b'],f['side']);link(a,b,copper_rho*L/1000/(f['width']*.035),L)
  elif f['kind']=='circle':node(f['xy'],f['side'])
 for p in parts.values():
  for pad in p['pads']:
   if pad['net']!=net:continue
   pin=p['ref']+'.'+pad['pin'];xy=pad['xy']
   for side in pad['sides']:padids[pin].append(node(xy,side))
   if len(pad['sides'])==2:link(*padids[pin],.001)
 # Split resistance edges at same-layer interior contacts. This includes
 # T junctions and intersecting tracks, which an endpoint-only graph misses.
 segs=[f for f in fs if f['net']==net and f['kind']=='track']
 for p in parts.values():
  for pad in p['pads']:
   if pad['net']!=net:continue
   key=p['ref']+'.'+pad['pin']
   for f,g in zip(fs,shapes):
    if f['key']!=key:continue
    for t in segs:
     if t['side']!=f['side']:continue
     line=LineString([t['a'],t['b']])
     if line.buffer(t['width']/2,quad_segs=16).distance(g)>.003:continue
     xy=line.interpolate(line.project(Point(pad['xy']))).coords[0]
     ni=node(xy,f['side'])
     for pi in padids[key]:
      if nodes[pi][2]==f['side']:link(pi,ni,1e-6)
 for i,f in enumerate(segs):
  line=LineString([f['a'],f['b']])
  for h in segs[i+1:]:
   if h['side']!=f['side']:continue
   other=LineString([h['a'],h['b']])
   if line.distance(other)>(f['width']+h['width'])/2+.002:continue
   pa,pb=nearest_points(line,other)
   na=node(pa.coords[0],f['side']);nb=node(pb.coords[0],h['side']);link(na,nb,1e-6)
 for f in segs:
  line=LineString([f['a'],f['b']]);contacts=[]
  for i,xy in enumerate(nodes):
   if xy[2]!=f['side'] or line.distance(Point(xy[:2]))>f['width']/2+.003:continue
   contacts.append((line.project(Point(xy[:2])),i))
  contacts.sort()
  for (da,a),(db,b) in zip(contacts,contacts[1:]):
   L=abs(db-da);link(a,b,copper_rho*L/1000/(f['width']*.035),L)
 bykey=collections.defaultdict(dict)
 for f,g in zip(fs,shapes):
  if f['net']==net and f['kind']!='track':bykey[f['key']][f['side']]=g
 for key,gg in bykey.items():
  if key.startswith('zone'):continue
  clusters=[]
  for side,g in gg.items():
   cf=next((f for f in fs if f['key']==key and f['side']==side),None)
   here=[i for i,v in enumerate(nodes) if v[2]==side and (g.distance(Point(v[:2]))<.003 or cf and cf['kind']=='circle' and math.dist(cf['xy'],v[:2])<=cf['radius']+.003)]
   # Include geometric centre of annuli/pads, without falsely making traces outside copper contact.
   if key in padids:here+=padids[key]
   if here:
    here=list(set(here));clusters+=here
    for i in here[1:]:link(here[0],i,1e-6)
  if key in d['plated_bridges'] and clusters:
   for i in clusters[1:]:link(clusters[0],i,.001)
 start=padids[frompad];ends=set(padids[topad]);q=[];dist={};prev={}
 for i in start:dist[i]=0;heapq.heappush(q,(0,i))
 while q:
  dd,i=heapq.heappop(q)
  if dd!=dist[i]:continue
  if i in ends:
   walk=[];v=i;L=0
   while v in prev:j,dl=prev[v];L+=dl;walk.append(nodes[v]);v=j
   walk.append(nodes[v]);return {'net':net,'from':frompad,'to':topad,'resistance_ohm_20C_35um':dd,'trace_length_mm':L,'route':walk[::-1]}
  for j,rr,ll in adj[i]:
   nd=dd+rr
   if nd<dist.get(j,float('inf')):dist[j]=nd;prev[j]=(i,ll);heapq.heappush(q,(nd,j))
 return {'net':net,'from':frompad,'to':topad,'error':'track graph incomplete; use copper connectivity proof'}
paths=[]
for net,a,b in [('+24V_IN','J1.1','F1.1'),('+24V_CTRL','D1.1','U1.1'),('+24V_CTRL','D1.1','U11.1'),('+24V_CTRL','D1.1','U33.1'),('+5V_CTRL','U1.3','D9.2'),('+5V_MCU_FEED','D9.1','J19.1'),('+5V_MCU','J19.2','U2.21'),('+5V_CTRL','U1.3','F2.1'),('+5V_BUZ','F2.2','BZ1.1'),('+3V3','U2.1','U40.14')]:
 try:paths.append(route(net,a,b))
 except Exception as e:paths.append({'net':net,'from':a,'to':b,'error':str(e)})
caps=[]
for p in parts.values():
 if not p['ref'].startswith('C'):continue
 for ic in [f'U{x}' for x in range(34,43)]+['U44','U45']:
  u=parts[ic];power=[x for x in u['pads'] if x['pin']==('1' if ic=='U45' else '3' if ic in ['U41','U44'] else '14')];gp=[x for x in u['pads'] if x['net']=='GND'];cp=[x for x in p['pads'] if x['net'] in ['+3V3','+5V_CTRL']];cg=[x for x in p['pads'] if x['net']=='GND']
  if power and gp and cp and cg and power[0]['net']==cp[0]['net']:
   dd=math.dist(power[0]['xy'],cp[0]['xy'])+math.dist(gp[0]['xy'],cg[0]['xy']);caps.append({'ic':ic,'capacitor':p['ref'],'sum_direct_loop_mm':dd})
nearest={ic:sorted([c for c in caps if c['ic']==ic],key=lambda x:x['sum_direct_loop_mm'])[:2] for ic in [f'U{x}' for x in range(34,43)]+['U44','U45']}
decouple=[]
for ic,cc in nearest.items():
 u=parts[ic];up=next(x for x in u['pads'] if x['pin']==('1' if ic=='U45' else '3' if ic in ['U41','U44'] else '14'));cr={'U34':'C24','U35':'C25','U36':'C26','U37':'C27','U38':'C28','U39':'C29','U40':'C30','U41':'C31','U42':'C32','U44':'C34','U45':'C35'}[ic];c=parts[cr];cp=next(x for x in c['pads'] if x['net']==up['net']);v=route(up['net'],ic+'.'+up['pin'],c['ref']+'.'+cp['pin']);decouple.append({k:a for k,a in v.items() if k!='route'})
ground_bridges=[f['xy'] for f in fs if f['kind']=='circle' and f['net']=='GND' and f['side']=='top']+[x['xy'] for p in parts.values() for x in p['pads'] if x['net']=='GND' and len(x['sides'])==2]
critical=['MCU_STEP','STEP_LATCHED','PUL_GATED','STEP_GATE','MOTOR_PUL_N','ARM_CLK','RUN_CLR_N','POR_RAW_N','POWER_OK','WDI','WDT_OK','MCU_RESET_N','I2C_SDA','I2C_SCL']
via_returns=[]
for f in fs:
 if f['kind']=='circle' and f['side']=='top' and f['net'] in critical:
  dd=min(math.dist(f['xy'],p) for p in ground_bridges);via_returns.append({'net':f['net'],'xy':f['xy'],'nearest_ground_bridge_mm':dd})
out={'revision':'V3.1','source_pcb_sha256':d['source_pcb_sha256'],'ground_copper_area_mm2':{k:v.area for k,v in ground.items()},'all_net_route_metrics':stats,'dc_forward_paths':paths,'decoupling_geometry':nearest,'decoupling_power_routes':decouple,'critical_signal_via_ground_distances':via_returns,'method':'Actual filled copper geometry; track samples every<=0.25mm; opposite-layer and coplanar ground distance, conservative35um copper forward resistance and via1mOhm. Geometric screening only, not field solver, EMC certification or measured voltage/ripple.'}
(W/'route_resistance_and_decoupling.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print('Forward resistance, actual cap power routes and critical via-return metrics saved.')
