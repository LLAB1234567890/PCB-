from pathlib import Path
import pcbnew as p,json,sys
file=Path(sys.argv[1]);out=Path(sys.argv[2]);b=p.LoadBoard(str(file));fps=[];xy=lambda a:[p.ToMM(a.x),p.ToMM(a.y)]
for f in b.GetFootprints():
 ee=[g.GetBoundingBox() for g in f.GraphicalItems() if g.GetLayer() in [p.F_CrtYd,p.B_CrtYd]]
 if not ee:ee=[g.GetBoundingBox() for g in f.GraphicalItems() if g.GetLayer() in [p.F_Fab,p.B_Fab]]
 bb=[min(xy(e.GetPosition())[0] for e in ee),min(xy(e.GetPosition())[1] for e in ee),max(xy(e.GetEnd())[0] for e in ee),max(xy(e.GetEnd())[1] for e in ee)] if ee else None
 fps.append({'ref':f.GetReference(),'xy':xy(f.GetPosition()),'angle':f.GetOrientationDegrees(),'side':'bottom' if f.GetLayer()==p.B_Cu else 'top','bbox':bb})
kk=[]
for z in b.Zones():
 if z.GetIsRuleArea():kk.append({'pts':[xy(z.Outline().COutline(0).CPoint(i)) for i in range(z.Outline().COutline(0).PointCount())],'layers':['top' if k==p.F_Cu else 'bottom' for k in [p.F_Cu,p.B_Cu] if z.GetLayerSet().Contains(k)],'tracks':z.GetDoNotAllowTracks(),'vias':z.GetDoNotAllowVias(),'pads':z.GetDoNotAllowPads()})
out.mkdir(exist_ok=True,parents=True);(out/'placement_geometry.json').write_text(json.dumps({'footprints':fps,'keepouts':kk},indent=2),encoding='utf8')
print('Placement and keepout geometry exported')
