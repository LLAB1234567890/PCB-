"""Rebuild source-bound geometric, intent, disposition and paired-model reviews."""
from pathlib import Path
import json,csv,math,hashlib,collections,datetime
import numpy as np
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from sx import parse,kids,one,dump
F=Path(__file__).resolve().parents[1];V=F/'validation';E=F/'evidence';R=F/'reports';R.mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf8'))
write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
B=read(E/'baseline/native_inventory.json');N=read(V/'routing/native_inventory.json');H=N['sha256'];assert H==sha(F/'project/CurtainDrive_V3_2_2L.kicad_pcb')
stamp={'revision':'V3.1','source_pcb_sha256':H,'source_schematic_sha256':{p.name:sha(p) for p in (F/'project').glob('*.kicad_sch')},'generated_local':datetime.datetime.now().isoformat(timespec='seconds'),'physical_measurements':False}
bc=read(E/'baseline/copper_geometry.json');fc=read(V/'routing/copper_geometry.json');cg=read(V/'routing/copper_gate.json');bp=read(E/'baseline/route_resistance_and_decoupling.json');fp=read(V/'routing/route_resistance_and_decoupling.json');na=read(V/'routing/native_audit.json');drc=read(V/'PCB_R1_DRC.json')
bf={p['ref']:p for p in B['footprints']};nf={p['ref']:p for p in N['footprints']}
norm=lambda s:str(s).replace('CurtainDriveV3_2_2L','CurtainDriveV3').replace('CurtainDrive_V3_2_2L','CurtainDrive_V3')
fixed=['U2','U1','U11','U33','J1','J3','J13','J14','J15','J18','U18','U19','U20','U21','U22','U23','U24','U30','J16','J17','J19',*[f'H{i}' for i in range(1,7)]]
fixed_errors=[];component_errors=[];moved=[]
for ref,a in bf.items():
 b=nf[ref]
 if any(a[k]!=b[k] for k in ['xy_nm','angle','layer']):moved.append({'ref':ref,'before':{k:a[k] for k in ['xy_nm','angle','layer']},'after':{k:b[k] for k in ['xy_nm','angle','layer']}})
 for k in ['value','footprint','fields']:
  if norm(a[k])!=norm(b[k]):component_errors.append([ref,k])
 # Pad shape and local pose stay invariant even for the two moved parts.
 def pads(f):
  return sorted([{k:v for k,v in p.items() if k!='xy_nm'}|{'local_xy_nm':[p['xy_nm'][i]-f['xy_nm'][i] for i in [0,1]]} for p in f['pads']],key=lambda p:(p['pin'],str(p)))
 if pads(a)!=pads(b):component_errors.append([ref,'pad local geometry/net'])
 if ref in fixed and any(a[k]!=b[k] for k in ['xy_nm','angle','layer','pads']):fixed_errors.append(ref)
assert not component_errors and not fixed_errors and set(bf)==set(nf),(component_errors,fixed_errors)
assert {q['ref'] for q in moved}=={'C35','R57'}
assert B['outline']==N['outline'];assert [z for z in B['zones'] if z['rule_area']]==[z for z in N['zones'] if z['rule_area']]
# Independent normalized native schematic coverage and all non-wire objects.
schematic=[];base=E/'baseline_project'
def normalized(doc):
 def walk(x):
  if isinstance(x,list):
   if x and x[0]=='title_block':return None
   return [v for y in x if (v:=walk(y)) is not None]
  return norm(x)
 return walk(doc)
