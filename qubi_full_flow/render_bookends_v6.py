"""Three-question episode: logo, Qubi greeting, untouched quiz, score, goodbye."""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw
from render_v2 import ROOT, W, H, FPS, load, font, ease

SKY=None
ROOM=None
QUESTION_TOTAL=3


def scene(t, kind, base, poses):
    if kind == 'logo':
        im=SKY.copy() if SKY is not None else Image.new('RGBA',(W,H),'#91cdf2')
        d=ImageDraw.Draw(im)
        reveal=ease((t-.22)/.52)
        if reveal:
            title_size=round(89+18*reveal)
            d.text((640,260),'Quizzz',anchor='mm',font=font(title_size),
                   fill='#243962',stroke_width=15,stroke_fill='#243962')
            d.text((640,256),'Quizzz',anchor='mm',font=font(title_size),
                   fill='#ffcf47',stroke_width=8,stroke_fill='#fff')
            d.text((640,256),'Quizzz',anchor='mm',font=font(title_size),
                   fill='#ffcf47',stroke_width=3,stroke_fill='#243962')
            d.text((640,365),'for Kids',anchor='mm',font=font(round(48+7*reveal)),
                   fill='#fff',stroke_width=9,stroke_fill='#243962')
        d.rounded_rectangle((353,473,927,571),radius=23,fill='#a86639',outline='#eec889',width=5)
        if t>1.35:
            d.text((640,507),'Small Questions!',anchor='mm',font=font(24),fill='#fff')
            d.text((640,539),'Big Discoveries!',anchor='mm',font=font(24),fill='#fff')
        return im.convert('RGB')

    im=(ROOM.copy() if kind=='greet' and ROOM is not None else base.copy())
    d=ImageDraw.Draw(im)
    if kind=='greet':
        # Bubble and captions are deterministic layers, avoiding generated text.
        d.rounded_rectangle((503,83,1193,389),radius=61,fill='#ffffff',outline='#e8d3b5',width=4)
        d.polygon([(576,367),(609,431),(659,373)],fill='#fff')
        d.text((848,167),'Hi, everyone!',anchor='mm',font=font(45),fill='#233955')
        d.text((848,251),"I'm Qubi.",anchor='mm',font=font(43),fill='#233955')
        d.text((848,322),'Ready to play?',anchor='mm',font=font(34),fill='#287f5d')
        d.rounded_rectangle((405,548,1168,613),radius=22,fill='#233955')
        d.text((786,580),'Welcome to Quizzz for Kids!',anchor='mm',font=font(25),fill='#fff')
        pose=poses['celebrate' if t<2 else 'point']
    elif kind=='score':
        d.rounded_rectangle((357,131,1136,560),radius=23,fill='#fffaf0')
        d.text((748,197),'GREAT JOB!',anchor='mm',font=font(47),fill='#e3764e')
        d.text((748,264),f'YOU FINISHED {QUESTION_TOTAL} QUESTIONS!',anchor='mm',font=font(31),fill='#233955')
        for i in range(QUESTION_TOTAL):
            grow=ease((t-.5-i*.35)/.4)
            if grow:
                step=68 if QUESTION_TOTAL>3 else 98
                x=748-step*(QUESTION_TOTAL-1)/2+step*i;r=round((20 if QUESTION_TOTAL>3 else 25)*grow)
                d.ellipse((x-r,336-r,x+r,336+r),fill='#f6bf46')
                d.text((x,335),'★',anchor='mm',font=font(26),fill='#fff')
        d.text((748,444),'How many did you get right?',anchor='mm',font=font(29),fill='#287f5d')
        pose=poses['celebrate']
    else:
        d.rounded_rectangle((357,131,1136,560),radius=23,fill='#fffaf0')
        d.rounded_rectangle((470,183,1027,405),radius=45,fill='#fff',outline='#d8b28d',width=3)
        d.text((748,249),'Thanks for playing!',anchor='mm',font=font(35),fill='#233955')
        d.text((748,312),'See you next time!',anchor='mm',font=font(31),fill='#287f5d')
        d.text((748,368),'Bye-bye!',anchor='mm',font=font(27),fill='#e3764e')
        d.rounded_rectangle((609,455,887,526),radius=19,fill='#9e6136')
        d.text((748,489),'Quizzz for Kids',anchor='mm',font=font(25),fill='#fff')
        pose=poses['celebrate']
    bounce=round(5*abs(math.sin(2*math.pi*1.3*t)))
    im.alpha_composite(pose,(185-pose.width//2,675-pose.height-bounce))
    return im.convert('RGB')


def segment(path,kind,duration,base,poses):
    p=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
        '-s',f'{W}x{H}','-r',str(FPS),'-i','-','-c:v','libx264','-preset','ultrafast',
        '-crf','21','-pix_fmt','yuv420p',str(path)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for i in range(FPS*duration):p.stdin.write(scene(i/FPS,kind,base,poses).tobytes())
    finally:
        p.stdin.close();err=p.stderr.read()
        if p.wait():raise RuntimeError(err.decode()[-2000:])


def main():
    global SKY,ROOM
    original=ROOT.parent/'Qubi_Episode_01_Visual_v3.mp4'
    base=Image.open(ROOT/'assets/scene_v3.png').convert('RGBA')
    SKY=Image.open(ROOT/'assets/intro_sky_v7.png').convert('RGBA').resize((W,H),Image.Resampling.LANCZOS)
    ROOM=Image.open(ROOT/'assets/intro_classroom_v7.png').convert('RGBA').resize((W,H),Image.Resampling.LANCZOS)
    _,poses=load()
    pieces=[]
    for kind,duration in (('logo',4),('greet',4),('score',5),('bye',7)):
        path=ROOT/f'{kind}_v6.silent.mp4'
        segment(path,kind,duration,base,poses);pieces.append(path)
        scene(duration/2,kind,base,poses).save(ROOT/f'qa_v6_{kind}.png')
    out=ROOT/'episode_visual_v6.mp4'
    subprocess.run(['ffmpeg','-y','-v','error',
        '-i',str(pieces[0]),'-i',str(pieces[1]),'-i',str(original),
        '-i',str(pieces[2]),'-i',str(pieces[3]),
        '-filter_complex',
        '[0:v]setpts=PTS-STARTPTS[v0];[1:v]setpts=PTS-STARTPTS[v1];'
        '[2:v]trim=start=4:end=56,setpts=PTS-STARTPTS[v2];'
        '[3:v]setpts=PTS-STARTPTS[v3];[4:v]setpts=PTS-STARTPTS[v4];'
        '[v0][v1][v2][v3][v4]concat=n=5:v=1:a=0[v];'
        '[2:a]adelay=4000,apad=pad_dur=14,atrim=duration=72[a]',
        '-map','[v]','-map','[a]','-c:v','libx264','-preset','medium',
        '-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',
        '-t','72','-movflags','+faststart',str(out)],check=True)
    for p in pieces:p.unlink()
    print(out)

if __name__=='__main__':main()
