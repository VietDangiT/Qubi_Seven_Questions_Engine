"""Reproducible temporary English guide voice for the Qubi edit.

Uses FFmpeg's local flite voice. Replace with a directed human performance
before publication. Captions and the script remain independent of this stem.
"""
from __future__ import annotations
import array
import json
import math
import subprocess
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RATE=48000
DURATION=62
LINES=[
 (0.15,3.95,"Hey, sound detectives! I'm Qubi. Ready to play?"),
 (4.03,5.95,"Who made this sound?"),
 (7.85,9.55,"Which animal?"),
 (9.62,10.99,"Your guess?"),
 (14.02,16.85,"Three, two, one!"),
 (17.12,19.8,"It's the cat! Meow!"),
 (20.12,21.85,"Great listening!"),
 (22.04,23.97,"Listen. Who is it?"),
 (25.82,27.54,"Take a guess!"),
 (27.65,28.95,"Your turn!"),
 (32.04,34.84,"Three, two, one!"),
 (35.15,37.83,"It's the dog! Woof, woof!"),
 (38.12,39.86,"You got it!"),
 (40.04,41.98,"Last one. Listen!"),
 (44.18,45.88,"Which animal?"),
 (46.02,46.99,"Guess!"),
 (50.05,52.84,"Three, two, one!"),
 (53.15,55.82,"It's the cow! Moo!"),
 (56.10,60.98,"You did it! Three sounds, three great guesses. See you next time!"),
]

def synthesize(out: Path,manifest: Path):
    temp=ROOT/'voice_clips';temp.mkdir(exist_ok=True)
    track=array.array('f',[0.0])*(DURATION*RATE)
    report=[]
    for index,(start,end,line) in enumerate(LINES):
        wav=temp/f'{index:02}.wav'
        txt=temp/f'{index:02}.txt'
        txt.write_text(line,encoding='utf-8')
        subprocess.run(['ffmpeg','-y','-f','lavfi','-i',f'flite=textfile={txt}:voice=slt',
                        '-ar',str(RATE),'-ac','1',str(wav)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        with wave.open(str(wav),'rb') as src:
            assert src.getframerate()==RATE and src.getnchannels()==1 and src.getsampwidth()==2
            pcm=array.array('h');pcm.frombytes(src.readframes(src.getnframes()))
        duration=len(pcm)/RATE
        slot=end-start
        if duration>slot:
            # Explicitly fail instead of clipping or overlapping dialogue.
            report.append({'line':line,'start':start,'end':end,'duration':round(duration,3),'status':'too_long'})
            continue
        offset=round(start*RATE)
        for i,s in enumerate(pcm):
            fade=min(1,i/480,max(0,(len(pcm)-i)/480))
            track[offset+i]+=0.82*(s/32768)*fade
        report.append({'line':line,'start':start,'end':end,'duration':round(duration,3),'status':'ok'})
    manifest.write_text(json.dumps(report,indent=2))
    if any(item['status']!='ok' for item in report):
        raise ValueError('Some guide voice lines exceed their scripted windows; inspect the timing report')
    pcm=array.array('h',(round(max(-1,min(1,s))*32767) for s in track))
    with wave.open(str(out),'wb') as dst:
        dst.setnchannels(1);dst.setsampwidth(2);dst.setframerate(RATE);dst.writeframes(pcm.tobytes())
    print(out)

if __name__=='__main__':
    synthesize(ROOT/'voice_guide.wav',ROOT/'voice_timing.json')