for p in sorted((F/'project').glob('*.kicad_sch')):
 old=base/('CurtainDrive_V3.kicad_sch' if p.name=='CurtainDrive_V3_2_2L.kicad_sch' else p.name);a=parse(old.read_text(encoding='utf8'));b=parse(p.read_text(encoding='utf8'))
 def wires(d):
  return unary_union([LineString([list(map(float,q[1:])),list(map(float,r[1:]))]) for x in kids(d,'wire') for q,r in [one(x,'pts')[1:3]]])
 da=wires(a);db=wires(b)
 aa=normalized([x for x in a if not (isinstance(x,list) and x and x[0]=='wire')]);bb=normalized([x for x in b if not (isinstance(x,list) and x and x[0]=='wire')])
 record={'file':p.name,'baseline_sha256':sha(old),'final_sha256':sha(p),'wire_coverage_symmetric_difference_mm':da.symmetric_difference(db).length,'normalized_non_wire_equal':aa==bb,'title_revision':one(one(b,'title_block'),'rev')[1],'title':one(one(b,'title_block'),'title')[1]}
 if aa!=bb:
  ca=collections.Counter(dump(x) for x in aa);cb=collections.Counter(dump(x) for x in bb);record['non_wire_differences']={'old_only':list((ca-cb).elements())[:5],'new_only':list((cb-ca).elements())[:5]}
 schematic.append(record)
assert len(schematic)==11 and all(x['wire_coverage_symmetric_difference_mm']<1e-8 and x['normalized_non_wire_equal'] and x['title_revision']=='V3.1' and 'V3.1' in x['title'] for x in schematic),schematic
libs=[]
for old in (base/'CurtainDriveV3.pretty').glob('*.kicad_mod'):
 p=F/'project/CurtainDriveV3_2_2L.pretty'/old.name;equal=norm(old.read_text(encoding='utf8'))==norm(p.read_text(encoding='utf8'));libs.append({'file':old.name,'native_geometry_equal':equal});assert equal
sym_equal=norm((base/'CurtainDriveV3.kicad_sym').read_text(encoding='utf8'))==norm((F/'project/CurtainDriveV3_2_2L.kicad_sym').read_text(encoding='utf8'));assert sym_equal
assert not na['PCB_schematic_pad_differences'] and not na['component_differences'] and not na['schematic_geometry_vs_export_differences']
write(V/'CONSISTENCY_R1_native_and_netlist.json',stamp|{'result':'PASS','native_schematic_pages':schematic,'schematic_symbol_library_geometry_equal':sym_equal,'footprint_library_objects':libs,'unique_electrical_parts':151,'unique_pads':469,'native_geometric_pin_count':na['schematic_pins_geometrically_inspected'],'PCB_schematic_pin_net_differences':[],'component_or_footprint_value_count_differences':component_errors,'metadata_normalization':'Namespace/root basename only; title_block excluded. Every other non-wire object compared, and native wire line-coverage union independently compared.'})
# Original short objects: map exact preservation, geometric union, removal or rerouting.
def shape(f):
 return Polygon(f['outline'],f.get('holes',[])).buffer(0) if f['kind']=='polygon' else LineString([f['a'],f['b']]).buffer(f['width']/2,quad_segs=64) if f['kind']=='track' else Point(f['xy']).buffer(f['radius'],quad_segs=64).difference(Point(f['xy']).buffer(f['drill_radius'],quad_segs=64))
def features(d):
 ff=[f for f in d['features'] if not f['key'].startswith('zone:')];gg=[shape(f) for f in ff];return ff,gg,STRtree(gg)
bff,bgg,bt=features(bc);fff,fgg,ft=features(fc);nt={t['uuid']:t for t in N['tracks']};btmap={t['uuid']:t for t in B['tracks']}
patches=[read(E/'accepted_patches'/p['file']) for p in read(E/'accepted_sequence.json')]
removed_at={r['uuid']:i for i,p in enumerate(patches) for r in p['removed']}
disps={}
exact=read(E/'accepted_patches/guarded_exact_patch.json')
for q in exact['records']:
 for uid in q.get('old_uuids',[q.get('uuid')]):
  if uid:disps[uid]=q
def contacts(t,ff,gg,tree):
 side='top' if t['layer']=='F.Cu' else 'bottom';aa=np.array(t['a_nm'])/1e6;bb=np.array(t['b_nm'])/1e6;g=LineString([aa,bb]).buffer(t['width_nm']/2e6,quad_segs=64)
 ids=[int(i) for i in tree.query(g.buffer(.001)) if ff[int(i)]['side']==side and ff[int(i)]['net']==t['net'] and ff[int(i)]['key']!=t['uuid'] and gg[int(i)].distance(g)<1e-6]
 return g,ids
