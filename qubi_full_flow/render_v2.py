"""Layered Qubi motion pilot. Render fresh frames from scene, pose and card assets."""
from pathlib import Path
import argparse
import json
import hashlib
import math
import subprocess
from PIL import Image, ImageDraw
from render import ROOT, W, H, FPS, DURATION, CARD_NAMES, CENTERS, CARD_TOP, MAX_SCALE, ease
from font_utils import font

def scene_plate():
    im=Image.new('RGBA',(W,H),'#f9efdc')
    d=ImageDraw.Draw(im)
    # Window and simple shelving are generated from geometry, not a flattened video.
    d.rounded_rectangle((20,48,305,356),radius=16,fill='#b6dff6',outline='#b98650',width=15)
    d.rectangle((151,49,166,358),fill='#b98650')
    d.rectangle((23,195,300,210),fill='#b98650')
    d.ellipse((-60,181,130,378),fill='#a6d283')
    d.ellipse((118,217,333,402),fill='#8fc16f')
    d.rectangle((0,589,W,H),fill='#d9a46e')
    d.rectangle((0,585,W,595),fill='#b57742')
    d.line((0,646,W,646),fill='#c58a57',width=3)
    d.line((0,700,W,700),fill='#c58a57',width=3)
    # Original board concept, one board and one coordinate system.
    d.rounded_rectangle((330,46,1164,607),radius=36,fill='#8d4b24')
    d.rounded_rectangle((339,54,1155,594),radius=31,fill='#b9743d')
    d.rounded_rectangle((349,73,1145,568),radius=26,fill='#fffaf0',outline='#e7d4b5',width=3)
    d.rounded_rectangle((615,18,882,117),radius=17,fill='#a96937',outline='#75421e',width=4)
    d.text((749,57),"Qubi's",anchor='mm',font=font(37),fill='#ffe379',stroke_width=2,stroke_fill='#734823')
    d.text((749,91),'Animal Quiz',anchor='mm',font=font(25),fill='#fffefd',stroke_width=2,stroke_fill='#734823')
    d.text((749,170),'Which animal made this sound?',anchor='mm',font=font(29),fill='#233955')
    # Small background props stay outside the board's safe zone.
    d.rounded_rectangle((1168,280,1256,548),radius=9,fill='#b77c45')
    for x,col in ((1184,'#e4ad4c'),(1207,'#78aacc'),(1230,'#a7c573')):
        d.rounded_rectangle((x,364,x+16,460),radius=4,fill=col)
    d.ellipse((1193,225,1241,273),fill='#6dab61')
    d.ellipse((1212,203,1264,258),fill='#88bd71')
    return im

def state(t):
    if t < 4.65:return 'think'
    if t < 5.45:return 'anticipation'
    if t < 7.35:return 'point'
    if t < 8.1:return 'settle'
    return 'celebrate'

def load():
    spec=json.loads((ROOT/'episode.json').read_text())
    assert spec['correct_index']==1 and spec['labels']==['DOG','CAT','COW']
    cards=[]
    for name in CARD_NAMES:
        p=ROOT/'assets'/name
        assert hashlib.sha256(p.read_bytes()).hexdigest()==spec['approved_card_sha256'][name]
        img=Image.open(p).convert('RGBA')
        assert img.width<=205 and img.height<=245
        cards.append(img)
    poses={}
    for key in ('think','anticipation','point','settle','celebrate'):
        p=ROOT/'assets/poses'/f'qubi_{key}.png'
        im=Image.open(p).convert('RGBA')
        assert im.getchannel('A').getextrema()==(0,255)
        crop=im.crop(im.getchannel('A').getbbox())
        crop.thumbnail((344,401),Image.Resampling.LANCZOS)
        poses[key]=crop
    for card in cards:
        assert card.width*MAX_SCALE<230
        assert CARD_TOP+round(card.height*MAX_SCALE)+9<520
    return cards,poses

def frame(t,base,cards,poses):
    im=base.copy()
    d=ImageDraw.Draw(im)
    if t<1.55:
        d.ellipse((719,193,777,251),outline='#efb43c',width=4)
        d.polygon([(731,215),(742,215),(754,205),(754,238),(742,227),(731,227)],fill='#429ac8')
        d.arc((742,209,768,238),-60,60,fill='#429ac8',width=3)
    for i,card in enumerate(cards):
        enter=ease((t-(1.05+i*.16))/.38)
        if enter<=0:continue
        selected=i==1 and t>=5.45
        scale=1+(.06*ease((t-5.45)/.35) if selected else 0)
        item=card if scale==1 else card.resize((round(card.width*scale),round(card.height*scale)),Image.Resampling.LANCZOS)
        x=round(CENTERS[i]-item.width/2);y=round(CARD_TOP+24*(1-enter))
        if selected:
            d.rounded_rectangle((x-4,y-4,x+item.width+4,y+item.height+4),radius=23,
                                outline='#399c61',width=5)
        im.alpha_composite(item,(x,y))
    d=ImageDraw.Draw(im)
    if 1.8<t<4.65:d.text((750,539),'Think...',anchor='mm',font=font(20),fill='#786552')
    elif 4.65<=t<5.45:
        n=max(1,3-int((t-4.65)/.27))
        d.text((750,539),str(n),anchor='mm',font=font(31),fill='#d18c23')
    elif t>=5.45:
        d.rounded_rectangle((604,517,895,559),radius=18,fill='#fffdf9',outline='#40a468',width=2)
        d.text((750,538),"Correct! It's the CAT!",anchor='mm',font=font(17),fill='#263953')
    # One transparent full-body pose per frame. No full-body crossfade.
    pose=poses[state(t)]
    breath=round(2*math.sin(2*math.pi*t*1.1))
    if state(t)=='celebrate':breath-=round(4*abs(math.sin(2*math.pi*t*1.5)))
    x=185-pose.width//2;y=675-pose.height+breath
    im.alpha_composite(pose,(x,y))
    return im.convert('RGB')

def render(out,qa):
    cards,poses=load();base=scene_plate();qa.mkdir(parents=True,exist_ok=True)
    for name,t in [('listen',.4),('think',2.6),('anticipation',4.95),('point',6.3),('settle',7.65),('celebrate',9.0)]:
        frame(t,base,cards,poses).save(qa/f'{name}.png')
    silent=out.with_suffix('.silent.mp4')
    cmd=['ffmpeg','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),
         '-i','-','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(silent)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for i in range(round(DURATION*FPS)):
            proc.stdin.write(frame(i/FPS,base,cards,poses).tobytes())
    finally:
        proc.stdin.close();error=proc.stderr.read();code=proc.wait()
        if code:raise RuntimeError(error.decode()[-1000:])
    subprocess.run(['ffmpeg','-y','-i',str(silent),'-i',str(ROOT/'assets/cat_meow.wav'),
                    '-filter_complex','[1:a]adelay=350|350,volume=0.8,apad=whole_dur=10.2[a]',
                    '-map','0:v','-map','[a]','-t',str(DURATION),'-c:v','copy','-c:a','aac',
                    '-b:a','160k','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    silent.unlink();print(out)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'Qubi_Animated_FullFlow_v2.mp4')
    ap.add_argument('--qa-dir',type=Path,default=ROOT/'qa_v2')
    a=ap.parse_args();render(a.out,a.qa_dir)
