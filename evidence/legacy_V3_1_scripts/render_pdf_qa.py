"""Render every final PDF page; visual approval must be supplied after inspection."""
from pathlib import Path
import subprocess,json,hashlib,argparse,shutil
from PIL import Image,ImageDraw,ImageFont
from pypdf import PdfReader
import pdfplumber
F=Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser();a.add_argument('--output',required=True);a.add_argument('--poppler',default=shutil.which('pdftoppm') or r'C:\Users\AAA\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe');args=a.parse_args()
O=Path(args.output).resolve();O.mkdir(parents=True,exist_ok=True)
items=[('report',F/'reports/CurtainDrive_V3_2_2L_工程设计与核验报告.pdf'),('schematic',F/'schematic/CurtainDrive_V3_2_2L.pdf'),('PTH',F/'manufacturing/Gerber/CurtainDrive_V3_2_2L-PTH-drl_map.pdf'),('NPTH',F/'manufacturing/Gerber/CurtainDrive_V3_2_2L-NPTH-drl_map.pdf')]
font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',20);rows=[]
for name,p in items:
 dest=O/name;dest.mkdir(exist_ok=True)
 subprocess.run([args.poppler,'-png','-r','110',str(p),str(dest/'page')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 pics=sorted(dest.glob('page-*.png'),key=lambda p:int(p.stem.rsplit('-',1)[-1]));doc=PdfReader(p);assert len(pics)==len(doc.pages)
 bounds=[]
 with pdfplumber.open(p) as d:
  for i,page in enumerate(d.pages):
   words=page.extract_words();outside=[w for w in words if w['x0']<-.5 or w['x1']>page.width+.5 or w['top']<-.5 or w['bottom']>page.height+.5]
   bounds.append({'page':i+1,'words':len(words),'outside_page_text':len(outside),'size_pt':[page.width,page.height]});assert not outside,(name,i,outside[:2])
 for start in range(0,len(pics),6):
  canvas=Image.new('RGB',(1140,960),'#dce4e8');draw=ImageDraw.Draw(canvas)
  for j,path in enumerate(pics[start:start+6]):
   im=Image.open(path).convert('RGB');im.thumbnail((360,425));canvas.paste(im,((j%3)*380+(380-im.width)//2,(j//3)*480+40));draw.text(((j%3)*380+15,(j//3)*480+10),f'{name} page{start+j+1}',font=font,fill='#203645')
  canvas.save(dest/f'contact_{start//6+1}.png')
 rows.append({'file':p.relative_to(F).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pages':len(pics),'all_pages_rendered':True,'bounds':bounds,'contact_sheets':(len(pics)+5)//6,'visual_review':'PENDING'})
out={'source_pcb_sha256':hashlib.sha256((F/'project/CurtainDrive_V3_2_2L.kicad_pcb').read_bytes()).hexdigest(),'PDFs':rows,'physical_sample_review':False}
(F/'validation/PDF_all_pages_QA.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print('Rendered31 pages. Inspect pages and update visual_review only after actual review.')
