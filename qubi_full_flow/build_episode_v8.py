"""Build seven-question episode from approved v6 and four data-driven rounds."""
import array
import json
import math
import os
import subprocess
import wave
from pathlib import Path
from PIL import Image
import render_bookends_v6 as book
import audio_master
from build_episode_v6 import decode, RATE
from elevenlabs_pipeline import generate, DEFAULT_VOICE_ID
from render_v2 import ROOT,load

DURATION=144
QUESTIONS=json.loads((ROOT/'extra_questions.json').read_text())
CACHE=ROOT/'elevenlabs_cache'/'v8_extra'

def run(*args):subprocess.run(args,check=True)

def visuals():
    book.QUESTION_TOTAL=7
    base=Image.open(ROOT/'assets/scene_v3.png').convert('RGBA')
    _,poses=load()
    for kind,length in (('score',5),('bye',7)):
        out=ROOT/f'{kind}_v8.silent.mp4'
        if not out.exists():book.segment(out,kind,length,base,poses)
        book.scene(length/2,kind,base,poses).save(ROOT/f'qa_v8_{kind}.png')
    output=ROOT/'episode_visual_v8.mp4'
    run('ffmpeg','-y','-v','error','-i',str(ROOT/'episode_visual_v6.mp4'),'-i',str(ROOT/'extra_questions_v8.mp4'),'-i',str(ROOT/'score_v8.silent.mp4'),'-i',str(ROOT/'bye_v8.silent.mp4'),'-filter_complex',
        '[0:v]trim=end=60,setpts=PTS-STARTPTS[v0];[1:v]setpts=PTS-STARTPTS[v1];[2:v]setpts=PTS-STARTPTS[v2];[3:v]setpts=PTS-STARTPTS[v3];[v0][v1][v2][v3]concat=n=4:v=1:a=0[v]',
        '-map','[v]','-c:v','libx264','-preset','medium','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(output))
    return output

def mix():
    CACHE.mkdir(parents=True,exist_ok=True)
    cues=[]
    for i,q in enumerate(QUESTIONS):
        start=60+i*18
        for label,offset,limit in (('prompt',.12,3.08),('choices',3.25,8.65),('reveal',13.12,17.72)):
            cues.append((f"q{q['id']}_{label}",start+offset,start+limit,q[label]))
    cues.append(('score',132.12,136.85,'Great job! Seven questions! How many did you get right?'))
    report=[]
    track=array.array('f',[0.0])*(DURATION*RATE)
    with wave.open(str(ROOT/'elevenlabs_cache/v6_bookends/voice_stem.wav'),'rb') as f:
        old=array.array('h');old.frombytes(f.readframes(f.getnframes()))
    for i,s in enumerate(old[:60*RATE]):track[i]=s/32768
    for i,s in enumerate(old[65*RATE:72*RATE]):track[(137*RATE)+i]=s/32768
    for name,start,end,words in cues:
        path=CACHE/f'{name}.mp3'
        if not path.exists():
            key=os.getenv('ELEVENLABS_API_KEY')
            if not key and os.getenv('QUBI_PREVIEW_NO_NEW_VOICE')=='1':
                report.append(dict(name=name,start=start,end=end,duration=0,fits=True,text=words,status='pending ElevenLabs'))
                continue
            if not key:raise RuntimeError('Set ELEVENLABS_API_KEY to generate the new spoken questions')
            path.write_bytes(generate(words,'','',key,DEFAULT_VOICE_ID))
        pcm=decode(path);length=len(pcm)/RATE
        report.append(dict(name=name,start=start,end=end,duration=round(length,3),fits=length<=end-start,text=words))
        if length>end-start:continue
        pos=round(start*RATE)
        for i,s in enumerate(pcm):track[pos+i]+=s/32768*min(1,i/480,(len(pcm)-i)/480)
    (CACHE/'timing_report.json').write_text(json.dumps(report,indent=2))
    if any(not c['fits'] for c in report):raise RuntimeError('Voice exceeds scheduled window; see timing_report.json')
    stem=CACHE/'voice_stem.wav'
    with wave.open(str(stem),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE)
        f.writeframes(array.array('h',(round(max(-1,min(1,s))*32767) for s in track)).tobytes())
    # Keep approved effects from the first 60 seconds and add four soft reveal chimes.
    effects=array.array('h',[0])*(DURATION*RATE)
    old_effects=decode(ROOT/'episode_visual_v6.mp4')
    for i,s in enumerate(old_effects[:60*RATE]):effects[i]=s
    for q in range(4):
        pos=round((60+18*q+13)*RATE)
        for i in range(round(.6*RATE)):
            t=i/RATE;env=(1-math.exp(-t*70))*math.exp(-t*7)
            sound=.105*env*(math.sin(2*math.pi*784*t)+.24*math.sin(2*math.pi*1568*t))
            effects[pos+i]=round(max(-32768,min(32767,effects[pos+i]+sound*32767)))
    with wave.open(str(ROOT/'effects_only.wav'),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(effects.tobytes())
    audio_master.DURATION=DURATION;audio_master.COUNT=DURATION*RATE
    audio_master.SOUND_WINDOWS=[(a+4,b+4) for a,b in audio_master.SOUND_WINDOWS]
    mastered=CACHE/'audio_master.wav';audio_master.master(mastered,stem)
    return mastered

def main():
    visual=visuals()
    audio=mix()
    preview=os.getenv('QUBI_PREVIEW_NO_NEW_VOICE')=='1'
    output=ROOT.parent/('Qubi_Episode_01_Seven_Questions_Preview.mp4' if preview else 'Qubi_Episode_01_Seven_Questions_Final.mp4')
    run('ffmpeg','-y','-v','error','-i',str(visual),'-i',str(audio),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','160k','-t',str(DURATION),'-movflags','+faststart',str(output))
    print(output)
if __name__=='__main__':main()
