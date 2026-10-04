from pathlib import Path
import json,collections,csv,math
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.path import Path as MP
from matplotlib.patches import PathPatch,Rectangle
from shapely.geometry import Polygon,LineString,Point
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely import points,distance
F=Path(__file__).resolve().parents[1];O=F/'reports/figures';O.mkdir(exist_ok=True);read=lambda p:json.loads(p.read_text(encoding='utf8'))
font_manager.fontManager.addfont(r'C:\Windows\Fonts\msyh.ttc');plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':10,'axes.unicode_minus':False})
base=read(F/'evidence/baseline/copper_geometry.json');final=read(F/'validation/routing/copper_geometry.json');places=read(F/'evidence/candidate_placement_comparison.json');ng=read(F/'thermal/board_geometry.json')
base['board_outline']=final['board_outline'] # Independently asserted unchanged native outline in CONSISTENCY_R1 / PCB_R1.
def shape(f):return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=16) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=16).difference(Point(f['xy']).buffer(f['drill_radius'],quad_segs=16))
def draw(ax,g,col,alpha=1):
 if g.is_empty:return
 if g.geom_type=='MultiPolygon':
  for a in g.geoms:draw(ax,a,col,alpha)
  return
 if g.geom_type!='Polygon':return
 g=orient(g,1);vv=[];cc=[]
 for q in [g.exterior,*g.interiors]:
  a=list(q.coords);vv+=a;cc += [MP.MOVETO]+[MP.LINETO]*(len(a)-2)+[MP.CLOSEPOLY]
 ax.add_patch(PathPatch(MP(vv,cc),facecolor=col,edgecolor='none',alpha=alpha))
def board(ax,d,side,bounds=None,highlight=None):
 ax.set_facecolor('#152632')
 for f in sorted(d['features'],key=lambda f:not f['key'].startswith('zone:')):
  if f['side']!=side:continue
  col='#385c4b' if f['net']=='GND' else '#927938' if f['net'].startswith('CASE') else '#dd5861' if side=='top' else '#76aee1'
  if highlight and f['net'] in highlight:col='#ffde5e'
  draw(ax,shape(f),col)
 xy=np.array(d['board_outline']+[d['board_outline'][0]]);ax.plot(*xy.T,'w',lw=.8)
 bounds=bounds or [89,193,65,138];ax.set_xlim(bounds[:2]);ax.set_ylim(bounds[3],bounds[2]);ax.set_aspect('equal');ax.set_xlabel('X / mm');ax.set_ylabel('Y / mm')
def save(fig,name):fig.savefig(O/(name+'.png'),dpi=190,bbox_inches='tight');plt.close(fig)
for side in ['top','bottom']:
 fig,axs=plt.subplots(1,2,figsize=(16,6));
 for ax,d,label in zip(axs,[base,final],['V3 基线','V3.1 最终']):board(ax,d,side);ax.set_title(label)
 fig.suptitle(('顶层' if side=='top' else '底层')+'实际铜同尺度比较：GND 绿色 / CASE 金色 / 信号红或蓝');save(fig,'comparison_'+side)
fig,axs=plt.subplots(1,2,figsize=(12,6));
for ax,d,label in zip(axs,[base,final],['V3：C35 原位置','V3.1：C35/R57 同面互换']):
 board(ax,d,'top',[143.5,157,71,82.5],{'+3V3','GND'});ax.set_title(label)
 for p in d['parts']:
  if p['ref'] in ['U45','C35','R57','R58','R60']:ax.text(p['x'],p['y'],p['ref'],ha='center',color='white',fontsize=8)
save(fig,'comparison_watchdog')
fig,axs=plt.subplots(1,2,figsize=(16,6));
for ax,d,label in zip(axs,[base,final],['V3：原 5V MCU 通路','V3.1：先保留地参考，再局部加宽']):board(ax,d,'bottom',[94,138,75,127],{'+5V_CTRL','+5V_MCU_FEED','+5V_MCU'});ax.set_title(label)
save(fig,'comparison_power')
# Same-scale finite candidate views, every unchanged body remains visible.
fig,axs=plt.subplots(1,3,figsize=(16,5.7));parts={p['ref']:p for p in ng['parts']}
for ax,key in zip(axs,['A','B','C']):
 xy=np.array(final['board_outline']+[final['board_outline'][0]]);ax.plot(*xy.T,'#506371');ax.set_xlim(118,190);ax.set_ylim(123,70);ax.set_aspect('equal')
 poses=places[key]['placements'];poses=poses if key!='A' else {'C35':[148,74.25],'R57':[146,76.75]}
 for ref,p in parts.items():
  if p['side']!='bottom' and ref not in ['U45','C35','R57','R58','R60']:continue
  box0=p['body_bbox'];dx=poses.get(ref,[p['x'],p['y']])[0]-p['x'];dy=poses.get(ref,[p['x'],p['y']])[1]-p['y'];ax.add_patch(Rectangle((box0[0]+dx,box0[1]+dy),box0[2]-box0[0],box0[3]-box0[1],facecolor='#cd5d54' if ref in poses else '#b6c7c8',edgecolor='white',alpha=.75))
  if ref in ['U45','C35','U39','U40','U34','U35','C25','C29']:ax.text(p['x']+dx,p['y']+dy,ref,fontsize=7,ha='center')
 ax.set_xlabel('KiCad X / mm');ax.set_ylabel('KiCad Y / mm');ax.set_title({'A':'A 主要位置保留：采用','B':'B 看门狗组迁移：冲突淘汰','C':'C 联锁组迁移：冲突淘汰'}[key],fontsize=11)
