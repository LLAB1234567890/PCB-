from pathlib import Path
import json,html
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader

W=Path(__file__).resolve().parents[1];R=W/'reports';model=json.loads((R/'document_model.json').read_text(encoding='utf8'))
pdfmetrics.registerFont(TTFont('YaHei',r'C:\Windows\Fonts\msyh.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('YaHeiBold',r'C:\Windows\Fonts\msyhbd.ttc',subfontIndex=0))
body=ParagraphStyle('body',fontName='YaHei',fontSize=9.5,leading=14.1,wordWrap='CJK',spaceAfter=8,textColor=colors.HexColor('#203344'))
head=ParagraphStyle('head',parent=body,fontName='YaHeiBold',fontSize=17,leading=24,spaceAfter=16,textColor=colors.HexColor('#163d55'))
cell=ParagraphStyle('cell',parent=body,fontSize=8.7,leading=12.2,spaceAfter=0)
cellhead=ParagraphStyle('cellhead',parent=cell,fontName='YaHeiBold',textColor=colors.white)
caption=ParagraphStyle('caption',parent=body,fontSize=8.4,leading=12,textColor=colors.HexColor('#536b7b'),spaceAfter=10)
width=A4[0]-82
def p(t,s=body):return Paragraph(html.escape(str(t)).replace('\n','<br/>'),s)
story=[]
for num,page in enumerate(model['pages']):
 if num:story.append(PageBreak())
 story.append(p(page['title'],head))
 for b in page['blocks']:
  if b['type']=='paragraph':story.append(p(b['text']))
  elif b['type']=='table':
   w=b.get('widths') or [1/len(b['header'])]*len(b['header'])
   rows=[[p(x,cellhead) for x in b['header']]]+[[p(x,cell) for x in row] for row in b['rows']]
   t=Table(rows,colWidths=[width*x/sum(w) for x in w],hAlign='LEFT',repeatRows=1)
   t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#27566e')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#eef4f7'),colors.white]),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#27566e')),('LINEBELOW',(0,1),(-1,-1),.35,colors.HexColor('#d4e0e7'))]))
   story += [t,Spacer(1,10)]
  else:
   f=R/b['path'];iw,ih=ImageReader(str(f)).getSize();scale=min(width/iw,246/ih)
   story.append(KeepTogether([Image(str(f),width=iw*scale,height=ih*scale),Spacer(1,3),p(b['caption'],caption)]))
def ornament(c,doc):
 c.saveState();c.setStrokeColor(colors.HexColor('#b9cdd9'));c.line(41,804,A4[0]-41,804)
 c.setFont('YaHei',8);c.setFillColor(colors.HexColor('#536b7b'));c.drawString(41,816,'CurtainDrive V3.1 | 原理 / PCB / 制造 / 机械 / 热力')
 c.line(41,34,A4[0]-41,34);c.drawString(41,21,'2026-10-03 | 离线设计核验，原型实测验收另列');c.drawRightString(A4[0]-41,21,str(doc.page))
 c.restoreState()
fn=R/'CurtainDrive_V3_2_2L_工程设计与核验报告.pdf'
doc=SimpleDocTemplate(str(fn),pagesize=A4,leftMargin=41,rightMargin=41,topMargin=48,bottomMargin=46,title='CurtainDrive V3.1 工程设计与核验报告',author='CurtainDrive Engineering',subject='Schematic, PCB, actual manufacturing parity, enclosure, support and thermal analysis')
doc.build(story,onFirstPage=ornament,onLaterPages=ornament)
pdf=PdfReader(fn);texts=[x.extract_text() or '' for x in pdf.pages]
expected=len(model['pages']);issues=[]
if len(pdf.pages)!=expected:issues.append({'page_count':len(pdf.pages),'expected':expected})
for i,x in enumerate(model['pages']):
 if i>=len(texts) or x['title'].replace(' ','') not in texts[i].replace(' ',''):issues.append({'page':i+1,'title_missing_or_shifted':x['title']})
qa={'pages':len(pdf.pages),'expected_pages':expected,'all_titles_found_on_expected_page':not issues,'extractable_characters':sum(map(len,texts)),'issues':issues,'visual_review_required':True}
(W/'validation/report_PDF_text_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf8')
print(qa)
