from pathlib import Path
import sys,json,math,collections
import numpy as np
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import unary_union,nearest_points
from shapely.strtree import STRtree
V=Path(sys.argv[1]);B=Path(sys.argv[2]);O=Path(sys.argv[3]);D=json.loads((V/'copper_geometry.json').read_text(encoding='utf8'));M=json.loads((V/'placement_geometry.json').read_text(encoding='utf8'));base=json.loads((B/'copper_gate.json').read_text(encoding='utf8'));now=json.loads((V/'copper_gate.json').read_text(encoding='utf8'));F=D['features']
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=32) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=64)
G=[shape(f) for f in F];ground={s:unary_union([g for f,g in zip(F,G) if f['side']==s and f['net']=='GND']) for s in ['top','bottom']};board=Polygon(D['board_outline']).buffer(-.501)
obs={s:[(f,g) for f,g in zip(F,G) if f['side']==s and f['net']!='GND' and not f['key'].startswith('zone:')] for s in ground};trees={s:STRtree([g for f,g in obs[s]]) for s in ground}
case={n:{s:unary_union([g for f,g in zip(F,G) if f['side']==s and f['net']==n]) for s in ground} for n in ['CASE_U1','CASE_U11','CASE_U33']};spent={n:{s:0 for s in ground} for n in case}
smdkeys={p['ref']+'.'+q['pin'] for p in D['parts'] for q in p['pads'] if len(q['sides'])==1};smd=[g for f,g in zip(F,G) if f['key'] in smdkeys];smdtree=STRtree(smd)
bridges=[f['xy'] for f in F if f['kind']=='circle' and f['side']=='top' and f['net']=='GND']+[q['xy'] for p in D['parts'] for q in p['pads'] if q['net']=='GND' and len(q['sides'])==2]
def paths(a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];ax,ay=abs(dx),abs(dy);sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
 if ax>ay:return [[a,[a[0]+sx*ay,b[1]],b],[a,[b[0]-sx*ay,a[1]],b]]
 return [[a,[b[0],a[1]+sy*ax],b],[a,[a[0],b[1]-sy*ax],b]]
def clear(poly,s):
 if not board.covers(poly):return False
 if any(poly.distance(obs[s][int(k)][1])<.205 for k in trees[s].query(poly.buffer(.21))):return False
 if any(s in q['layers'] and q['tracks'] and poly.intersects(Polygon(q['pts'])) for q in M['keepouts']):return False
 return True
items=[];notes=[];deferred=[]
critical={'WDI','ARM_CLK','MCU_RESET_N','STEP_LATCHED','RUN_CLR_N','POWER_OK'}
vv=[f for f in F if f['kind']=='circle' and f['side']=='top' and f['net'] in critical];vv.sort(key=lambda f:-min(math.dist(f['xy'],b) for b in bridges))
for f in vv:
 old=min(math.dist(f['xy'],b) for b in bridges)
 if old<3:continue
 xx,yy=f['xy'];options=[]
 for radius in [1.,1.8]:
  for x in np.arange(xx-radius,xx+radius+.03,.1):
   for y in np.arange(yy-radius,yy+radius+.03,.1):
    xy=[round(float(x),6),round(float(y),6)];dd=math.dist(xy,f['xy'])
    if dd>radius or dd>=old-.5 or min(math.dist(xy,b) for b in bridges)<.65:continue
    disk=Point(xy).buffer(.25,quad_segs=64)
    if any(disk.distance(smd[int(k)])<.2 for k in smdtree.query(disk.buffer(.21))):continue
    if not all(clear(disk,s) for s in ground):continue
    route={};lost={n:{} for n in case};ok=True;length=0
    for s in ground:
     best=None
     tap=nearest_points(Point(xy),ground[s])[1];bb=[round(tap.x,6),round(tap.y,6)]
     if math.dist(xy,bb)>5:ok=False;break
     if ground[s].covers(disk):best=([xy],disk,0)
     else:
      for pp in paths(xy,bb):
       pl=LineString(pp);poly=pl.buffer(.1,quad_segs=64).union(disk)
       if clear(poly,s) and (best is None or pl.length<best[2]):best=(pp,poly,pl.length)
     if best is None:ok=False;break
     route[s]=best;length+=best[2]
     for n in case:
      loss=best[1].buffer(.205).intersection(case[n][s]).area;lost[n][s]=loss
      margin=now['anchored_area_mm2'][n][s]-base['anchored_area_mm2'][n][s]-spent[n][s]
      if loss>max(0,margin-.03):ok=False;break
    if ok:options.append((dd+length*.2,xy,dd,route,lost))
  if options:break
 if not options:deferred.append({'net':f['net'],'signal_via':f['xy'],'nearest_ground_bridge_mm':old,'reason':'No <=1.8mm legal return via plus copper-root stubs within exact CASE-area budget and fixed/solder clearances.'});continue
 _,xy,dd,route,lost=min(options,key=lambda a:a[0]);bridges.append(xy);items.append({'type':'via','net':'GND','xy':xy,'diameter':.5,'drill':.3})
 for s,(pp,poly,L) in route.items():
  ground[s]=ground[s].union(poly)
  for a,b in zip(pp,pp[1:]):
   if math.dist(a,b)>.000001:items.append({'type':'segment','net':'GND','side':s,'width':.2,'a':[round(v,6) for v in a],'b':[round(v,6) for v in b]})
  for n in case:spent[n][s]+=lost[n][s]
 notes.append({'net':f['net'],'signal_via':f['xy'],'new_ground_via':xy,'before_mm':old,'after_mm':dd,'case_loss_upper_screen_mm2':lost,'ground_root_connection':'Both sides connected by plated via and explicit stubs into already anchor-connected GND; final filled-copper gate required.'})
O.write_text(json.dumps({'remove':[],'items':items,'strategic_returns':notes,'deferred':deferred,'CASE_loss_screen':spent},ensure_ascii=False,indent=2),encoding='utf8');print('Strategic ground returns',len(notes),'conductors',len(items),'deferred',len(deferred))
