import re, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(r"E:\熊本")
outdir=Path(r"C:\Users\USER\Documents\Codex\2026-07-04\new-chat\work\analysis_1_to_6")
outdir.mkdir(parents=True, exist_ok=True)
ffmpeg=root/'.codex_tools'/'bin'/'ffmpeg.exe'
files=['1.mp4','2.mp4','3.mp4','4.mp4','5.mp4','6.mp4']
rows=[]
for name in files:
    p=root/name
    info=subprocess.run([str(ffmpeg),'-hide_banner','-i',str(p)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace').stdout
    m=re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)',info)
    dur=int(m.group(1))*3600+int(m.group(2))*60+float(m.group(3)) if m else 0
    step=5 if dur>15 else 1
    times=[]
    t=0.8
    while t<dur-0.3:
        times.append(t); t+=step
    if dur>10 and dur-1 not in times: times.append(dur-1)
    fps=[]
    for i,t in enumerate(times):
        fp=outdir/f'{Path(name).stem}_{i:02d}_{t:.1f}.jpg'
        subprocess.run([str(ffmpeg),'-y','-ss',f'{t:.3f}','-i',str(p),'-frames:v','1','-q:v','3','-vf','scale=260:-2',str(fp)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        fps.append((t,fp))
    rows.append((name,dur,fps))
cell_w=1500; row_h=210
sheet=Image.new('RGB',(cell_w,row_h*len(rows)),(18,18,22))
d=ImageDraw.Draw(sheet)
try:
    font=ImageFont.truetype('arial.ttf',17); small=ImageFont.truetype('arial.ttf',13)
except Exception:
    font=ImageFont.load_default(); small=font
for r,(name,dur,fps) in enumerate(rows):
    y=r*row_h
    d.text((10,y+8),f'{name}  duration {dur:.1f}s',fill=(240,240,240),font=font)
    for i,(t,fp) in enumerate(fps[:7]):
        x=10+i*210
        im=Image.open(fp).convert('RGB'); im.thumbnail((200,140))
        sheet.paste(im,(x,y+38))
        d.text((x,y+38+im.height+4),f'{t:.1f}s',fill=(190,190,200),font=small)
out=outdir/'analysis_contact_1_to_6.jpg'
sheet.save(out,quality=92)
print(out)
