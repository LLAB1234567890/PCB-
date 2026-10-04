"""Bind offline evidence to frozen native sources; never upgrade physical acceptance."""
from pathlib import Path
import json,csv,hashlib,datetime,zipfile
F=Path(__file__).resolve().parents[1];V=F/'validation';E=F/'evidence';P=F/'project'
read=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
H=sha(P/'CurtainDrive_V3_2_2L.kicad_pcb');S={p.name:sha(p) for p in P.glob('*.kicad_sch')};assert len(S)==11
checks=[]
def record(name,condition):
 assert condition,name
 checks.append({'check':name,'result':'PASS'})
def bound(path,sch=False):
 d=read(path)
 if 'source_pcb_sha256' in d:record(path.name+' PCB source',d['source_pcb_sha256']==H)
 if sch:record(path.name+' all11 schematic sources',d['source_schematic_sha256']==S)
 return d
freeze=bound(V/'frozen_sources.json',True)
record('preserved baseline SHA',freeze['baseline_pcb_sha256']=='46f10d5db1eadab9c5d524b781945b204c26d077fb969e462897530ded63045b')
record('native project/root/PCB same basename',all((P/('CurtainDrive_V3_2_2L'+s)).is_file() for s in ['.kicad_pro','.kicad_sch','.kicad_pcb']))
drc=read(V/'PCB_R1_DRC.json');erc=read(V/'SCH_R1_ERC.json')
record('configured native findings all zero',not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity'] and not any(s['violations'] for s in erc['sheets']))
allerc=read(V/'SCH_R1_all_categories_review.json');ctx=bound(V/'SCH_R1_all_categories_context.json',True);styles=bound(V/'SCH_R1_style_warning_dispositions.json',True)
record('all ERC classes reviewed',not allerc['ignored_checks'] and ctx['errors']==0 and len(styles['enabled_category_warnings'])==31)
r1=bound(V/'PCB_R1_geometry_fixed_and_native.json',True);r2=bound(V/'PCB_R2_actual_copper_and_returns.json',True);r3=bound(V/'PCB_R3_system_assembly_thermal_support.json',True)
record('PCB three independent rounds',r1['result']=='PASS' and r2['result']=='PASS_WITH_RECORDED_REFERENCE_LIMITS' and r3['result']=='OFFLINE_REVIEW_COMPLETE_PHYSICAL_PENDING')
record('fixed boundaries/poses/faces/MPN/GPIO/count/topology',not r1['fixed_pose_and_face_differences'] and not r1['component_MPN_value_count_GPIO_topology_differences'] and r1['board_outline_and_six_holes_unchanged'] and r1['antenna_rule_areas_unchanged'])
record('current native track/via counts',r1['geometry_counts']['final_tracks']==2107 and r1['geometry_counts']['final_vias']==489)
cg=bound(V/'routing/copper_gate.json');cu=bound(V/'routing/copper_geometry.json')
record('all469 pads and every conductor independently connected',cg['required_unique_pad_count']==469 and not cg['opens'] and not cg['shorts'] and not cg['orphan_conductors'])
record('CASE six effective faces >=baseline',all(a['final']>=a['baseline']-1e-6 for sides in r2['CASE_separate_effective_area'].values() for a in sides.values()))
record('GND/CASE islands not counted as useful area',all(abs(a)<1e-8 for sides in cg['floating_area_mm2'].values() for a in sides.values()))
sc2=bound(V/'SCH_R2_component_and_intent.json',True);sc3=bound(V/'SCH_R3_dynamic_fault_and_rearm.json',True)
record('schematic three rounds pin/spec/fault intent',not sc2['issues'] and sc3['static_vectors']==16384 and not sc3['static_failures'] and len(sc3['fault_sequences'])==22)
record('fault recovery requires new ARM on every inhibited fault',all(q['recovery_requires_new_ARM'] for q in sc3['fault_sequences'] if q['fault_inhibits_current_direction']))
record('EN/HIGHhold/fallingedge independent boundary model',len(sc3['watchdog_edge_sequences'])==3 and all(q[k] for q in sc3['watchdog_edge_sequences'] for k in ['HIGH_hold_never_feeds','50ms_descending_edge_period_alive','missing_descending_edges_times_out','EN_LOW_independently_inhibits']))
record('firmware and physical tests explicitly unexecuted',sc3['firmware_implemented'] is False and sc3['physical_tests_executed'] is False)
c1=bound(V/'CONSISTENCY_R1_native_and_netlist.json',True);c2=bound(V/'CONSISTENCY_R2_manufacturing.json',True)
record('consistency round1 native wires/nonwire/netlist/PCB',c1['result']=='PASS' and not c1['PCB_schematic_pin_net_differences'] and len(c1['native_schematic_pages'])==11 and all(q['normalized_non_wire_equal'] and q['wire_coverage_symmetric_difference_mm']<1e-8 and q['title_revision']=='V3.1' and 'V3.1' in q['title'] for q in c1['native_schematic_pages']))
record('consistency round2 fabrication/CPL/BOM',not c2['issues'] and not c2['CPL_source_differences'] and c2['CPL_count']==130 and c2['SMT_BOM_component_count']==130 and c2['Manual_PCB_components']==21 and c2['native_drill_count']==596 and c2['drill_differences']['one_to_one_matches']==596 and not c2['drill_differences']['missing'] and not c2['drill_differences']['extra'])
record('current manufacturing source netlist',c2['source_netlist_sha256']==sha(V/'routing/schematic.net'))
record('native/Gerber copper <3um quantization tolerance',all(q['extra_beyond_3um_mm2']==0 and q['missing_beyond_3um_mm2']==0 for q in c2['copper_parity'].values()))
for name,value in c2['file_sha256'].items():record('Gerber '+name,sha(F/'manufacturing/Gerber'/name)==value)
for name,value in c2['assembly_file_sha256'].items():record('Assembly '+name,sha(F/'manufacturing'/name)==value)
micro=bound(V/'MICRO_243_disposition.json',True);geom=bound(V/'GEOMETRY_remaining_exceptions.json',True);silk=bound(V/'SILK_native_review.json')
record('all243 original objects individually disposed',micro['strict_count']==240 and micro['exact_boundary_count']==3 and len(micro['items'])==243)
record('necessary remaining short/angle exceptions explicit',len(geom['remaining_short_items'])==148 and geom['integer_nonstandard_angle_count']==537 and geom['zero_length']==0 and not geom['exact_duplicate_segments'])
record('two silk reading directions',silk['two_reading_directions'] and sum(silk['angle_counts'].values())==200 and not silk['native_silk_to_pad_DRC_violations'])
power=bound(V/'POWER_voltage_and_resistance_review.json',True);sheet=read(V/'DC_sheet_paired.json')
record('paired actual Cu DC methods bound',sheet['paired']['V3.1']['source_pcb_sha256']==H and sheet['paired']['V3']['source_pcb_sha256']==freeze['baseline_pcb_sha256'])
record('unmet power target not presented as achieved',power['forward_005ohm_target_met'] is False)
thermal=bound(V/'THERMAL_six_paired_cases.json',True);tr=bound(F/'thermal/results.json');tg=bound(F/'thermal/board_geometry.json')
record('six same-algorithm/same-input thermal cases',len(thermal['cases'])==6 and thermal['same_source_algorithm'] and thermal['same_load_material_and_boundary_parameters'] and tr['inputs_sha256']==sha(F/'thermal/inputs.json') and all(q['energy_relative_error']<.0001 for q in thermal['cases']))
mass=read(F/'mechanical/bare_PCB_support_analysis.json');mech=bound(F/'mechanical/geometry_validation.json');cad=bound(V/'CAD_export_readback.json');fixedcad=bound(V/'CAD_fixed_geometry_parity.json')
record('mass/current fixed supports mechanically legal',mass['pcb_sha256']==H and all(q['patch_inside_board'] and q['blocked_overlap_mm2']==0 and q['minimum_clearance_from_inflated_bottom_envelopes_mm']>0 for q in mass['support_patch_checks']))
record('CAD native/STEP/STL readback and fixed body parity',not cad['issues'] and not mech['interferences'] and all(q['valid'] for q in cad['native_shape_checks']) and fixedcad['fixed_case_and_button_pods_and_supports_unchanged'])
for name,value in cad['file_sha256'].items():record('CAD '+name,sha(F/'mechanical'/name)==value)
replay=read(V/'ACCEPTED_replay_byte_parity.json');record('accepted sequence actual byte-identical replay',replay['byte_identical_final'] and replay['replay_final_sha256']==H and replay['final_expected_sha256']==H)
pdf=bound(V/'PDF_all_pages_QA.json');record('all4 PDFs31 pages actually visually reviewed',len(pdf['PDFs'])==4 and sum(q['pages'] for q in pdf['PDFs'])==31 and all(q['all_pages_rendered'] and q['visual_review']=='PASS' and q['sha256']==sha(F/q['file']) and not any(r['outside_page_text'] for r in q['bounds']) for q in pdf['PDFs']))
for q in pdf['PDFs']:
 for name,value in q['contact_preview_sha256'].items():record('PDF preview '+name,sha(F/name)==value)
textqa=read(V/'report_PDF_text_QA.json');record('report18page text QA',textqa['pages']==18 and not textqa['issues'] and textqa['all_titles_found_on_expected_page'])
fab=bound(V/'FABRICATION_ZIP_validation.json');record('fabrication ZIP hashes/CRC',fab['CRC'] and fab['member_byte_hashes_equal_source'] and fab['zip_sha256']==sha(F/'manufacturing/CurtainDrive_V3_2_2L_Gerber.zip'))
with zipfile.ZipFile(F/'manufacturing/CurtainDrive_V3_2_2L_Gerber.zip') as z:record('fabrication ZIP current CRC',z.testzip() is None)
with (F/'reports/样机验收表.csv').open(encoding='utf-8-sig',newline='') as f:tests=list(csv.DictReader(f))
record('24 prototype cases remain unexecuted',len(tests)==24 and all(q['状态']=='未执行' and not q['通过/未通过'] for q in tests))
record('prototype measurement procedures supplied',(F/'reports/样机测量步骤与判据.md').is_file())
dependencies={p.relative_to(F).as_posix():sha(p) for p in sorted(F.rglob('*')) if p.is_file() and p.name not in ['OFFLINE_RELEASE_ACCEPTANCE.json','file_manifest.json'] and '__pycache__' not in p.parts}
out={'revision':'V3.1','state':'OFFLINE_ENGINEERING_AND_MANUFACTURING_REVIEW_COMPLETE_WITH_RECORDED_LIMITS','physical_acceptance':'NOT_EXECUTED','firmware_implemented':False,'source_pcb_sha256':H,'source_schematic_sha256':S,'generated_local':datetime.datetime.now().isoformat(timespec='seconds'),'checks':checks,'PCB_rounds':3,'schematic_rounds':3,'consistency_rounds':2,'engineering_limits':['0.05ohm progressive goal unmet;0.5A reviewed calculation envelope requires actual contact/ripple/current/LDO temperature measurements;0.8A combined worst sensitivity insufficient.','LocalRESET nearestGND change+0.063mm expressly reviewed; retained WDI/ARM cross-layer return gaps are not EMC proof.','Six-case temperature changes below model uncertainty; lumpedDevKit/adverse~89.4C is neither junction nor local ambient.','Unknown SETlamp/rear, PA12/reference material/contact, real wire lengths and USB/print fit require prototype acceptance.','Stocklibrary placement polarity/rotational offset/order preview pending; electrical behaviour/torque/stopdistance and EMC not tested.'],'baseline_backup_manifest':'evidence/baseline_manifest.json','mirror_and_full_archive_proof':'Sibling CurtainDrive_V3_2_2L_delivery_validation.json, generated after package closure to avoid self-referential hashes.','dependency_sha256':dependencies,'no_absolute_optimum_or_production_claim':True}
(V/'OFFLINE_RELEASE_ACCEPTANCE.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print('Offline closure PASS',len(checks),'checks /',len(dependencies),'bound dependencies / physical24 unexecuted',H)