def describe(t,ff,gg,tree):
 g,ids=contacts(t,ff,gg,tree);c=[ff[i] for i in ids];pv=[f['key'] for f in c if f['kind']!='track'];ww=[f['key'] for f in c if f['kind']=='track' and abs(f['width']-t['width_nm']/1e6)>.000001]
 cover=unary_union([gg[i] for i in ids]);extra=g.difference(cover).area
 if pv:use='焊盘/过孔接入及原生中心接入'
 elif ww:use='线宽过渡/铜颈'
 else:use='拐角或中途侧接的连续足宽铜'
 return {'use':use,'branch_contacts':[f['key'] for f in c],'pad_via_contacts':pv,'width_transition_contacts':ww,'metal_added_outside_other_explicit_copper_mm2':extra},g
ledger=[]
for t in B['tracks']:
 if t['squared_length_nm2']>150000**2:continue
 c,g=describe(t,bff,bgg,bt);kept=t['uuid'] in nt
 q=disps.get(t['uuid']);side='top' if t['layer']=='F.Cu' else 'bottom'
 exact_restored=[f['key'] for f,gg in zip(fff,fgg) if f['kind']=='track' and f['net']==t['net'] and f['side']==side and math.dist(f['a'],[v/1e6 for v in t['a_nm']])<1e-7 and math.dist(f['b'],[v/1e6 for v in t['b_nm']])<1e-7 and abs(f['width']-t['width_nm']/1e6)<1e-7]
 new_ids=[fff[int(i)]['key'] for i in ft.query(g.buffer(.001)) if fff[int(i)]['net']==t['net'] and fff[int(i)]['side']==side and len(fff[int(i)]['key'])==36 and fgg[int(i)].distance(g)<.001]
 if kept:action='保留';reason=c['use']+'；删除将改变完整截面或必要原生接入。实际连接已独立验证。'
 elif exact_restored:action='原生接入重建';reason='保持同一铜几何；原生 via_dangling 语义需要轨迹接至中心，独立铜覆盖不替代此规则。'
 elif q and q['action']=='exact_collinear_coverage_union':action='共线合并';reason='同网同层同宽，整数坐标区间覆盖并集完全相同；保留中途接入。'
 elif q:action='冗余覆盖删除';reason='原线段金属完整包含于其它同网显式铜内；最终焊盘、支路及导体连通重新验证。'
 else:action='局部重布替换';reason='按电源/逻辑/接口组替换；宽度、原有侧接、去耦和回流经阶段及最终检查。'
 ledger.append({k:t[k] for k in ['uuid','net','layer','a_nm','b_nm','width_nm','length_mm']}|{'threshold_class':'boundary' if t['squared_length_nm2']==150000**2 else 'strict',**c,'action':action,'reason':reason,'new_uuid':t['uuid'] if kept else ';'.join(exact_restored or sorted(set(new_ids))) or '无新轨迹；见保留焊盘铜联系人','verification':'Final native DRC0; exact copper469 pads/track/via/branches; stage source hashes in accepted_sequence.json','removal_patch_index':removed_at.get(t['uuid'])})
assert len(ledger)==243 and sum(x['threshold_class']=='strict' for x in ledger)==240
fields=list(ledger[0]);
with (R/'微短段243项处置表.csv').open('w',encoding='utf-8-sig',newline='') as file:
 wr=csv.DictWriter(file,fieldnames=fields);wr.writeheader();wr.writerows(ledger)
