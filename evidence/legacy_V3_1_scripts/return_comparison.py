from pathlib import Path
import json,math
import numpy as np
from shapely.geometry import Point,Polygon,LineString
from shapely.ops import unary_union,linemerge
from shapely import points,distance
W=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text(encoding='utf8'))
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=64) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=64).difference(Point(f['xy']).buffer(f['drill_radius'],quad_segs=64))
data={r:read(p) for r,p in [('V3',W/'evidence/baseline/copper_geometry.json'),('V3.1',W/'validation/routing/copper_geometry.json')]};ground={r:{s:unary_union([shape(f) for f in d['features'] if f['net']=='GND' and f['side']==s]) for s in ['top','bottom']} for r,d in data.items()};both={r:unary_union(list(g.values())) for r,g in ground.items()}
nets=['MCU_RESET_N','MCU_WDI','WDI','WDT_OK','POR_RAW_N','POWER_OK','ARM_CLK','RUN_CLR_N','RUN_LATCH_Q','MCU_STEP','STEP_LATCHED','PUL_GATED','MCU_DIR','HOLD_ENABLE','I2C_SDA','I2C_SCL'];out={}
for n in nets:
 out[n]={}
 for rev,d in data.items():
  pts=[];sidepts={}
  for s in ['top','bottom']:
   metal=unary_union([shape(f) for f in d['features'] if f['net']==n and f['side']==s and f['kind']!='track' and not f['key'].startswith('zone:')]);line=unary_union([LineString([f['a'],f['b']]) for f in d['features'] if f['net']==n and f['side']==s and f['kind']=='track']).difference(metal)
   if line.is_empty:sidepts[s]=[];continue
   if line.geom_type=='MultiLineString':line=linemerge(line)
   lines=list(line.geoms) if line.geom_type=='MultiLineString' else [line]
   pp=[]
   for q in lines:
    if q.geom_type!='LineString':continue
    count=max(1,math.ceil(q.length/.05));pp.extend(q.interpolate(q.length*i/count).coords[0] for i in range(count+1))
   sidepts[s]=pp;pts.extend(pp)
  a=points(np.array(pts));da=distance(a,both[rev]);worst=int(np.argmax(da));op=[]
  for s,pp in sidepts.items():
   if pp:op.extend(distance(points(np.array(pp)),ground[rev]['bottom' if s=='top' else 'top']))
  # The very same spatial samples expose genuine GND changes without track split bias.
  paired=distance(a,both['V3.1'])-distance(a,both['V3']);out[n][rev]={'max_any_GND_distance_mm':float(max(da)),'max_opposite_GND_distance_mm':float(max(op)),'any_reference_within_1mm_sample_percent':float(np.mean(da<=1)*100),'worst_xy_mm':list(pts[worst]),'max_same_point_change_in_GND_distance_mm':float(max(paired)),'same_point_worst_change_xy_mm':list(pts[int(np.argmax(paired))]),'sample_count':len(pts)}
(W/'validation/RETURN_paired_canonical.json').write_text(json.dumps({'nets':out,'method':'Actual GND copper unions; net track line-coverage union, pads/vias excluded from escape centreline,0.05mm sampling. Same-point comparison separates genuine GND changes from track-split sampling differences. Screening only, not inductance/EMC acceptance.'},ensure_ascii=False,indent=2),encoding='utf8')
print([(n,round(v['V3.1']['max_any_GND_distance_mm']-v['V3']['max_any_GND_distance_mm'],4),round(v['V3.1']['max_same_point_change_in_GND_distance_mm'],4)) for n,v in out.items()])
