"""Assemble 19 approved actor takes into one 58-second timeline stem.

Each numbered source starts with the spoken line. Timing is controlled by the
cue sheet, not by silence or file names from the previous temporary voice.
"""
from __future__ import annotations
import argparse
import array
import csv
import subprocess
import tempfile
import wave
from pathlib import Path
from voiceover import LINES, RATE, DURATION


def assemble(takes: Path, out: Path):
    track=array.array('f',[0.0])*(DURATION*RATE)
    for n,(start,end,text) in enumerate(LINES,1):
        paths=[takes/f'{n:02d}{ext}' for ext in ('.wav','.flac','.mp3','.m4a')]
        available=[p for p in paths if p.is_file()]
        if len(available)!=1:
            raise FileNotFoundError(f'Expected one take named {n:02d}.wav/.flac/.mp3/.m4a')
        with tempfile.TemporaryDirectory() as tmp:
            wav=Path(tmp)/'converted.wav'
            subprocess.run(['ffmpeg','-y','-i',str(available[0]),'-ar',str(RATE),'-ac','1',
                            '-c:a','pcm_s16le',str(wav)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            with wave.open(str(wav),'rb') as f:
                pcm=array.array('h');pcm.frombytes(f.readframes(f.getnframes()))
        # Allow a short end tail, while prohibiting truncation against the next cue.
        slot=(end-start)
        duration=len(pcm)/RATE
        if duration>slot:
            raise ValueError(f'Take {n:02d} ({text}) lasts {duration:.2f}s, exceeds {slot:.2f}s cue window')
        offset=round(start*RATE)
        for i,s in enumerate(pcm):
            fade=min(1,i/480,max(0,(len(pcm)-i)/480))
            track[offset+i]+=s/32768*fade
    pcm=array.array('h',(round(max(-1,min(1,s))*32767) for s in track))
    with wave.open(str(out),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(pcm.tobytes())
    print(out)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--takes',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=Path('human_voice_stem.wav'))
    a=ap.parse_args();assemble(a.takes,a.out)