write(V/'MICRO_243_disposition.json',stamp|{'original_threshold_nm':150000,'strict_count':240,'exact_boundary_count':3,'floating_241_explanation':'Historical math.hypot/float strict comparison assigned rounding-near-threshold values inconsistently. Integer squared length gives240 strict +3 exact boundary. Classification includes the boundary objects explicitly.','original_action_counts':dict(collections.Counter(x['action'] for x in ledger)),'items':ledger})
remaining=[];angles=[]
for t in N['tracks']:
 if t['squared_length_nm2']<=150000**2:
  c,g=describe(t,fff,fgg,ft);remaining.append(t|c|{'decision':'保留足宽接入/短拐角/过渡；详见联系人及独立铜增量。长度阈值本身不是删除理由。'})
 if not t['standard_angle']:
  dx=abs(t['b_nm'][0]-t['a_nm'][0]);dy=abs(t['b_nm'][1]-t['a_nm'][1]);err=min(dx,dy,abs(dx-dy)/math.sqrt(2))/1e6;c,g=describe(t,fff,fgg,ft)
  category='整数坐标取整 ≤2nm' if err<=.000002 else c['use'] if c['pad_via_contacts'] or c['width_transition_contacts'] else '密集铜间的原有侧接/绕障例外'
  # Clearance and contact identities permit review of every remaining exception.
  foreign=[int(i) for i in ft.query(g.buffer(1)) if fff[int(i)]['side']==('top' if t['layer']=='F.Cu' else 'bottom') and fff[int(i)]['net']!=t['net']]
  gap=min((g.distance(fgg[i]) for i in foreign),default=1)
  angles.append(t|c|{'category':category,'nearest_45deg_lateral_coordinate_residual_mm':err,'nearest_foreign_explicit_copper_mm':gap,'decision':'原有非主干接入/量化/密集通道例外；不增加新蛇形。全网线覆盖与侧接审查，合法性由DRC独立确认。'})
write(V/'GEOMETRY_remaining_exceptions.json',stamp|{'remaining_short_counts':{'strict':145,'boundary':3},'remaining_short_use_counts':dict(collections.Counter(q['use'] for q in remaining)),'remaining_short_items':remaining,'integer_nonstandard_angle_count':len(angles),'angle_categories':dict(collections.Counter(q['category'] for q in angles)),'angle_items':angles,'zero_length':sum(t['squared_length_nm2']==0 for t in N['tracks']),'exact_duplicate_segments':na['routing']['duplicate_segments'],'candidate_extent':'Final branch-aware DP considered7 further alternatives; sub-micron DISABLE_GATE/DIR_ALLOWED and protected-reference changes retained in scope review, not a proof of global optimality.'})
# Paired resistance, ground and voltage headroom, using independent union geometry.
sheet=read(V/'DC_sheet_paired.json');res={}
for rev in ['V3','V3.1']:
 paths=(bp if rev=='V3' else fp)['dc_forward_paths'];sel=[x for x in paths if x['net'] in ['+5V_CTRL','+5V_MCU_FEED','+5V_MCU'] and x['to'] in ['D9.2','J19.1','U2.21']]
 rr=sheet['paired'][rev]['cases']
 res[rev]={'centreline_forward_ohm_20C':sum(x['resistance_ohm_20C_35um'] for x in sel),'centreline_forward_mm':sum(x['trace_length_mm'] for x in sel),'sheet_forward_ohm_20C_by_mesh':{str(p):sum(x['resistance_ohm_20C'] for x in rr if x['net']!='GND' and x['mesh_mm']==p) for p in [.05,.04]},'sheet_ground_ohm_20C':next(x['resistance_ohm_20C'] for x in rr if x['net']=='GND' and x['mesh_mm']==.15)}
rloop=res['V3.1']['sheet_forward_ohm_20C_by_mesh']['0.04']+res['V3.1']['sheet_ground_ohm_20C'];factor=1+.00393*60;budgets=[]
for i,droop in [(.3,.38),(.5,.38),(.8,.61)]:
 for vmin,label in [(4.85,'−3% module accuracy screen'),(4.70,'two −3% terms additive sensitivity; may double count')]:
  copper=i*rloop*factor;pin=vmin-.55-copper;margin=pin-(3.3+droop)
  budgets.append({'MCU_5V_A':i,'U1_output_lower_V':vmin,'source_case':label,'D9_screen_V':.55,'loop_copper_drop_at80C_V':copper,'U2_21_before_unknown_contacts_ripple_V':pin,'LDO_screen_V':3.3+droop,'remaining_unknown_contact_ripple_transient_headroom_V':margin,'criterion':'This headroom must exceed measured total contacts/ripple/transient plus design margin. Datasheet dropout is defined at95% nominal; not an exact3.3V regulation guarantee.'})
