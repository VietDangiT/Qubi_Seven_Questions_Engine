"""Render four data-driven 18-second animal fact questions."""
import json
import math
import subprocess
from pathlib import Path
from PIL import Image,ImageDraw
from render_v2 import ROOT,W,H,FPS,load,font,ease

QUESTIONS=json.loads((ROOT/'extra_questions.json').read_text())
CENTERS=(495,745,995)
TOP=250
OLD={'DOG':0,'CAT':1,'COW':2}
STRIP=ROOT/'assets/new_animals/fly_trio.png'


def art():
    strip=Image.open(STRIP).convert('RGBA')
    w,h=strip.size
    lookup={
      'PENGUIN':strip.crop((0,0,545,h)),
      'EAGLE':strip.crop((550,0,1225,h)),
      'ELEPHANT':strip.crop((1310,0,w,h)),
    }
    for name in ('rabbit','dolphin','giraffe','kangaroo'):
        lookup[name.upper()]=Image.open(ROOT/'assets/new_animals'/f'{name}.png').convert('RGBA')
    return lookup


def generated_card(name,letter,position,illustration):
    colors=(('#eff8ff','#69b0de'),('#fff8e7','#f4bc51'),('#fff6f3','#ee9187'))
    fill,edge=colors[position]
    im=Image.new('RGBA',(205,245),(0,0,0,0));d=ImageDraw.Draw(im)
    d.rounded_rectangle((3,4,201,239),radius=25,fill=fill,outline=edge,width=4)
    bbox=illustration.getchannel('A').getbbox()
    if not bbox:raise ValueError(f'No visible art for {name}')
    cut=illustration.crop(bbox)
    cut.thumbnail((181,170),Image.Resampling.LANCZOS)
    im.alpha_composite(cut,((205-cut.width)//2,14+(174-cut.height)//2))
    d.ellipse((13,194,55,236),fill=edge)
    d.text((34,215),letter,anchor='mm',font=font(20),fill='#fff')
    size=20
    while d.textbbox((0,0),name,font=font(size))[2]>134 and size>15:size-=1
    d.text((127,215),name,anchor='mm',font=font(size),fill='#243955')
    # Text must not exceed the dedicated label region.
    assert d.textbbox((127,215),name,anchor='mm',font=font(size))[0]>=57
    return im


def frame(t,q,base,cards,poses):
    im=base.copy();d=ImageDraw.Draw(im)
    d.rounded_rectangle((363,132,1131,229),radius=14,fill='#fffaf0')
    title=q['question']
    if len(title)>37:
        words=title.split();split=len(words)//2
        lines=[' '.join(words[:split]),' '.join(words[split:])]
        ys=(163,202);size=24
    else:
        lines=[title];ys=(169,);size=29
    for line,y in zip(lines,ys):
        d.text((748,y),line,anchor='mm',font=font(size),fill='#243955')
    d.rounded_rectangle((1041,187,1128,222),radius=17,fill='#e8f3e9')
    d.text((1084,204),f"{q['id']}/7",anchor='mm',font=font(17),fill='#287c57')
    correct=q['answer']
    if t<2:
        pose='think'
        d.ellipse((718,204,776,262),outline='#efb94c',width=4)
        d.text((748,232),'?',anchor='mm',font=font(29),fill='#2798bf')
    else:
        for j,item in enumerate(cards):
            visible=ease((t-(2+j*.16))/.4)
            if visible<=0:continue
            highlight=j==correct and t>=13
            scale=1+.06*ease((t-13)/.35) if highlight else 1
            picture=item if scale==1 else item.resize((round(item.width*scale),round(item.height*scale)),Image.Resampling.LANCZOS)
            x=round(CENTERS[j]-picture.width/2);y=round(TOP+25*(1-visible))
            if highlight:d.rounded_rectangle((x-4,y-4,x+picture.width+4,y+picture.height+4),radius=24,outline='#329d60',width=5)
            im.alpha_composite(picture,(x,y))
        d=ImageDraw.Draw(im)
        if t<10:
            pose='think';d.text((748,539),'Think... choose one!',anchor='mm',font=font(19),fill='#7d654d')
        elif t<13:
            pose='anticipation';n=max(1,3-int(t-10));d.text((748,539),str(n),anchor='mm',font=font(31),fill='#d18c23')
        else:
            pose='point' if t<16 else 'celebrate'
            d.rounded_rectangle((609,518,887,559),radius=17,fill='#fffef9',outline='#3d9f65',width=2)
            d.text((748,539),f"It's the {q['options'][correct]}!",anchor='mm',font=font(20),fill='#253a55')
    p=poses[pose]
    bounce=round(3*math.sin(2*math.pi*t*1.1))
    im.alpha_composite(p,(185-p.width//2,675-p.height+bounce))
    return im.convert('RGB')


def render():
    existing,poses=load();library=art();base=Image.open(ROOT/'assets/scene_v3.png').convert('RGBA')
    cards=[]
    for q in QUESTIONS:
        row=[]
        for j,name in enumerate(q['options']):
            row.append(existing[OLD[name]] if name in OLD else generated_card(name,'ABC'[j],j,library[name]))
        cards.append(row)
    for i,q in enumerate(QUESTIONS):
        frame(5,q,base,cards[i],poses).save(ROOT/f"qa_v8_question_{q['id']}.png")
        frame(14,q,base,cards[i],poses).save(ROOT/f"qa_v8_answer_{q['id']}.png")
    out=ROOT/'extra_questions_v8.mp4'
    p=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}',
        '-r',str(FPS),'-i','-','-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p',str(out)],
        stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for i in range(len(QUESTIONS)*18*FPS):
            qid=i//(18*FPS);local=(i%(18*FPS))/FPS
            p.stdin.write(frame(local,QUESTIONS[qid],base,cards[qid],poses).tobytes())
    finally:
        p.stdin.close();err=p.stderr.read()
        if p.wait():raise RuntimeError(err.decode()[-2000:])
    print(out)

if __name__=='__main__':render()
