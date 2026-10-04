from pathlib import Path
import json,sys,math,collections
import numpy as np
from shapely.geometry import Polygon,LineString,Point,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
V=Path(sys.argv[1]);out=Path(sys.argv[2]);D=json.loads((V/'copper_geometry.json').read_text(encoding='utf8'));M=json.loads((V/'placement_geometry.json').read_text(encoding='utf8'));crit=set(sys.argv[3].split(',')) if len(sys.argv)>3 else {'MCU_RESET_N','WDI','WDT_OK','ARM_CLK','MCU_STEP','STEP_LATCHED','RUN_CLR_N','POR_RAW_N','POWER_OK','PUL_GATED'}
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=16) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=32)
F=D['features'];G=[shape(f) for f in F];ground={s:unary_union([g for f,g in zip(F,G) if f['side']==s and f['net']=='GND']) for s in ['top','bottom']}
foreign={s:[(f,g) for f,g in zip(F,G) if f['side']==s and f['net']!='GND'] for s in ground};trees={s:STRtree([g for f,g in foreign[s]]) for s in ground}
smdkeys={p['ref']+'.'+q['pin'] for p in D['parts'] for q in p['pads'] if len(q['sides'])==1};smd=[g for f,g in zip(F,G) if f['key'] in smdkeys];smdtree=STRtree(smd)
bridge=[f['xy'] for f in F if f['kind']=='circle' and f['net']=='GND' and f['side']=='top']+[q['xy'] for p in D['parts'] for q in p['pads'] if q['net']=='GND' and len(q['sides'])==2];items=[];notes=[];deferred=[]
vias=[f for f in F if f['kind']=='circle' and f['side']=='top' and f['net'] in crit];vias.sort(key=lambda f:-min(math.dist(f['xy'],g) for g in bridge))
for f in vias:
 old=min(math.dist(f['xy'],g) for g in bridge)
 if old<=1:continue
 xx,yy=f['xy'];candidates=[]
 for radius in [1.,2.,3.]:
  for x in np.arange(xx-radius,xx+radius+.05,.1):
   for y in np.arange(yy-radius,yy+radius+.05,.1):
    x,y=round(float(x),6),round(float(y),6);dd=math.hypot(x-xx,y-yy)
    if dd>radius or dd>=old-.15 or any(math.dist((x,y),g)<.65 for g in bridge):continue
    disk=Point(x,y).buffer(.275,quad_segs=32)
    # Both faces already must be true GND; adding a named via on an island is forbidden.
    if not all(ground[s].covers(disk.buffer(.01)) for s in ground):continue
    if any(x-2.5<=x2<=x+2.5 and y-2.5<=y2<=y+2.5 for x2,y2 in [(140.788,133.748),(184.288,114.748)]):continue
    if any((q['vias'] or q['tracks']) and disk.intersects(Polygon(q['pts'])) for q in M['keepouts']):continue
    if any(disk.distance(foreign[s][int(i)][1])<.205 for s in ground for i in trees[s].query(disk.buffer(.21))):continue
    # SMD solder exclusion on either face.
    if any(disk.distance(smd[int(i)])<.2 for i in smdtree.query(disk.buffer(.205))):continue
    candidates.append((dd,x,y))
  if candidates:break
 if not candidates:deferred.append({'net':f['net'],'signal_via':f['xy'],'nearest_bridge_mm':old,'reason':'No legal 0.55/0.30mm through GND bridge on both existing GND faces within3mm; no CASE island substitution.'});continue
 dd,x,y=min(candidates);bridge.append([x,y]);items.append({'type':'via','net':'GND','xy':[x,y],'diameter':.55,'drill':.3});notes.append({'signal_net':f['net'],'signal_via':f['xy'],'ground_via':[x,y],'before_mm':old,'after_mm':dd,'both_faces_already_GND':True})
out.write_text(json.dumps({'remove':[],'items':items,'ground_return_improvements':notes,'deferred':deferred},ensure_ascii=False,indent=2),encoding='utf8');print('Legal GND bridges',len(items),'deferred',len(deferred))
