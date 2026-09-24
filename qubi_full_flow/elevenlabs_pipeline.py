"""Generate and master Qubi voiceover from the timed script with ElevenLabs.

Requires ELEVENLABS_API_KEY. Each cue is cached by text, voice, model and
settings. A long take fails the build rather than being clipped or overlapping.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from assemble_human_voice import assemble
from audio_master import master
from voiceover import LINES, DURATION

ROOT = Path(__file__).resolve().parent
DEFAULT_VOICE_ID = "cgSgspJ2msm6clMCkdW9"  # Jessica, playful/bright/warm premade voice
MODEL_ID = "eleven_multilingual_v2"


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def duration(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True).strip())


def generate(text: str, previous: str, following: str, key: str, voice_id: str) -> bytes:
    body = json.dumps({
        "text": text,
        "model_id": MODEL_ID,
        "previous_text": previous or None,
        "next_text": following or None,
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
        data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            content = response.read()
            if not response.headers.get("Content-Type", "").startswith("audio/"):
                raise RuntimeError("ElevenLabs did not return audio")
            return content
    except urllib.error.HTTPError as error:
        # API errors are useful, but never print request headers or credentials.
        detail = error.read(1200).decode("utf-8", "replace")
        raise RuntimeError(f"ElevenLabs HTTP {error.code}: {detail}") from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice-id", default=DEFAULT_VOICE_ID, help="ElevenLabs voice ID; defaults to Jessica")
    parser.add_argument("--preview-voice", type=Path, help="Existing Lyan MP3 for cue 01; saves one API call")
    parser.add_argument("--out", type=Path, default=ROOT / "Qubi_Episode_01_ElevenLabs_Master.mp4")
    parser.add_argument("--cache", type=Path, default=ROOT / "elevenlabs_cache")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without API calls")
    args = parser.parse_args()
    visual = ROOT / "episode_visual_v4.mp4"
    if not visual.exists():
        visual = ROOT / "episode_visual.mp4"
    if not visual.exists():
        visual = ROOT.parent / "Qubi_Episode_01_Visual_v3.mp4"
    if not visual.exists():
        parser.error("58-second episode visual is missing")
    if args.preview_voice and not args.preview_voice.is_file():
        parser.error("Preview voice file is missing")
    if args.preview_voice and args.voice_id != "PStJ2DzQnh8zxG5PDf1s":
        parser.error("The supplied intro is Lyan; select her voice ID or omit --preview-voice")

    takes = args.cache / "takes"
    plan = []
    for n, (start, end, text) in enumerate(LINES, 1):
        previous = LINES[n - 2][2] if n > 1 else ""
        following = LINES[n][2] if n < len(LINES) else ""
        spec = {"voice_id": args.voice_id, "model_id": MODEL_ID, "text": text,
                "previous_text": previous, "next_text": following}
        digest = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:16]
        source = args.cache / f"{n:02d}_{digest}.mp3"
        plan.append({"cue": n, "start": start, "end": end, "text": text,
                     "source": str(source), "cached": source.exists() or bool(n == 1 and args.preview_voice)})
    if args.dry_run:
        print(json.dumps({"voice_id": args.voice_id, "model": MODEL_ID,
                          "api_calls_needed": sum(not p["cached"] for p in plan),
                          "cues": plan}, indent=2))
        return

    key = os.environ.get("ELEVENLABS_API_KEY")
    if any(not p["cached"] for p in plan) and not key:
        parser.error("ELEVENLABS_API_KEY is required for uncached cues")
    args.cache.mkdir(parents=True, exist_ok=True)
    takes.mkdir(parents=True, exist_ok=True)
    report = []
    for item in plan:
        n = item["cue"]
        source = Path(item["source"])
        if n == 1 and args.preview_voice:
            source = args.preview_voice
        elif not source.exists():
            text = item["text"]
            previous = LINES[n - 2][2] if n > 1 else ""
            following = LINES[n][2] if n < len(LINES) else ""
            audio = generate(text, previous, following, key, args.voice_id)
            with tempfile.NamedTemporaryFile(dir=args.cache, suffix=".mp3", delete=False) as tmp:
                tmp.write(audio)
                temporary = Path(tmp.name)
            temporary.replace(source)
        length = duration(source)
        slot = item["end"] - item["start"]
        report.append({**item, "duration": round(length, 3), "fits": length <= slot + 0.02})
        if report[-1]["fits"]:
            shutil.copyfile(source, takes / f"{n:02d}.mp3")

    (args.cache / "timing_report.json").write_text(json.dumps(report, indent=2))
    too_long = [p for p in report if not p["fits"]]
    if too_long:
        numbers = ", ".join(f"{p['cue']:02d}" for p in too_long)
        raise RuntimeError(f"Cues {numbers} exceed their time slots. See timing_report.json; "
                           "revise narration or scene timings. No audio was clipped.")
    stem = args.cache / "voice_stem.wav"
    assembled = args.cache / "audio_master.wav"
    assemble(takes, stem)
    # The visual contains animal sounds. Recreate the clean effects stem so no
    # previous guide voice can accidentally enter this master.
    run("ffmpeg", "-y", "-v", "error", "-i", str(visual), "-map", "0:a:0",
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(ROOT / "effects_only.wav"))
    master(assembled, stem)
    run("ffmpeg", "-y", "-v", "error", "-i", str(visual), "-i", str(assembled),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-b:a", "192k", "-t", str(DURATION), "-movflags", "+faststart", str(args.out))
    print(args.out)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Build stopped: {error}", file=sys.stderr)
        sys.exit(1)
