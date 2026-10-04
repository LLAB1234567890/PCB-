"""Paired DC sheet screening on copper unions, independent of track segmentation.
Raster convergence and contact/barrel assumptions are reported, never measured IR.
"""
from pathlib import Path
import json,math,sys
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from scipy.sparse.csgraph import connected_components
from shapely.geometry import Polygon,Point,LineString
from shapely.ops import unary_union
from shapely import contains_xy
W=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text(encoding='utf8'))
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=64) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=64).difference(Point(f['xy']).buffer(f['drill_radius'],quad_segs=64))
def solve(D,net,start,end,h):
 fs=[f for f in D['features'] if f['net']==net];gs=[shape(f) for f in fs];cu={s:unary_union([g for f,g in zip(fs,gs) if f['side']==s]) for s in ['top','bottom']};total=unary_union(list(cu.values()));xmin,ymin,xmax,ymax=total.bounds;ox=math.floor(xmin/h)*h;oy=math.floor(ymin/h)*h
 xx=np.arange(ox+h/2,xmax+h,h);yy=np.arange(oy+h/2,ymax+h,h);X,Y=np.meshgrid(xx,yy);ids={};masks={};coords=[];off=0;edges=[];conductance=[];rs=.01724/1000/.035
 for s in cu:
  mask=contains_xy(cu[s],X,Y);idmap=np.full(mask.shape,-1,dtype=int);idmap[mask]=np.arange(off,off+mask.sum());off+=mask.sum();ids[s]=idmap;masks[s]=mask;coords.extend(zip(X[mask],Y[mask]))
  for aa,bb in [(idmap[:,:-1],idmap[:,1:]),(idmap[:-1,:],idmap[1:,:])]:
   ok=(aa>=0)&(bb>=0);edges.extend(zip(aa[ok],bb[ok]));conductance.extend(np.full(ok.sum(),1/rs))
 # Plated annuli/pads create cross-layer return paths with finite barrel R.
 for key in D['plated_bridges']:
  ff=[(f,g) for f,g in zip(fs,gs) if f['key']==key];sides={f['side'] for f,g in ff}
  if sides!={'top','bottom'}:continue
  ring={}
  for f,g in ff:
   mask=contains_xy(g,X,Y)&masks[f['side']];ring[f['side']]=ids[f['side']][mask]
  if not all(len(a) for a in ring.values()):continue
  f=ff[0][0]
  radius=f.get('drill_radius',0)
  if not radius:
   part,pin=key.split('.');p=next(p for a in D['parts'] if a['ref']==part for p in a['pads'] if p['pin']==pin);radius=min(p['drill'])/2
  rb=.01724/1000*1.6/(math.pi*max(2*radius,.1)*.025);star=off;off+=1
  for a in ring.values():edges.extend((int(k),int(star)) for k in a);conductance.extend(np.full(len(a),2/(rb*len(a))))
 contact={}
 for key,val in [(start,0.),(end,1.)]:
  wanted=[]
  for f,g in zip(fs,gs):
   if f['key']==key:
    mask=contains_xy(g,X,Y)&masks[f['side']];wanted.extend(ids[f['side']][mask])
  assert wanted,(net,key,h);contact[key]=np.unique(wanted)
 ea=np.array(edges,dtype=int);cc=np.array(conductance);assert len(ea)
 adj=coo_matrix((np.ones(len(ea)*2),(np.r_[ea[:,0],ea[:,1]],np.r_[ea[:,1],ea[:,0]])),shape=(off,off)).tocsr();ncomp,labels=connected_components(adj,directed=False);srcroot=labels[contact[start][0]];assert all(labels[contact[end]]==srcroot),(net,'raster disconnected',h)
 used=np.where(labels==srcroot)[0];fixed=np.r_[contact[start],contact[end]];free=np.setdiff1d(used,fixed);values=np.zeros(off);values[contact[end]]=1
 lap=coo_matrix((np.r_[cc,cc,-cc,-cc],(np.r_[ea[:,0],ea[:,1],ea[:,0],ea[:,1]],np.r_[ea[:,0],ea[:,1],ea[:,1],ea[:,0]])),shape=(off,off)).tocsr()
 values[free]=spsolve(lap[free][:,free],-lap[free].dot(values));current=lap[contact[end]].dot(values).sum();R=1/current;residual=float(np.max(np.abs(lap[free].dot(values))))
 return {'net':net,'from':start,'to':end,'mesh_mm':h,'nodes':len(used),'resistance_ohm_20C':float(R),'max_current_balance_residual_A_at_1V':residual,'raster_component_count':int(ncomp)}
results={}
for rev,fn in [('V3',W/'evidence/baseline/copper_geometry.json'),('V3.1',W/'validation/routing/copper_geometry.json')]:
 D=read(fn);rows=[]
 for h in [.05,.04]:
  for net,a,b in [('+5V_CTRL','U1.3','D9.2'),('+5V_MCU_FEED','D9.1','J19.1'),('+5V_MCU','J19.2','U2.21')]:
   z=solve(D,net,a,b,h);rows.append(z);print(rev,z,flush=True)
 for h in [.2,.15]:
  try:z=solve(D,'GND','U1.2','U2.22',h)
  except AssertionError as e:z={'net':'GND','mesh_mm':h,'status':'RASTER_UNRESOLVED','reason':str(e),'actual_connectivity':'Native and independent exact copper connectivity are authoritative; coarse raster cannot replace them.'}
  rows.append(z);print(rev,z,flush=True)
 results[rev]={'source_pcb_sha256':D['source_pcb_sha256'],'cases':rows}
out={'paired':results,'method':'Copper union four-neighbour sheet network, rho20C0.01724ohm mm2/m,35um faces;1.6mm/25um plated barrels; ideal solder pad contacts. Raster estimate and mesh sensitivity, not field solver or measured complete supply voltage. Identical method on V3/V3.1; collinear segmentation cannot alter geometry used.','limitations':['Centre-sampled cells produce width/neck and diagonal bias, especially on fine traces; mesh deltas must be considered.','Only MCU branch injection is evaluated; other ground currents, contact resistance, ripple and transients remain prototype acceptance.','No AC return inductance or electromagnetic immunity proof.']}
(W/'validation/DC_sheet_paired.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
