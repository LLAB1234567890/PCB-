"""Priority-group local reroute; no global rip-up. Foreign copper remains immutable.
Two-layer octilinear grid with resistance-aware widths, explicit CASE obstacles,
native pad anchors and reviewable patch output. Filled GND is regenerated later.
"""
from pathlib import Path
import json,sys,math,itertools,heapq,time,collections
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import distance_transform_edt
from shapely.geometry import Polygon,Point,LineString,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
V=Path(sys.argv[1]);J=Path(sys.argv[2]);O=Path(sys.argv[3]);D=json.loads((V/'copper_geometry.json').read_text(encoding='utf8'));M=json.loads((V/'placement_geometry.json').read_text(encoding='utf8'));job=json.loads(J.read_text(encoding='utf8'))
step=job.get('grid_mm',.05);x0,y0=89.788,65.748;nx=math.ceil(102.48/step)+1;ny=math.ceil(71.12/step)+1;plane=nx*ny
def geo(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=16) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=32)
selected={r['net'] for r in job['routes']};remove=list({f['key'] for f in D['features'] if f['net'] in selected and f['kind'] in ['track','circle']});F=[(f,geo(f)) for f in D['features'] if f['key'] not in remove]
allpads={p['ref']+'.'+q['pin']:q for p in D['parts'] for q in p['pads'] if q['net']}
patch=[];records=[];seq=itertools.count()
def raster(gg):
 out=np.zeros((ny,nx),dtype=bool)
 def stamp(g):
  if g.is_empty:return
  if g.geom_type in ['MultiPolygon','GeometryCollection']:
   for a in g.geoms:stamp(a)
   return
  if g.geom_type!='Polygon':return
  a,b,c,d=g.bounds;ix=max(0,int((a-x0)/step)-2);iy=max(0,int((b-y0)/step)-2);jx=min(nx,int(math.ceil((c-x0)/step))+3);jy=min(ny,int(math.ceil((d-y0)/step))+3)
  if jx<=ix or jy<=iy:return
  im=Image.new('1',(jx-ix,jy-iy));dr=ImageDraw.Draw(im)
  cc=lambda ring:[((x-x0)/step-ix,(y-y0)/step-iy) for x,y in ring]
  dr.polygon(cc(g.exterior.coords),fill=1)
  for h in g.interiors:dr.polygon(cc(h.coords),fill=0)
  out[iy:jy,ix:jx]|=np.asarray(im,dtype=bool)
 for g in gg:stamp(g)
 return out
