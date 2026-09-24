"""Mix new ElevenLabs bookends around the approved three-question sequence."""
from __future__ import annotations

import array
import json
import math
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import audio_master
from elevenlabs_pipeline import generate, DEFAULT_VOICE_ID
from voiceover import LINES

ROOT=Path(__file__).resolve().parent
RATE=48000
DURATION=72
BOOKENDS=[
    ('greeting',4.13,7.92,"Hi, everyone! I'm Qubi. Ready to play?"),
    ('score',60.13,64.92,"Great job! Three questions done. How many did you get right?"),
    ('goodbye',65.13,71.40,"Thanks for playing with me! See you next time. Bye-bye!"),
]


def decode(path):
    with tempfile.TemporaryDirectory() as folder:
        wav=Path(folder)/'audio.wav'
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(path),'-ar',str(RATE),
                        '-ac','1','-c:a','pcm_s16le',str(wav)],check=True)
        with wave.open(str(wav),'rb') as f:
            pcm=array.array('h');pcm.frombytes(f.readframes(f.getnframes()))
    return pcm


def add_logo_sting(path):
    """A short, original four-note celesta motif for the silent logo scene."""
    with wave.open(str(path),'rb') as f:
        params=f.getparams()
        pcm=array.array('h');pcm.frombytes(f.readframes(f.getnframes()))
    for start,hz in ((.28,523.25),(1.03,659.25),(1.78,783.99),(2.55,1046.5)):
        at=round(start*RATE)
        for i in range(round(.55*RATE)):
            t=i/RATE
            env=(1-math.exp(-t*90))*math.exp(-t*6.4)
            sound=.115*env*(math.sin(2*math.pi*hz*t)+.22*math.sin(4*math.pi*hz*t))
            pos=at+i
            if pos<len(pcm):pcm[pos]=round(max(-32768,min(32767,pcm[pos]+sound*32767)))
    with wave.open(str(path),'wb') as f:
        f.setparams(params);f.writeframes(pcm.tobytes())


def main():
    visual=ROOT/'episode_visual_v6.mp4'
    if not visual.is_file():
        raise RuntimeError('Run render_bookends_v6.py first')
    cache=ROOT/'elevenlabs_cache'/'v6_bookends'
    cache.mkdir(parents=True,exist_ok=True)
    cues=[]
    for i,(name,start,end,text) in enumerate(BOOKENDS):
        path=cache/f'{name}.mp3'
        if not path.is_file():
            key=os.environ.get('ELEVENLABS_API_KEY')
            if not key:raise RuntimeError('ELEVENLABS_API_KEY needed for new bookend narration')
            audio=generate(text,'','',key,DEFAULT_VOICE_ID)
            with tempfile.NamedTemporaryFile(dir=cache,suffix='.mp3',delete=False) as f:
                f.write(audio); temporary=Path(f.name)
            temporary.replace(path)
        cues.append((name,start,end,text,path))
    # The approved answers and prompts retain their original audio bytes.
    for n,(start,end,text) in enumerate(LINES[1:18],2):
        path=ROOT/'elevenlabs_cache'/'takes'/f'{n:02d}.mp3'
        if not path.is_file():raise FileNotFoundError(path)
        cues.append((f'quiz_{n:02d}',start+4,end+4,text,path))
    cues.sort(key=lambda c:c[1])
    track=array.array('f',[0.0])*(DURATION*RATE)
    report=[]
    for name,start,end,text,path in cues:
        pcm=decode(path)
        length=len(pcm)/RATE
        fits=length<=end-start
        report.append({'cue':name,'start':start,'end':end,'duration':round(length,3),
                       'text':text,'fits':fits})
        if not fits:continue
        offset=round(start*RATE)
        for i,s in enumerate(pcm):
            fade=min(1,i/480,max(0,(len(pcm)-i)/480))
            track[offset+i]+=s/32768*fade
    (cache/'timing_report.json').write_text(json.dumps(report,indent=2))
    if any(not item['fits'] for item in report):
        raise RuntimeError('A voice cue exceeds its window; see v6_bookends/timing_report.json')
    stem=cache/'voice_stem.wav'
    pcm=array.array('h',(round(max(-1,min(1,s))*32767) for s in track))
    with wave.open(str(stem),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(pcm.tobytes())
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(visual),'-map','0:a:0',
                    '-ar','48000','-ac','1','-c:a','pcm_s16le',str(ROOT/'effects_only.wav')],check=True)
    add_logo_sting(ROOT/'effects_only.wav')
    audio_master.DURATION=DURATION
    audio_master.COUNT=RATE*DURATION
    audio_master.SOUND_WINDOWS=[(a+4,b+4) for a,b in audio_master.SOUND_WINDOWS]
    mastered=cache/'audio_master.wav'
    audio_master.master(mastered,stem)
    output=ROOT/'Qubi_Episode_01_Refined_Bookends_v6.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(visual),'-i',str(mastered),
                    '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac',
                    '-b:a','192k','-t',str(DURATION),'-movflags','+faststart',str(output)],check=True)
    print(output)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(f'Build stopped: {exc}',file=sys.stderr)
        raise SystemExit(1)
