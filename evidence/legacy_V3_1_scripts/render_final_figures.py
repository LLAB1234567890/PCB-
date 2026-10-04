from pathlib import Path
import json,csv,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch,Circle,Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from shapely.geometry import Polygon,Point,LineString
from shapely.geometry.polygon import orient
W=Path(__file__).resolve().parents[1];C=W;O=C/'reports/figures';O.mkdir(parents=True,exist_ok=True)
font_manager.fontManager.addfont(r'C:\Windows\Fonts\msyh.ttc');plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':10,'axes.unicode_minus':False})
g=json.loads((C/'thermal/board_geometry.json').read_text(encoding='utf8'));d=json.loads((C/'validation/routing/copper_geometry.json').read_text(encoding='utf8'));s=json.loads((C/'mechanical/bare_PCB_support_analysis.json').read_text(encoding='utf8'));r=json.loads((C/'thermal/results.json').read_text(encoding='utf8'))
def save(fig,name):
 fig.savefig(O/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(O/(name+'.svg'),bbox_inches='tight');plt.close(fig)
def draw(ax,poly,col,alpha=1):
 if poly.is_empty:return
 if poly.geom_type=='MultiPolygon':
  for q in poly.geoms:draw(ax,q,col,alpha)
  return
 if poly.geom_type!='Polygon':return
 poly=orient(poly,1);verts=[];codes=[]
 for ring in [poly.exterior,*poly.interiors]:
  xy=list(ring.coords);verts.extend(xy);codes.extend([MPath.MOVETO]+[MPath.LINETO]*(len(xy)-2)+[MPath.CLOSEPOLY])
 ax.add_patch(PathPatch(MPath(verts,codes),facecolor=col,edgecolor='none',alpha=alpha))
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=8) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=8).difference(Point(f['xy']).buffer(f['drill_radius'],quad_segs=8))
for side,name in [('top','PCB_F_Cu'),('bottom','PCB_B_Cu')]:
 fig,ax=plt.subplots(figsize=(11.5,8));ax.set_facecolor('#142431')
 for f in sorted(d['features'],key=lambda q:not q['key'].startswith('zone:')):
  if f['side']!=side:continue
  col='#406c56' if f['net']=='GND' else '#d6ad35' if f['net'].startswith('CASE') else '#e75460' if side=='top' else '#74aee4'
  draw(ax,shape(f),col,.76 if f['key'].startswith('zone:') else 1)
 for p in d['parts']:
  if p['side']==side:ax.text(p['x'],p['y'],p['ref'],ha='center',va='center',fontsize=6,color='white',clip_on=True)
 xy=np.array(g['outline']+[g['outline'][0]]);ax.plot(*xy.T,color='white',lw=1)
 ax.set_xlim(89,193);ax.set_ylim(137.8,65);ax.set_aspect('equal');ax.set_xlabel('KiCad X / mm');ax.set_ylabel('KiCad Y / mm');ax.set_title('V3.1 '+('顶层' if side=='top' else '底层')+'实际铜层：绿色 GND，黄色浮置 CASE 散热铜');save(fig,name)
fig,ax=plt.subplots(figsize=(10,7));draw(ax,Polygon(g['outline']),'#e3efdf')
for p in g['parts']:
 if p['side']=='bottom':ax.add_patch(Rectangle((p['body_bbox'][0],p['body_bbox'][1]),p['body_bbox'][2]-p['body_bbox'][0],p['body_bbox'][3]-p['body_bbox'][1],facecolor='#9baea9',alpha=.45,lw=0))
for h in s['fixed_supports']:
 x,y=h['x'],h['y'];ax.add_patch(Rectangle((x-2.5,y-2.5),5,5,facecolor='#426fbe',alpha=.6));ax.text(x,y-3,h['ref'],ha='center',color='#234878');ax.add_patch(Circle((x,y),h['drill_mm']/2,color='white'))
for h in s['additional_supports']:
 x,y=h['xy_mm'];ax.add_patch(Rectangle((x-2.5,y-2.5),5,5,facecolor='#e79b42',alpha=.7));ax.text(x,y-3,h['ref']+' 缓冲支撑',ha='center',color='#865617')