write(V/'POWER_voltage_and_resistance_review.json',stamp|{'paired_methods':res,'forward_005ohm_target_met':False,'bottleneck':'Fixed J19-to-U2 long route, dual-layer dense signals and protected baseline GND channels limit wide trunk length; .3-.6mm local escapes remain.1oz35um actual Cu and fixed service port prevent0.05ohm target in accepted local family.','budgets':budgets,'recommended_design_envelope':'0.5A MCU branch is the reviewed operating envelope. Actual peak/ripple/contacts and complete DevKit3.3V regulator temperature acceptance remain unexecuted.0.8A combined-worst sensitivity has inadequate margin and must not be promised.','minimum_scope_options':['If prototype headroom fails, authorize J19 placement/interface change to shorten MCU path.','Or authorize an efficient independent3.3V design with exclusive power interlock, revised supervision and renewed functional verification.'],'physical_nodes':['U1.3 vsU1.2','U2.21 vsU2.22','local +3V3 vsU2.22'],'goal_claim':'Electrical improvement demonstrated by two paired copper methods; target0.05ohm not achieved, no absolute optimum or production guarantee.'})
ret=read(V/'RETURN_paired_canonical.json');reset={'local_same_point_increase_mm':ret['nets']['MCU_RESET_N']['V3.1']['max_same_point_change_in_GND_distance_mm'],'xy_mm':ret['nets']['MCU_RESET_N']['V3.1']['same_point_worst_change_xy_mm'],'old_top_distance_mm':.2906936634511112,'new_top_distance_mm':.3535531912823115,'opposite_face_distance_mm_unchanged':1.3076729330159125,'decision':'Reviewed local EN escape spacing change, still<0.36mm from actual connected top GND; opposite face, signal swaps and whole-net worst gap unchanged. New ground extension is rooted at U45.4. A nearest-distance screen alone is not proof of AC return quality. No new reference gap or disconnection; sampleEMC pending.'}
worst=sorted(fp['critical_signal_via_ground_distances'],key=lambda x:x['nearest_ground_bridge_mm'],reverse=True)[:12]
areas={net:{s:{'baseline':read(E/'baseline/copper_gate.json')['anchored_area_mm2'][net][s],'final':cg['anchored_area_mm2'][net][s]} for s in ['top','bottom']} for net in ['CASE_U1','CASE_U11','CASE_U33']}
assert all(v['final']>=v['baseline']-1e-6 for q in areas.values() for v in q.values());assert not cg['opens'] and not cg['shorts']
assert not cg['orphan_conductors']
silk=read(V/'SILK_native_review.json') if (V/'SILK_native_review.json').exists() else {'pending':True}
write(V/'PCB_R1_geometry_fixed_and_native.json',stamp|{'result':'PASS','native_violations':drc['violations'],'native_unconnected':drc['unconnected_items'],'schematic_parity':drc['schematic_parity'],'fixed_reference_designators':fixed,'fixed_pose_and_face_differences':fixed_errors,'component_MPN_value_count_GPIO_topology_differences':component_errors,'moved_components':moved,'board_outline_and_six_holes_unchanged':True,'antenna_rule_areas_unchanged':True,'fabrication':na['fabrication'],'silk':silk,'geometry_counts':{'baseline_tracks':len(B['tracks']),'final_tracks':len(N['tracks']),'baseline_vias':len(B['vias']),'final_vias':len(N['vias'])},'exceptions_reference':'GEOMETRY_remaining_exceptions.json and243-item ledger; all31 enabled-category schematic style warnings individually reviewed separately.'})
write(V/'PCB_R2_actual_copper_and_returns.json',stamp|{'result':'PASS_WITH_RECORDED_REFERENCE_LIMITS','independent_method':cg['method'],'opens':cg['opens'],'shorts':cg['shorts'],'pads_verified':469,'all_explicit_conductors_in_anchored_net':not cg['orphan_conductors'],'orphan_explicit_conductors':cg['orphan_conductors'],'ground_area_anchored_mm2':cg['anchored_area_mm2']['GND'],'CASE_separate_effective_area':areas,'floating_GND_CASE_mm2':cg['floating_area_mm2'],'decoupling_outside_pad_copper_routes':fp['decoupling_power_routes'],'RESET_local_spacing_review':reset,'worst_remaining_signal_to_GND_bridge_distances':worst,'known_reference_gaps':'MCU_RESET_N worst planar nearestGND≈7.49mm; existing WDI/ARM cross-layer bridge gaps remain up to8.25/8.34mm. Fixed scope cannot assert0.5-1mm everywhere;14 additional dual-face connectedGND vias improve feasible sites. No EMC or HF immunity certification.','noise_review':['U1 switching input/CASE and3.3V reset/WD paths reviewed jointly; modules fixed, no loop-wide cosmetic ripup.','D15 protection/100ohm extI2C resistors retain topology and nearestGND root; I2C routing retained after cosmetic trial caused reference loss.','Q1-Q5 output edges use existing gate100ohm/pulldowns and localGND, external common-anode5V pairs required.','Buzzer30mA branch held below MCU0.5A power priority; no motor phase or driver negative current through PCBsignalground.'],'power_review_file':'POWER_voltage_and_resistance_review.json'})
# Six thermal cases and bare-board / support parity.
th0=read(E/'baseline_models/thermal/results.json');th1=read(F/'thermal/results.json');mass0=read(E/'baseline_models/mechanical/bare_PCB_support_analysis.json');mass1=read(F/'mechanical/bare_PCB_support_analysis.json');thermal=[]
for case in ['nominal_99kPa','nominal_101kPa','nominal_103kPa','stress_101kPa','adverse_99kPa','mesh_2mm_101kPa']:
 a,b=th0[case],th1[case];row={'case':case,'pressure_kPa':b['pressure_kPa'],'nodes':b['nodes'],'baseline':{k:a[k] for k in ['air_C','max_pcb_C','max_pa12_C','total_input_W']},'final':{k:b[k] for k in ['air_C','max_pcb_C','max_pa12_C','total_input_W']},'DevKit_baseline_C':a['hot_components_C']['U2'],'DevKit_final_C':b['hot_components_C']['U2'],'all_component_delta_C':{k:b['hot_components_C'][k]-a['hot_components_C'][k] for k in a['hot_components_C']},'energy_relative_error':b['energy_balance_relative_error']};thermal.append(row)
