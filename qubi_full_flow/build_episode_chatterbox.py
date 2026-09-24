"""Render the complete seven-question episode with one local Chatterbox voice.

Run --plan before installing the model. Run --sample to audition Qubi's voice.
After approving the sample, run --build to synthesize and master every cue.
"""
from __future__ import annotations

import argparse
import array
import json
import math
import subprocess
import wave
from pathlib import Path

import audio_master
from build_episode_v6 import RATE, decode
from render_v2 import ROOT
from voiceover import LINES

DURATION = 144
CACHE = ROOT / 'chatterbox_cache'
QUESTIONS = json.loads((ROOT / 'extra_questions.json').read_text())
OUTPUT = ROOT.parent / 'Qubi_Episode_01_Seven_Questions_Chatterbox.mp4'


def cues():
    result = [('greeting', 4.13, 7.92, "Hi, everyone! I'm Qubi. Ready to play?")]
    for index, (start, end, words) in enumerate(LINES[1:18], 2):
        result.append((f'old_{index:02d}', start + 4, end + 4, words))
    for index, question in enumerate(QUESTIONS):
        start = 60 + index * 18
        for name, offset, limit in (('prompt', .12, 3.08),
                                    ('choices', 3.25, 8.65),
                                    ('reveal', 13.12, 17.72)):
            result.append((f"q{question['id']}_{name}", start + offset,
                           start + limit, question[name]))
    result.extend([
        ('score', 132.12, 136.85, 'Great job! Seven questions! How many did you get right?'),
        ('goodbye', 137.13, 143.40, 'Thanks for playing with me! See you next time. Bye-bye!'),
    ])
    result.sort(key=lambda item: item[1])
    for a, b in zip(result, result[1:]):
        if a[2] > b[1]:
            raise ValueError(f'Overlapping voice slots: {a[0]} and {b[0]}')
    if result[-1][2] > DURATION:
        raise ValueError('Voice schedule exceeds video length')
    return result


def load_model():
    try:
        import torch
        from chatterbox.tts import ChatterboxTTS
    except ImportError as exc:
        raise RuntimeError('Install chatterbox-tts in the Python 3.12.10 environment first') from exc
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print('Chatterbox device:', device, flush=True)
    return ChatterboxTTS.from_pretrained(device=device), torch


def synthesize(name, words, model, torch):
    path = CACHE / 'takes' / f'{name}.wav'
    spec = {'text': words, 'model': 'chatterbox-base', 'seed': 20260924,
            'exaggeration': .62, 'cfg_weight': .36}
    manifest = path.with_suffix('.json')
    if path.exists() and manifest.exists() and json.loads(manifest.read_text()) == spec:
        return path
    import torchaudio
    path.parent.mkdir(parents=True, exist_ok=True)
    # One seed and the model's default speaker conditioning keep a coherent voice.
    torch.manual_seed(20260924)
    with torch.inference_mode():
        wav = model.generate(words, exaggeration=.62, cfg_weight=.36)
    temporary = path.with_suffix('.tmp.wav')
    torchaudio.save(str(temporary), wav.detach().cpu(), model.sr)
    temporary.replace(path)
    manifest.write_text(json.dumps(spec, indent=2))
    return path


def voice_track(schedule, model, torch):
    track = array.array('f', [0.0]) * (DURATION * RATE)
    report = []
    for name, start, end, words in schedule:
        source = synthesize(name, words, model, torch)
        pcm = decode(source)
        length = len(pcm) / RATE
        fits = length <= end - start
        report.append({'cue': name, 'start': start, 'end': end,
                       'duration': round(length, 3), 'fits': fits, 'text': words})
        if not fits:
            continue
        offset = round(start * RATE)
        for index, sample in enumerate(pcm):
            fade = min(1, index / 480, (len(pcm) - index) / 480)
            track[offset + index] += sample / 32768 * fade
    (CACHE / 'timing_report.json').write_text(json.dumps(report, indent=2))
    if any(not row['fits'] for row in report):
        raise RuntimeError('A spoken line is too long. See chatterbox_cache/timing_report.json; '
                           'adjust its wording or timing and regenerate only that take.')
    path = CACHE / 'voice_stem.wav'
    with wave.open(str(path), 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(array.array('h', (round(max(-1, min(1, x)) * 32767)
                                            for x in track)).tobytes())
    return path


def sound_effects():
    # The original visual carries animal sounds without spoken narration.
    old = decode(ROOT / 'episode_visual_v6.mp4')
    result = array.array('h', [0]) * (DURATION * RATE)
    result[:60 * RATE] = old[:60 * RATE]
    for question in range(4):
        offset = round((60 + question * 18 + 13) * RATE)
        for i in range(round(.6 * RATE)):
            t = i / RATE
            envelope = (1 - math.exp(-t * 70)) * math.exp(-t * 7)
            note = .105 * envelope * (math.sin(2 * math.pi * 784 * t) +
                                      .24 * math.sin(2 * math.pi * 1568 * t))
            result[offset + i] = round(max(-32768, min(32767,
                                          result[offset + i] + note * 32767)))
    with wave.open(str(ROOT / 'effects_only.wav'), 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(result.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--sample', action='store_true')
    mode.add_argument('--build', action='store_true')
    args = parser.parse_args()
    schedule = cues()
    if args.plan:
        print(json.dumps([{'name': n, 'start': a, 'end': b, 'text': s}
                          for n, a, b, s in schedule], indent=2))
        return
    CACHE.mkdir(parents=True, exist_ok=True)
    model, torch = load_model()
    if args.sample:
        sample = synthesize('greeting', schedule[0][3], model, torch)
        print('Qubi voice sample:', sample)
        return
    visual = ROOT / 'episode_visual_v8.mp4'
    if not visual.is_file():
        raise FileNotFoundError('Render episode_visual_v8.mp4 with build_episode_v8.py first')
    voice = voice_track(schedule, model, torch)
    sound_effects()
    audio_master.DURATION = DURATION
    audio_master.COUNT = RATE * DURATION
    audio_master.SOUND_WINDOWS = [(a + 4, b + 4) for a, b in audio_master.SOUND_WINDOWS]
    mastered = CACHE / 'master.wav'
    audio_master.master(mastered, voice)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(visual), '-i', str(mastered),
                    '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac',
                    '-b:a', '160k', '-t', str(DURATION), '-movflags', '+faststart',
                    str(OUTPUT)], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(OUTPUT), '-f', 'null', '-'], check=True)
    print('Final video:', OUTPUT)


if __name__ == '__main__':
    main()
