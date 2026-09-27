"""Render local report/source pages for visual QA only."""
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageDraw

root=Path(__file__).resolve().parent
out=root/'visual-review'
out.mkdir(exist_ok=True)
sources=[('proposal',Path('C:/Users/ASUS TUF/Desktop/ISP_Project_Proposal .pdf'),[18,30]),
         ('example',Path('C:/Users/ASUS TUF/Desktop/ISP-04.pdf'),[23]),
         ('report',root/'StegaShield_Group60_Progress_Report.pdf',None)]
for name,path,pages in sources:
    with pdfium.PdfDocument(str(path)) as doc:
        selected=pages if pages is not None else range(len(doc))
        thumbs=[]
        for n in selected:
            page=doc[n]; bitmap=page.render(scale=1)
            im=bitmap.to_pil().convert('RGB')
            if pages is not None: im.save(out/f'{name}-{n+1}.png')
            im.thumbnail((280,396))
            tile=Image.new('RGB',(300,425),'#e5eeea')
            tile.paste(im,((300-im.width)//2,20))
            ImageDraw.Draw(tile).text((12,407),f'{name} page {n+1}',fill='black')
            thumbs.append(tile)
            bitmap.close();page.close()
        if pages is None:
            for start in range(0,len(thumbs),12):
                group=thumbs[start:start+12]
                sheet=Image.new('RGB',(1200,425*((len(group)+3)//4)),'white')
                for i,tile in enumerate(group):sheet.paste(tile,((i%4)*300,(i//4)*425))
                sheet.save(out/f'report-contact-{start//12+1}.png')
