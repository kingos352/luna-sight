#!/usr/bin/env python3
"""Yakalanan karelerden 120 saniyelik demo videosunu kurar.

Girdi:
  `build/frames/*.png`   — `k5_record_demo.py` çıktısı, gerçek arayüz
  `build/narration.json` — `k5_synthesize_narration.py` çıktısı, **ölçülmüş**
                           segment süreleri ve altyazı parçaları

Çıktı:
  `build/luna_sight_demo_120s_v2.mp4` — 1920x1080, 30 fps, H.264 + AAC
  `build/luna_sight_demo_120s_v2.en.srt` — altyazı dosyası

Zamanlama tahmin edilmez: her segmentin süresi seslendirme dosyasından
ölçülür, kareler o süreye bölünür, altyazı parçaları da karakter uzunluğuna
göre aynı süre içinde dağıtılır. Böylece ses, görüntü ve altyazı tek
kaynaktan hizalanır.

Kullanım:

    .venv\\Scripts\\python.exe scripts/k5_build_video.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 1920, 1080
FPS = 30
CARD_SECONDS = 2.0

FONT_REGULAR = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")

BACKGROUND = (6, 10, 20)
ACCENT = (125, 190, 255)
TEXT = (238, 243, 252)
MUTED = (150, 165, 190)
CAPTION_BG = (8, 12, 22)


@dataclass
class Shot:
    """Videodaki tek bir kare: görüntü, süre, altyazı."""

    image: Path
    seconds: float
    caption: str


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Metni piksel genişliğine göre satırlara böl."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def compose_frame(image: Image.Image, text: str) -> Image.Image:
    """Arayüz karesini tuvale otur ve altyazı şeridini çiz.

    Arayüz 1920x900 yakalanır, altyazı kalan 180 piksellik şeride yazılır.
    Altyazı arayüzün üzerine binmez: jüri videosunda bir metrik kartını
    kapatmak, o kartı hiç göstermemekle aynı şeydir.
    """
    canvas = Image.new("RGB", (WIDTH, HEIGHT), CAPTION_BG)
    source = image.convert("RGB")
    canvas.paste(source, (0, 0))
    if source.height >= HEIGHT:
        return canvas

    draw = ImageDraw.Draw(canvas)
    strip_top = source.height
    draw.rectangle([0, strip_top, WIDTH, HEIGHT], fill=CAPTION_BG)
    draw.line([0, strip_top, WIDTH, strip_top], fill=ACCENT, width=2)
    if not text:
        return canvas

    font = _font(FONT_REGULAR, 34)
    lines = _wrap(text, font, WIDTH - 220)[:3]
    line_height = 46
    y = strip_top + max(18, (HEIGHT - strip_top - len(lines) * line_height) / 2)
    for line in lines:
        draw.text(((WIDTH - font.getlength(line)) / 2, y), line, font=font, fill=TEXT)
        y += line_height
    return canvas


def make_card(path: Path, heading: str, subtitle: str, footer: str) -> Path:
    """Başlık veya kapanış kartını çiz."""
    card = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(card)
    heading_font = _font(FONT_BOLD, 96)
    subtitle_font = _font(FONT_REGULAR, 42)
    footer_font = _font(FONT_REGULAR, 30)

    heading_lines = _wrap(heading, heading_font, WIDTH - 320)
    subtitle_lines = _wrap(subtitle, subtitle_font, WIDTH - 420)
    block = len(heading_lines) * 112 + 40 + len(subtitle_lines) * 58
    y = (HEIGHT - block) / 2 - 40
    for line in heading_lines:
        draw.text(
            ((WIDTH - heading_font.getlength(line)) / 2, y), line, font=heading_font, fill=TEXT
        )
        y += 112
    y += 40
    for line in subtitle_lines:
        draw.text(
            ((WIDTH - subtitle_font.getlength(line)) / 2, y), line, font=subtitle_font, fill=ACCENT
        )
        y += 58

    footer_lines = _wrap(footer, footer_font, WIDTH - 420)
    y = HEIGHT - 140
    for line in footer_lines:
        draw.text(
            ((WIDTH - footer_font.getlength(line)) / 2, y), line, font=footer_font, fill=MUTED
        )
        y += 40

    card.save(path)
    return path


def frame_prefix(path: Path) -> str:
    """`006_horizon_initial.png` -> `horizon`."""
    stem = path.stem.split("_", 1)[1] if "_" in path.stem else path.stem
    return stem.split("_", 1)[0]


def _boundaries(weights: list[int], total: float) -> list[float]:
    """Ağırlıklara göre kümülatif bitiş anları."""
    span = sum(weights)
    bounds, elapsed = [], 0.0
    for weight in weights:
        elapsed += total * weight / span
        bounds.append(elapsed)
    return bounds


def _index_at(offset: float, bounds: list[float]) -> int:
    for index, bound in enumerate(bounds):
        if offset < bound:
            return index
    return len(bounds) - 1


def segment_shots(frames: list[Path], chunks: list[str], total: float) -> list[Shot]:
    """Bir segmenti kare ve altyazı sınırlarını birleştirerek böl.

    Altyazı kare sayısına bağlanırsa, karesi az olan bir segmentte anlatımın
    bir kısmı ekrana hiç gelmez. Burada iki sınır kümesi birleştirilir: her
    aralıkta hem doğru kare hem o anda konuşulan cümle bulunur.
    """
    frame_bounds = _boundaries([1] * len(frames), total)
    chunk_bounds = _boundaries([max(len(chunk), 1) for chunk in chunks], total)
    marks = sorted({round(bound, 6) for bound in frame_bounds + chunk_bounds})

    shots: list[Shot] = []
    previous = 0.0
    for mark in marks:
        seconds = mark - previous
        if seconds <= 1e-3:
            previous = mark
            continue
        midpoint = (previous + mark) / 2
        frame = frames[_index_at(midpoint, frame_bounds)]
        caption = chunks[_index_at(midpoint, chunk_bounds)]
        shots.append(Shot(frame, seconds, caption))
        previous = mark
    return shots


def build_shots(frames_dir: Path, narration: dict, cards_dir: Path) -> list[Shot]:
    frames = sorted(frames_dir.glob("*.png"))
    if not frames:
        raise SystemExit(f"kare bulunamadı: {frames_dir}")

    cards_dir.mkdir(parents=True, exist_ok=True)
    title = narration["title_card"]
    end = narration["end_card"]
    title_card = make_card(
        cards_dir / "title.png", title["heading"], title["subtitle"], title["footer"]
    )
    shots = [Shot(title_card, CARD_SECONDS, "")]

    for segment in narration["segments"]:
        selected = [f for f in frames if frame_prefix(f) in segment["scene_prefixes"]]
        if not selected:
            print(f"  uyari: {segment['id']} icin kare yok")
            continue
        shots.extend(segment_shots(selected, segment["chunks"], float(segment["duration"])))

    shots.append(
        Shot(
            make_card(cards_dir / "end.png", end["heading"], end["subtitle"], end["footer"]),
            CARD_SECONDS,
            "",
        )
    )
    return shots


def render_shots(shots: list[Shot], render_dir: Path) -> list[Shot]:
    """Altyazıyı kareye gömer ve yeni yolları döndürür."""
    if render_dir.exists():
        shutil.rmtree(render_dir)
    render_dir.mkdir(parents=True)
    rendered = []
    for index, shot in enumerate(shots):
        target = render_dir / f"{index:04d}.png"
        with Image.open(shot.image) as source:
            compose_frame(source, shot.caption).save(target)
        rendered.append(Shot(target, shot.seconds, shot.caption))
    return rendered


def write_concat(shots: list[Shot], path: Path) -> None:
    lines = []
    for shot in shots:
        lines.append(f"file '{shot.image.as_posix()}'")
        lines.append(f"duration {shot.seconds:.4f}")
    lines.append(f"file '{shots[-1].image.as_posix()}'")  # son kareyi boşalt
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True)


def probe(path: Path, entries: str, stream: str | None = "v:0") -> str:
    """ffprobe sarmalayıcısı. `stream=None` biçim düzeyinde sorgular."""
    args = ["ffprobe", "-v", "error"]
    if stream:
        args += ["-select_streams", stream]
    args += ["-show_entries", entries, "-of", "csv=p=0", str(path)]
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def build_audio(narration: dict, audio_dir: Path, work: Path) -> Path:
    """Baş/son sessizlikleriyle birlikte tek ses parçası üret."""
    first = audio_dir / narration["segments"][0]["wav"]
    rate = probe(first, "stream=sample_rate", stream="a:0").splitlines()[0]
    silence = work / "silence.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-t",
            f"{CARD_SECONDS}",
            "-i",
            f"anullsrc=r={rate}:cl=mono",
            str(silence),
        ]
    )

    listing = work / "audio_concat.txt"
    parts = [silence] + [audio_dir / s["wav"] for s in narration["segments"]] + [silence]
    listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts) + "\n", encoding="utf-8")
    merged = work / "narration_full.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(merged),
        ]
    )
    return merged


def write_srt(shots: list[Shot], path: Path) -> None:
    """Altyazıyı zaman damgalarıyla yaz; aynı parça art arda birleştirilir."""

    def stamp(seconds: float) -> str:
        millis = int(round(seconds * 1000))
        hours, millis = divmod(millis, 3_600_000)
        minutes, millis = divmod(millis, 60_000)
        secs, millis = divmod(millis, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    entries: list[tuple[float, float, str]] = []
    clock = 0.0
    for shot in shots:
        start, end = clock, clock + shot.seconds
        clock = end
        if not shot.caption:
            continue
        if entries and entries[-1][2] == shot.caption:
            entries[-1] = (entries[-1][0], end, shot.caption)
        else:
            entries.append((start, end, shot.caption))

    blocks = []
    for index, (start, end, text) in enumerate(entries, start=1):
        body = "\n".join(textwrap.wrap(text, 78))
        blocks.append(f"{index}\n{stamp(start)} --> {stamp(end)}\n{body}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, default=ROOT / "build" / "frames")
    parser.add_argument("--narration", type=Path, default=ROOT / "build" / "narration.json")
    parser.add_argument("--audio", type=Path, default=ROOT / "build" / "audio")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "luna_sight_demo_120s_v2.mp4")
    args = parser.parse_args(argv)

    narration = json.loads(args.narration.read_text(encoding="utf-8"))
    work = args.out.parent / "work"
    work.mkdir(parents=True, exist_ok=True)

    print("kareler hazirlaniyor")
    shots = build_shots(args.frames, narration, work / "cards")
    rendered = render_shots(shots, work / "render")
    planned = sum(shot.seconds for shot in rendered)
    print(f"  {len(rendered)} kare, planlanan sure {planned:.2f} sn")

    listing = work / "video_concat.txt"
    write_concat(rendered, listing)
    silent = work / "video_silent.mp4"
    print("video kodlaniyor")
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-vf",
            f"fps={FPS},format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "medium",
            str(silent),
        ]
    )

    print("ses hazirlaniyor")
    audio = build_audio(narration, args.audio, work)

    print("ses ve goruntu birlestiriliyor")
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(silent),
            "-i",
            str(audio),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(args.out),
        ]
    )

    srt = args.out.with_suffix(".en.srt")
    write_srt(rendered, srt)

    duration = float(probe(args.out, "format=duration", stream=None))
    size = probe(args.out, "stream=width,height").replace("\n", "x")
    rate = probe(args.out, "stream=r_frame_rate")
    print("\n=== sonuc ===")
    print(f"  dosya    : {args.out}")
    print(f"  sure     : {duration:.2f} sn (hedef 120 +/- 3)")
    print(f"  cozunurluk: {size}")
    print(f"  fps      : {rate}")
    print(f"  altyazi  : {srt.name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