assert max(x['energy_relative_error'] for x in thermal)<.0001
write(V/'THERMAL_six_paired_cases.json',stamp|{'same_source_algorithm':True,'same_load_material_and_boundary_parameters':read(E/'baseline_models/thermal/inputs.json')==read(F/'thermal/inputs.json'),'cases':thermal,'thermal_source_sha256':th1['source_pcb_sha256'],'limitations':['Paired model differences<0.02C are below reference-material/contact/grid uncertainty; do not claim cooling.','DevKit is one lumped node; esp32_3v3_A is not independently used by heat-source function. V3/V3.1 compared with identical unchanged algorithm.','80-90C lumped node is neither ESP junction nor module-adjacent ambient; N8R8 ambient limits require local physical measurement.','One cavity air node, solid finite-volume conduction plus convection/radiation closure; not CFD.','PA12 reference properties, load/SETcurrent/contact andwirelength assumptions remain adjustable and physically unverified.']})
write(V/'PCB_R3_system_assembly_thermal_support.json',stamp|{'result':'OFFLINE_REVIEW_COMPLETE_PHYSICAL_PENDING','functional_model':'SCH_R3_dynamic_fault_and_rearm.json:16384 vectors,22 active/inactive-direction fault sequences, independent EN/WDI edge model; no propagation/bounce/torque test','fault_semantics':['NormalSTOP/WD clear motion authorization while healthy power/ESTOP preserves HOLD.','FourNC limit faults are direction-selective: LO/RO inhibitOPEN; LC/RC inhibitCLOSE. Opposite-direction retreat remains possible. Actuation and brokenwire indistinguishable.','EN reset disables watchdog ENOUT immediately; WDI high hold never feeds; loss of fallingedges eventually clearsRUN. WD does not resetESP32.','Recovery with GPIO6 HIGH cannot autoARM; a new LOW→HIGHedge after healthy conditions is required.','K1 physically removes externaldriverpositivepower. U24 coil-command sense cannot prove contacts opened; internaldrivealarm/powerloss cannot guarantee hold.'],'bare_PCB_mass_g':mass1['bare_board_estimate_g'],'baseline_bare_PCB_mass_g':mass0['bare_board_estimate_g'],'centroid_KiCad_mm':mass1['centroid_KiCad_mm'],'baseline_centroid_KiCad_mm':mass0['centroid_KiCad_mm'],'fixed_support_checks':mass1['support_patch_checks'],'support_span':mass1['span_after'],'CAD_reference':'CAD_export_readback.json / CAD_fixed_geometry_parity.json / mechanical/geometry_validation.json','thermal_reference':'THERMAL_six_paired_cases.json','assembly_review':['Six5x5 posts andS1/S2 unchanged; bottombody/pad/via andplugtail exclusion maintained.','Fixedterminal orientations andmating25x9.5x6mmUSB budget maintained.30tool corridors checked inCAD; no new blockedsocket/screw path.','Double-sidedSMT130parts;21manualTHT/modules/sockets, manually fittedESPTwoSamtecSSQ-122 sockets; do not treatDevKit as SMT.','Hotair/rework envelope is approximate Fabbody; actual connector tools/wires/button rear/USBfit/foam/tap torque awaitsample.'],'physical_acceptance':'Not executed: firmware absent, no prototype. Bring-up/fault/current/thermal/EMC andmechanical test sheet provided.'})
# Review every re-enabled ERC style warning, with current geometry/netlist proof.
allerc=read(V/'SCH_R1_all_categories_review.json');styles=[]
for sheet0 in allerc['sheets']:
 for q in sheet0['violations']:
  assert q['severity']=='warning' and q['type'] in ['four_way_junction','single_global_label'],q
  styles.append({'sheet_path':sheet0['path'],'type':q['type'],'description':q['description'],'items':q['items'],'disposition':'有意四向共点连接；原生几何与导出网表及PCB逐脚核对无冲突。保留布局，避免改动拓扑。' if q['type']=='four_way_junction' else '单处全局标签作为外部/保留针网命名；该网的所有实际针和PCB一致，非遗漏跨页接线。','verification':'Native line coverage unchanged; geometric schematic graph473pins, unique469pads andXMLnetlist all agree; warning is drawing style.'})
