from pathlib import Path
import pcbnew,json,hashlib,sys
R=Path(__file__).resolve().parents[2];O=Path(sys.argv[1]);W=O
path=Path(sys.argv[1]);W=Path(sys.argv[2]);W.mkdir(parents=True,exist_ok=True);b=pcbnew.LoadBoard(str(path));features=[];bridges=[];parts=[]
def xy(p):return [pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)]
def chain(c):return [xy(c.CPoint(i)) for i in range(c.PointCount())]
def addpoly(poly,side,net,key):
    for i in range(poly.OutlineCount()):features.append({'kind':'polygon','side':side,'net':net,'key':key,'outline':chain(poly.COutline(i)),'holes':[chain(poly.CHole(i,j)) for j in range(poly.HoleCount(i))]})
for f in b.GetFootprints():
    if f.GetReference().startswith("H"):continue
    pads=[]
    for p in f.Pads():
        key=f.GetReference()+'.'+p.GetNumber();net=p.GetNetname() or 'NC:'+key
        sides=[]
        for side,k in [('top',pcbnew.F_Cu),('bottom',pcbnew.B_Cu)]:
            if not p.GetLayerSet().Contains(k):continue
            buf=pcbnew.SHAPE_POLY_SET();p.TransformShapeToPolygon(buf,k,0,pcbnew.FromMM(.001),pcbnew.ERROR_INSIDE);addpoly(buf,side,net,key);sides.append(side)
        if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH and len(sides)==2:bridges.append(key)
        pads.append({'pin':p.GetNumber(),'uuid':p.m_Uuid.AsString(),'net':p.GetNetname(),'xy':xy(p.GetPosition()),'drill':xy(p.GetDrillSize()),'angle':p.GetOrientationDegrees(),'type':int(p.GetAttribute()),'shape':int(p.GetShape()),'sides':sides})
    fields={t.GetName():t.GetText() for t in f.GetFields()}
    parts.append({'ref':f.GetReference(),'value':f.GetValue(),'footprint':str(f.GetFPID().GetLibItemName()),'mpn':fields.get('Manufacturer Part'),'rating':fields.get('Voltage Rating'),'x':pcbnew.ToMM(f.GetPosition().x),'y':pcbnew.ToMM(f.GetPosition().y),'side':'bottom' if f.GetLayer()==pcbnew.B_Cu else 'top','angle':f.GetOrientationDegrees(),'path':f.GetPath().AsString(),'pads':pads})
for t in b.GetTracks():
    key=t.m_Uuid.AsString();net=t.GetNetname()
    if isinstance(t,pcbnew.PCB_VIA):
        bridges.append(key)
        for side,k in [('top',pcbnew.F_Cu),('bottom',pcbnew.B_Cu)]:features.append({'kind':'circle','side':side,'net':net,'key':key,'xy':xy(t.GetPosition()),'radius':pcbnew.ToMM(t.GetWidth(k))/2,'drill_radius':pcbnew.ToMM(t.GetDrillValue())/2})
    else:features.append({'kind':'track','side':'top' if t.GetLayer()==pcbnew.F_Cu else 'bottom','net':net,'key':key,'a':xy(t.GetStart()),'b':xy(t.GetEnd()),'width':pcbnew.ToMM(t.GetWidth())})
for z in b.Zones():
    if z.GetIsRuleArea():continue
    for side,k in [('top',pcbnew.F_Cu),('bottom',pcbnew.B_Cu)]:
        if z.GetLayerSet().Contains(k):addpoly(z.GetFilledPolysList(k),side,z.GetNetname(),'zone:'+z.m_Uuid.AsString())
outline=pcbnew.SHAPE_POLY_SET();b.GetBoardPolygonOutlines(outline,False)
d={'source_pcb_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'features':features,'plated_bridges':bridges,'parts':parts,'board_outline':chain(outline.COutline(0))}
(W/'copper_geometry.json').write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')),encoding='utf8');print('Independent exact copper polygons exported:',len(features),'features;',len(parts),'parts')
