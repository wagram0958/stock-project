import re, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(r"E:\熊本")
outdir=Path(r"C:\Users\USER\Documents\Codex\2026-07-04\new-chat\work\travel_editor_1_to_6")
outdir.mkdir(parents=True, exist_ok=True)
ffmpeg=root/'.codex_tools'/'bin'/'ffmpeg.exe'
files=['1.mp4','2.mp4','3.mp4','4.mp4','5.mp4','6.mp4']
rows=[]
for name in files:
    p=root/name
    info=subprocess.run([str(ffmpeg),'-hide_banner','-i',str(p)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace').stdout
    m=re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)',info)
    dur=int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)) if m else 0
    r=re.search(r'Video:.*?(\d{3,5})x(\d{3,5}).*?(\d+(?:\.\d+)?)\s*fps',info)
    res=f"{r.group(1)}x{r.group(2)}" if r else ''
    fps=r.group(3) if r else ''
    if dur <= 6:
        times=[0.8,1.8,2.8,3.8,4.8]
    else:
        times=[0.8,5.8,10.8,15.8,20.8,25.8]
        if dur > 32: times += [30.8,35.8]
        if dur > 45: times += [40.8,47.8]
    fps_paths=[]
    for i,t in enumerate([x for x in times if x < dur-.2]):
        fp=outdir/f'{Path(name).stem}_{i:02d}_{t:.1f}.jpg'
        subprocess.run([str(ffmpeg),'-y','-ss',f'{t:.3f}','-i',str(p),'-frames:v','1','-q:v','3','-vf','scale=260:-2',str(fp)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        fps_paths.append((t,fp))
    rows.append((name,dur,res,fps,fps_paths))
cell_w=1500; row_h=210
sheet=Image.new('RGB',(cell_w,row_h*len(rows)),(18,18,22))
d=ImageDraw.Draw(sheet)
try:
    font=ImageFont.truetype('arial.ttf',17); small=ImageFont.truetype('arial.ttf',13)
except Exception:
    font=ImageFont.load_default(); small=font
for r,(name,dur,res,fps,fps_paths) in enumerate(rows):
    y=r*row_h
    d.text((10,y+8),f'{name}  {dur:.1f}s  {res}  {fps}fps',fill=(240,240,240),font=font)
    for i,(t,fp) in enumerate(fps_paths[:7]):
        x=10+i*210
        im=Image.open(fp).convert('RGB'); im.thumbnail((200,140))
        sheet.paste(im,(x,y+38))
        d.text((x,y+38+im.height+4),f'{t:.1f}s',fill=(190,190,200),font=small)
out=outdir/'travel_editor_contact_1_to_6.jpg'
sheet.save(out,quality=92)
print(out)
for name,dur,res,fps,_ in rows:
    print(f'{name}\t{dur:.2f}\t{res}\t{fps}')