ax.scatter(*s['centroid_KiCad_mm'],marker='+',s=150,c='#bb3147');ax.text(s['centroid_KiCad_mm'][0]+2,s['centroid_KiCad_mm'][1]+1,'裸板重心',color='#bb3147');ax.set_xlim(89,193);ax.set_ylim(137.8,65);ax.set_aspect('equal');ax.set_xlabel('KiCad X / mm');ax.set_ylabel('KiCad Y / mm');ax.set_title(f"裸板估算 {s['bare_board_estimate_g']:.2f} g；6 个固定孔 + 2 个无孔缓冲支撑\n灰色为底面器件禁放区域；不含器件质量与插拔冲击");save(fig,'PCB_supports')
meshes=json.loads((C/'mechanical/preview_mesh.json').read_text(encoding='utf8'))
fig=plt.figure(figsize=(12,8));ax=fig.add_subplot(111,projection='3d');allv=[]
for m in meshes:
 name=m['name']
 if name.startswith(('Lid_','USB_corridor','Conservative_THT')):continue
 v=np.array(m['vertices']);f=np.array(m['faces']);allv.extend(v)
 col=m['color'];alpha=.27 if name.startswith('PA12_Main') else .85
 ax.add_collection3d(Poly3DCollection(v[f],facecolor=col,edgecolor='none',alpha=alpha))
v=np.array(allv);lo=v.min(axis=0);hi=v.max(axis=0);ax.set_xlim(lo[0]-5,hi[0]+5);ax.set_ylim(lo[1]-5,hi[1]+5);ax.set_zlim(0,65);ax.set_box_aspect((hi[0]-lo[0],hi[1]-lo[1],65));ax.view_init(55,-65);ax.set_xlabel('CAD X / mm');ax.set_ylabel('CAD Y / mm');ax.set_zlabel('Z / mm');ax.set_title('V3.1 装配参考模型：顶部敞开，按钮仓向外\n半透明 PA12 外壳；器件/按钮/USB 为尺寸包络，实物适配待验收');save(fig,'Enclosure_preview')
cases=['nominal_99kPa','nominal_101kPa','nominal_103kPa','stress_101kPa','adverse_99kPa','mesh_2mm_101kPa'];labels=['名义 99kPa','名义 101kPa','名义 103kPa','较重负载 101kPa','不利参数 99kPa','名义细网格 101kPa']
fig,ax=plt.subplots(figsize=(10.5,5));x=np.arange(len(cases));width=.24
for j,(key,label,col) in enumerate([('max_pcb_C','PCB 最高','#d4772b'),('max_pa12_C','PA12 最高','#5d927a'),('U2','开发板等效','#a65579')]):
 values=[r[c]['hot_components_C']['U2'] if key=='U2' else r[c][key] for c in cases];ax.bar(x+(j-1)*width,values,width,label=label,color=col)
 for xx,yy in zip(x+(j-1)*width,values):ax.text(xx,yy+.5,f'{yy:.1f}',ha='center',fontsize=8)
ax.axhline(24,color='#74858f',ls=':',label='环境 24℃');ax.set_xticks(x,labels,rotation=15,ha='right');ax.set_ylabel('稳态估算 / ℃');ax.set_ylim(20,101);ax.grid(axis='y',alpha=.2);ax.legend(ncol=4,fontsize=9);ax.set_title('无强制风、水平敞口 PA12 外壳的参数化热估算\n开发板为等效表面节点；不等于芯片结温或实测温度');save(fig,'Thermal_cases')
fig,axs=plt.subplots(1,2,figsize=(13,5.5));xy=np.array([[x-141.028,101.308-y] for x,y in g['outline']+[g['outline'][0]]])
for ax,case,label in zip(axs,['nominal_101kPa','stress_101kPa'],['名义负载','较重连续负载']):
 rows=list(csv.DictReader((C/'thermal'/(case+'_nodes.csv')).open(encoding='utf8')));rows=[a for a in rows if a['name']=='PCB top'];xs=[float(a['X_mm']) for a in rows];ys=[float(a['Y_mm']) for a in rows];ts=[float(a['temperature_C']) for a in rows]
 im=ax.scatter(xs,ys,c=ts,cmap='inferno',s=26,marker='s',vmin=24,vmax=70);ax.plot(*xy.T,c='black',lw=.7);ax.set_aspect('equal');ax.set_xlabel('CAD X / mm');ax.set_ylabel('CAD Y / mm');ax.set_title(label+'，101kPa，PCB 顶面');fig.colorbar(im,ax=ax,label='℃')
fig.suptitle('实际板框、填充铜及槽孔进入热模型；3mm 网格');save(fig,'Thermal_board_maps')
print('Final PCB/support/enclosure/thermal figures saved',len(list(O.glob('*.png'))))

