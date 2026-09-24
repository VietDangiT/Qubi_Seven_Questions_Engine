"""Mix effects, temporary narration and low-level original code-composed music."""
from pathlib import Path
import array
import math
import wave

ROOT=Path(__file__).resolve().parent
RATE=48000
DURATION=62
COUNT=RATE*DURATION
SOUND_WINDOWS=[(6,7.7),(11,12.7),(24,25.1),(29,30.1),(42,44),(47,49)]

def read(path):
    with wave.open(str(path),'rb') as f:
        assert f.getframerate()==RATE and f.getnchannels()==1 and f.getsampwidth()==2
        a=array.array('h');a.frombytes(f.readframes(f.getnframes()))
        if len(a)<COUNT:a.extend([0]*(COUNT-len(a)))
        return a[:COUNT]

def master(out, voice_file=None):
    voice=read(voice_file or ROOT/'voice_guide.wav')
    effects=read(ROOT/'effects_only.wav')
    result=array.array('h',[0])*COUNT
    # Gentle three-note motif. It is composed deterministically here and kept
    # well below speech; no externally generated music asset is used.
    notes=[(0,392),(1.2,440),(2.4,523),(3.6,440),(4.8,392),(6,330),(7.2,392),(8.4,440)]
    melody=[]
    for cycle in range(8):
        for at,hz in notes:
            start=cycle*9.6+at
            if start<DURATION:melody.append((int(start*RATE),hz))
    for i in range(COUNT):
        t=i/RATE
        music=0.0
        # Periodically placed marimba-like notes with short decays.
        # Only check notes in the current and previous 0.9 seconds.
        local=t%9.6
        idx=int(local/1.2)
        start=(int(t/9.6)*9.6+idx*1.2)
        dt=t-start
        if 0<=dt<.8:
            hz=notes[idx][1]
            env=(1-math.exp(-dt*80))*math.exp(-dt*5.2)
            music=.017*env*(math.sin(2*math.pi*hz*dt)+.31*math.sin(2*math.pi*hz*2*dt))
        # Under animal calls reduce even the quiet motif.
        if any(a-.1<=t<=b+.15 for a,b in SOUND_WINDOWS):music*=.22
        s=.85*(voice[i]/32768)+.85*(effects[i]/32768)+music
        # Soft safety limiting; individual stems remain replaceable.
        s=math.tanh(s*1.02)/math.tanh(1.02)
        result[i]=round(max(-1,min(1,s))*32767)
    with wave.open(str(out),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE)
        f.writeframes(result.tobytes())
    print(out)

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--voice',type=Path,default=ROOT/'voice_guide.wav')
    ap.add_argument('--out',type=Path,default=ROOT/'audio_master_v4.wav')
    args=ap.parse_args()
    master(args.out,args.voice)