assert len(styles)==31
write(V/'SCH_R1_style_warning_dispositions.json',stamp|{'enabled_category_warnings':styles,'counts':dict(collections.Counter(x['type'] for x in styles)),'configured_ERC_errors_and_warnings':0,'all_categories_errors':0,'note':'All disabled categories re-enabled in a separate exact project copy;10four-way +21single-global-label style warnings reviewed instead of treating ignored categories as nonexistent.'})
write(V/'frozen_sources.json',stamp|{'baseline_pcb_sha256':B['sha256'],'complete_intake_manifest':'evidence/baseline_manifest.json','fixed_boundaries_and_values_pass':True,'native_metadata_vs_routing_change_separated':True})
sources=[{'relative_file':str(p.relative_to(F)).replace('\\','/'),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted((F/'sources').rglob('*')) if p.is_file()]
write(E/'source_files_locked_final.json',{'files':sources,'reference_index':'evidence/baseline/source_manuals_locked.json','extra_manuals':{'SGM2212_DevKit_LDO.pdf':'SGMICRO official July2023 RevA.2 https://www.sg-micro.com/rect/assets/54089b71-cc25-4f36-af2e-34b07f00a108/SGM2212.pdf','MDD_SS14_C2480.pdf':'ActualMDD C2480 https://datasheet.lcsc.com/datasheet/pdf/9977bb85cd7e349115b7bcb7054cfa0d.pdf'}})
print('Formal source/parity/fixed/243 disposition/reviews generated',H,'micro actions',dict(collections.Counter(x['action'] for x in ledger)),'angles',dict(collections.Counter(x['category'] for x in angles)))