outline=Polygon(job['outline']);edge=box(x0-1,y0-1,x0+104,y0+73).difference(outline.buffer(-.51))
gbridges=[f['xy'] for f in D['features'] if f['kind']=='circle' and f['side']=='top' and f['net']=='GND']+[q['xy'] for p in D['parts'] for q in p['pads'] if q['net']=='GND' and len(q['sides'])==2]
bridge_mask=np.ones((ny,nx),dtype=bool)
for x,y in gbridges:bridge_mask[round((y-y0)/step),round((x-x0)/step)]=False
bridge_dist=distance_transform_edt(bridge_mask)*step
gnd_mask=raster([g for f,g in F if f['net']=='GND']);gnd_dist=distance_transform_edt(~gnd_mask)*step
def makepath(net,src,dst,widths):
 begin=time.monotonic();goalpad=allpads[dst];srcpad=allpads[src];nmode=len(widths);blocks=[];vblock=[];trees=[];obsby=[]
 for side in ['top','bottom']:
  obs=[(f,g) for f,g in F if f['side']==side and f['net']!=net and (not f['key'].startswith('zone:') or f['net'].startswith('CASE') and not job.get('refill_CASE_trial',False))]
  obsby.append(obs);trees.append(STRtree([g for f,g in obs]))
  forbidden=[edge]+[Polygon(q['pts']) for q in M['keepouts'] if side in q['layers'] and q['tracks']]
  for width in widths:blocks.append(raster([g.buffer(width/2+.205+step*.25) for f,g in obs]+[g.buffer(width/2) for g in forbidden]))
  sd=job.get('via_diameter',.6)
  smd=[g.buffer(.25) for f,g in F if f['side']==side and f['key'] in allpads and len(allpads[f['key']]['sides'])==1]
  supports=[box(x-2.5,y-2.5,x+2.5,y+2.5) for x,y in [[140.788,133.748],[184.288,114.748]]]
  vblock.append(raster([g.buffer(sd/2+.205+step*.25) for f,g in obs]+[g.buffer(sd/2) for g in forbidden]+smd+supports))
 for i in range(len(blocks)):blocks[i][0,:]=blocks[i][-1,:]=True;blocks[i][:,0]=blocks[i][:,-1]=True
 blocks=np.stack(blocks);N=blocks.shape[0]*plane;dist=np.full(N,np.inf,dtype=np.float32);prev=np.full(N,-1,dtype=np.int32);queue=[]
 sy,sx=round((srcpad['xy'][1]-y0)/step),round((srcpad['xy'][0]-x0)/step);gy,gx=round((goalpad['xy'][1]-y0)/step),round((goalpad['xy'][0]-x0)/step)
 def heuristic(y,x):dx,dy=abs(x-gx)*step,abs(y-gy)*step;return (max(dx,dy)+(.41421356237)*min(dx,dy))/max(widths)
 # Grid vertices inside connected pad copper are valid anchors, including THT centres.
 for s,side in enumerate(['top','bottom']):
  if side not in srcpad['sides']:continue
  for w,width in enumerate(widths):
   if blocks[s*nmode+w,sy,sx]:continue
   i=(s*nmode+w)*plane+sy*nx+sx;dist[i]=0;heapq.heappush(queue,(heuristic(sy,sx),next(seq),i,0.0))
 if not queue:raise RuntimeError((net,src,'blocked source centre'))
 dirs=[(1,0),(0,1),(-1,0),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)];end=None;expanded=0;lastreport=begin
 while queue:
  _,_,i,cc=heapq.heappop(queue)
  if abs(float(dist[i])-cc)>1e-4:continue
  mode,rem=divmod(i,plane);y,x=divmod(rem,nx);s,w=divmod(mode,nmode);width=widths[w];expanded+=1
  if x==gx and y==gy and ['top','bottom'][s] in goalpad['sides']:end=i;break
  if expanded%32768==0:
   elapsed=time.monotonic()-begin
   if elapsed>job.get('timeout_s',55):break
   if time.monotonic()-lastreport>20:print('Routing',net,expanded,'states',round(elapsed,1),'s',flush=True);lastreport=time.monotonic()
  for dy,dx in dirs:
   yy,xx=y+dy,x+dx
   if yy<=0 or yy>=ny-1 or xx<=0 or xx>=nx-1 or blocks[mode,yy,xx]:continue
   if dx and dy and (blocks[mode,y,xx] or blocks[mode,yy,x]):continue
   j=mode*plane+yy*nx+xx;reference_penalty=1+job.get('track_return_penalty',0)*max(0,float(gnd_dist[yy,xx])-.8);value=cc+step*(math.sqrt(2) if dx and dy else 1)/width*(1.005 if s else 1)*reference_penalty
   if value<float(dist[j])-1e-4:dist[j]=value;prev[j]=i;heapq.heappush(queue,(value+job.get('heuristic_weight',1.25)*heuristic(yy,xx),next(seq),j,value))
  for ww in range(nmode):
   if ww==w or blocks[s*nmode+ww,y,x]:continue
   j=(s*nmode+ww)*plane+rem;value=cc+.7
   if value<float(dist[j])-1e-4:dist[j]=value;prev[j]=i;heapq.heappush(queue,(value+heuristic(y,x),next(seq),j,value))
  if not vblock[0][y,x] and not vblock[1][y,x] and not blocks[(1-s)*nmode+w,y,x] and bridge_dist[y,x]<=job.get('return_via_max_mm',100):
   j=((1-s)*nmode+w)*plane+rem;value=cc+job.get('via_cost',8)+max(0,float(bridge_dist[y,x])-1)*job.get('return_penalty',0)
   if value<float(dist[j])-1e-4:dist[j]=value;prev[j]=i;heapq.heappush(queue,(value+heuristic(y,x),next(seq),j,value))
 if end is None:raise RuntimeError((net,src,dst,'no route or timeout',expanded,round(time.monotonic()-begin,1)))
 route=[end]
 while prev[route[-1]]>=0:route.append(int(prev[route[-1]]))
 route.reverse();path=[]
 for i in route:
  m,r=divmod(i,plane);y,x=divmod(r,nx);s,w=divmod(m,nmode);path.append((s,w,x,y))
 verts=[path[0]]
 for i in range(1,len(path)-1):
  a,b,c=path[i-1],path[i],path[i+1]
  if a[:2]!=b[:2] or b[:2]!=c[:2] or (b[2]-a[2],b[3]-a[3])!=(c[2]-b[2],c[3]-b[3]):verts.append(b)
 verts.append(path[-1]);items=[]
 def point(v):return [round(x0+v[2]*step,6),round(y0+v[3]*step,6)]
 # Exact pad-centre endpoints, with a short off-grid pad entry only.
 for pad,v in [(srcpad,verts[0]),(goalpad,verts[-1])]:
  vv=point(v)
  if vv!=pad['xy']:items.append({'type':'segment','net':net,'a':pad['xy'],'b':vv,'side':['top','bottom'][v[0]],'width':widths[v[1]],'purpose':'exact pad centre to grid anchor'})
 for a,b in zip(verts,verts[1:]):
  aa,bb=point(a),point(b)
  if a[0]!=b[0]:items.append({'type':'via','net':net,'xy':aa,'diameter':job.get('via_diameter',.6),'drill':.3})
  elif aa!=bb:items.append({'type':'segment','net':net,'a':aa,'b':bb,'side':['top','bottom'][a[0]],'width':widths[a[1]]})
 # Final exact geometry checks against every immutable foreign conductor/CASE.
 for a in items:
  if a['type']=='via':pairs=[(s,Point(a['xy']).buffer(a['diameter']/2,quad_segs=32)) for s in [0,1]]
  else:pairs=[(0 if a['side']=='top' else 1,LineString([a['a'],a['b']]).buffer(a['width']/2,quad_segs=16))]
  for s,g in pairs:
   for k in trees[s].query(g.buffer(.201)):
    f,h=obsby[s][int(k)];assert g.distance(h)>=.2001,(net,'exact clearance failed',f['key'],g.distance(h),a)
  kid='trial-'+str(next(seq))
  for s,g in pairs:F.append(({'side':['top','bottom'][s],'net':net,'key':kid,'kind':'circle' if a['type']=='via' else 'track'},g))
 return items,{'net':net,'from':src,'to':dst,'length_mm':sum(math.dist(a['a'],a['b']) for a in items if a['type']=='segment'),'vias':sum(a['type']=='via' for a in items),'segments':sum(a['type']=='segment' for a in items),'resistance_proxy_ohm_20C':sum(.01724*math.dist(a['a'],a['b'])/1000/(a['width']*.035) for a in items if a['type']=='segment')+.001*sum(a['type']=='via' for a in items),'search_states':expanded,'seconds':time.monotonic()-begin}
failed=[]
for r in job['routes']:
 try:
  items,report=makepath(r['net'],r['from'],r['to'],r.get('widths',[.2]));patch+=items;records.append(report);print(report,flush=True)
 except Exception as e:failed.append({'request':r,'error':str(e)});print('FAILED',str(e),flush=True)
O.write_text(json.dumps({'scope':'Only the enumerated priority-group nets; all foreign existing tracks/pads/CASE are immutable obstacles','remove':remove,'items':patch,'routes':records,'failed':failed},ensure_ascii=False,indent=2),encoding='utf8')
if failed:raise SystemExit(2)
