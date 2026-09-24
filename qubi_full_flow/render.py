"""Reproducible Qubi pilot from original illustrated card assets.

One whole-card asset owns its animal, letter and label; no duplicated UI text.
This is an end-to-end prototype. The scene plate contains a static Qubi pose.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from font_utils import font

ROOT=Path(__file__).resolve().parent
W,H,FPS,DURATION=1280,720,30,10.2
CENTERS=(495,745,995)
CARD_TOP=250
MAX_SCALE=1.06
BANNER_TOP=520
CARD_NAMES=('dog_card.png','cat_card.png','cow_card.png')

def preflight(manifest):
    spec=json.loads(Path(manifest).read_text())
    assert spec['correct_index']==1 and spec['labels']==['DOG','CAT','COW']
    plate=Image.open(ROOT/'assets/scene_plate.png').convert('RGB')
    assert plate.size==(W,H)
    cards=[]
    for name in CARD_NAMES:
        path=ROOT/'assets'/name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==spec['approved_card_sha256'][name],name
        img=Image.open(path).convert('RGBA')
        assert img.width<=205 and img.height<=245 and img.getchannel('A').getextrema()[0]==0,name
        cards.append(img)
    for scale in (1,MAX_SCALE):
        widths=[round(c.width*scale) for c in cards]
        heights=[round(c.height*scale) for c in cards]
        for center,width in zip(CENTERS,widths):
            assert width<230 and center-width/2>=380 and center+width/2<=1110
        assert all((CENTERS[i+1]-widths[i+1]/2)-(CENTERS[i]+widths[i]/2)>=35 for i in (0,1))
        assert CARD_TOP+max(heights)+8<=BANNER_TOP
    return plate,cards,spec

def ease(t):
    t=max(0,min(1,t));return 1-(1-t)**3

def frame_at(t,plate,cards):
    base=plate.convert('RGBA')
    draw=ImageDraw.Draw(base)
    for i,card in enumerate(cards):
        u=ease((t-(1.05+i*.16))/.4)
        if u<=0:continue
        reveal=ease((t-5.45)/.4) if i==1 else 0
        scale=1+0.06*reveal
        if scale!=1:
            item=card.resize((round(card.width*scale),round(card.height*scale)),Image.Resampling.LANCZOS)
        else:item=card
        x=round(CENTERS[i]-item.width/2)
        y=round(CARD_TOP+28*(1-u))
        # Highlight rendered outside the original card boundary. No text is drawn.
        if reveal>0:
            rd=ImageDraw.Draw(base)
            rd.rounded_rectangle((x-4,y-4,x+item.width+4,y+item.height+4),radius=24,
                                 outline=(56,160,93,round(230*reveal)),width=5)
        base.alpha_composite(item,(x,y))
    d=ImageDraw.Draw(base)
    if 1.85<=t<4.65:
        d.text((748,500),'Think...',anchor='mm',font=font(19),fill='#806c52')
    elif 4.65<=t<5.45:
        n=max(1,3-int((t-4.65)/.27))
        d.text((748,500),str(n),anchor='mm',font=font(32),fill='#d38e28')
    elif t>=5.45:
        d.rounded_rectangle((605,520,893,554),radius=18,fill='#fffdf9',outline='#40a468',width=2)
        d.text((749,537),"Correct! It's the CAT!",anchor='mm',font=font(18),fill='#253a55')
    return base.convert('RGB')

def render(out,qa_dir):
    plate,cards,_=preflight(ROOT/'episode.json')
    qa_dir.mkdir(exist_ok=True,parents=True)
    for label,t in [('listen',0.4),('think',2.5),('countdown',5.1),('reveal',6.2),('celebrate',9.0)]:
        frame_at(t,plate,cards).save(qa_dir/f'{label}.png')
    silent=out.with_suffix('.silent.mp4')
    cmd=['ffmpeg','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}',
         '-r',str(FPS),'-i','-','-c:v','libx264','-preset','fast','-crf','19',
         '-pix_fmt','yuv420p',str(silent)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for i in range(round(DURATION*FPS)):
            proc.stdin.write(frame_at(i/FPS,plate,cards).tobytes())
    finally:
        proc.stdin.close();err=proc.stderr.read();rc=proc.wait()
        if rc:raise RuntimeError(err.decode()[-1500:])
    sound=ROOT/'assets/cat_meow.wav'
    cmd=['ffmpeg','-y','-i',str(silent),'-i',str(sound),'-filter_complex',
         '[1:a]adelay=350|350,volume=0.8,apad=whole_dur=10.2[a]',
         '-map','0:v','-map','[a]','-t',str(DURATION),'-c:v','copy','-c:a','aac','-b:a','160k',
         '-movflags','+faststart',str(out)]
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    silent.unlink()
    print(out)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'Qubi_FullFlow_Pilot_v1.mp4')
    parser.add_argument('--qa-dir',type=Path,default=ROOT/'qa')
    args=parser.parse_args();render(args.out,args.qa_dir)
