#!/usr/bin/env python3
"""Anlatım seslerini üretir ve gerçek sürelerini ölçer.

Tek kaynak `docs/demo_narration_en.json`. Her segment Windows SAPI ile
seslendirilir, süresi `ffprobe` ile **ölçülür** ve `build/narration.json`
dosyasına yazılır. Montaj betiği bu ölçülen süreleri kullanır, böylece ses ve
görüntü tahminle değil ölçümle hizalanır.

Anlatım dili İngilizce: bu makinede Türkçe TTS sesi yok ve Türkçe metni
İngilizce sesle okutmak jüri videosunda kabul edilemez. Karar
`docs/demo_narration_en.json` içinde gerekçesiyle kayıtlı.

Kullanım:

    .venv\\Scripts\\python.exe scripts/k5_synthesize_narration.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NARRATION = ROOT / "docs" / "demo_narration_en.json"

# PowerShell tarafında konuşan parça. Metin dosyadan okunur, böylece
# kaçış sorunları olmaz.
PS_TEMPLATE = """
Add-Type -AssemblyName System.Speech
$text = Get-Content -LiteralPath '{text_path}' -Raw -Encoding utf8
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice('{voice}')
$synth.Rate = {rate}
$synth.SetOutputToWaveFile('{wav_path}')
$synth.Speak($text.Trim())
$synth.Dispose()
"""


def probe_duration(path: Path) -> float:
    """Ses dosyasının gerçek süresi (saniye)."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def synthesize(text: str, wav_path: Path, voice: str, rate: int) -> float:
    text_path = wav_path.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    script = PS_TEMPLATE.format(
        text_path=text_path.as_posix(),
        voice=voice,
        rate=rate,
        wav_path=wav_path.as_posix(),
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True,
        capture_output=True,
    )
    return probe_duration(wav_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "audio")
    parser.add_argument("--rate", type=int, default=0, help="SAPI konuşma hızı (-10..10)")
    args = parser.parse_args(argv)

    spec = json.loads(NARRATION.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)

    measured = []
    total = 0.0
    for segment in spec["segments"]:
        text = " ".join(segment["chunks"])
        wav_path = args.out / f"{segment['id']}.wav"
        duration = synthesize(text, wav_path, spec["voice"], args.rate)
        total += duration
        measured.append(
            {
                "id": segment["id"],
                "scene_prefixes": segment["scene_prefixes"],
                "chunks": segment["chunks"],
                "wav": wav_path.name,
                "duration": round(duration, 3),
            }
        )
        print(f"  {segment['id']}: {duration:6.2f} sn  ({len(text.split())} kelime)")

    manifest = {
        "voice": spec["voice"],
        "title_card": spec["title_card"],
        "end_card": spec["end_card"],
        "segments": measured,
        "narration_seconds": round(total, 3),
    }
    out_file = args.out.parent / "narration.json"
    out_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nanlatim toplami: {total:.2f} sn -> {out_file}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