fig.suptitle('有限候选布局比较：红色表示候选位置；同面、方向和固定接口约束不变');save(fig,'candidate_placement')
silk=read(F/'validation/SILK_native_review.json');fig,axs=plt.subplots(1,2,figsize=(16,6));
for ax,side in zip(axs,['top','bottom']):
 board(ax,final,side)
 for t in silk['visible_texts']:
  if t['side']!=side:continue
  ax.text(*t['xy_mm'],t['text'],fontsize=max(3.7,t['text_size_mm'][1]*5),rotation=-t['angle_degrees'],color='#fff5ba',ha='center',va='center',clip_on=True)
 ax.set_title(('顶层' if side=='top' else '底层')+'原生丝印位置/方向（非居中重标位号）')
save(fig,'silk_actual_positions')
# Full changed-object table, beyond the243original short-object ledger.
B=read(F/'evidence/baseline/native_inventory.json');N=read(F/'validation/routing/native_inventory.json');rows=[]
for kind in ['tracks','vias','zones','footprints']:
 a={t['uuid']:t for t in B[kind]};b={t['uuid']:t for t in N[kind]}
 for uid in sorted(set(a)|set(b)):
  aa=a.get(uid);bb=b.get(uid)
  if aa==bb:continue
  if kind=='footprints' and aa and bb:
   old={k:aa[k] for k in ['xy_nm','angle','layer']};new={k:bb[k] for k in ['xy_nm','angle','layer']}
   if old==new:continue # local-library namespace is metadata, reported separately.
  else:old=aa;new=bb
  rows.append({'object_kind':kind,'UUID':uid,'net_or_ref':(bb or aa).get('net',(bb or aa).get('ref','')),'action':'新增' if aa is None else '删除' if bb is None else '几何调整','old_native':json.dumps(old,ensure_ascii=False),'new_native':json.dumps(new,ensure_ascii=False),'reason_source':'accepted_sequence.json +accepted_patches; metadata normalization separately inCONSISTENCY_R1'})
with (F/'reports/全部铜与布局对象变更表.csv').open('w',encoding='utf-8-sig',newline='') as file:
 wr=csv.DictWriter(file,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
# Compare all finite placement lower bounds and state conflict gate before routing.
table=[]
for key in ['A','B','C']:
 q=places[key]
 for net,m in q['geometric_lower_bounds'].items():table.append({'candidate':key,'net':net,**m,'constraint_gate':'通过并实施局部比较' if key=='A' else '装配/铜间距冲突淘汰；未构建走线，数值不是实际路径'})
with (F/'reports/候选各网络布局下界比较.csv').open('w',encoding='utf-8-sig',newline='') as file:
 wr=csv.DictWriter(file,fieldnames=list(table[0]));wr.writeheader();wr.writerows(table)
# Potential-return removal screen for final DP alternatives; no undocumented edits.
pd=read(F/'evidence/post_cleanup_alternatives.json');ground={s:unary_union([shape(f) for f in final['features'] if f['net']=='GND' and f['side']==s]) for s in ['top','bottom']};crit=['MCU_RESET_N','MCU_WDI','WDI','WDT_OK','ARM_CLK','RUN_CLR_N','POR_RAW_N','POWER_OK','RUN_LATCH_Q','MCU_STEP','STEP_LATCHED','PUL_GATED','MCU_DIR','HOLD_ENABLE','I2C_SDA','I2C_SCL'];pp=[]
for f in final['features']:
 if f['kind']=='track' and f['net'] in crit:
  line=LineString([f['a'],f['b']]);c=max(1,math.ceil(line.length/.08));pp.extend(line.interpolate(line.length*i/c).coords[0] for i in range(c+1))
ap=points(np.array(pp));oldg=unary_union(list(ground.values()));old=distance(ap,oldg);reviews=[]
for q in pd['chains']:
 its=[t for t in pd['items'] if t['net']==q['net'] and t['side']==q['side']];cut=unary_union([LineString([t['a'],t['b']]).buffer(t['width']/2+.25,quad_segs=16) for t in its]);newg=unary_union([ground[q['side']].difference(cut),ground['top' if q['side']=='bottom' else 'bottom']]);change=float(max(distance(ap,newg)-old));removed=ground[q['side']].intersection(cut).area
 reviews.append(q|{'estimated_new_clearance_intersection_with_GND_mm2':removed,'predicted_max_critical_same_point_reference_loss_mm':change,'decision':'未采用：额外走线扫掠侵入已保护的关键返回区域；保留已通过方案。' if change>1e-5 else '未采用：有限候选的改动不改变可见主干复杂度；量化/支路接入及现有返回优先保留。同等工程结果保留原布局。','method_limit':'Read-only swept-clearance screen without refill; overestimates combined same-net proposals, not final-candidate performance evidence.'})
(F/'validation/POST_CLEANUP_candidate_dispositions.json').write_text(json.dumps({'source_pcb_sha256':N['sha256'],'alternatives':reviews,'no_global_optimum_claim':True},ensure_ascii=False,indent=2),encoding='utf8')
print('Comparison, candidate, actualsilk figures and full change tables generated',len(rows),'changed objects')
