"""Smoke test: render a short video end-to-end with VideoEngine (Edge TTS + PIL subtitles + moviepy).

Run:  ./venv/bin/python scripts/render_smoke_test.py
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video_engine import VideoEngine, resolve_font_path

OUT = Path(__file__).resolve().parent.parent / "downloads" / "render_smoke_test"

TEXT = "Steam rises from a cup of coffee in the soft morning light — the start of something good."


def make_fake_scene_image(path):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1080, 1920), (20, 24, 46))
    draw = ImageDraw.Draw(img)
    draw.ellipse([340, 760, 740, 1160], fill=(240, 200, 120))
    img.save(path)
    return str(path)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"resolved font: {resolve_font_path()}")

    engine = VideoEngine(output_dir=str(OUT))

    print("🎙 Generating TTS via Edge (en-US)...")
    speech = await engine.generate_voiceover(TEXT, 0, voice="en-US-ChristopherNeural", language="en-US")
    assert speech and Path(speech).stat().st_size > 0, f"TTS failed: {speech}"
    print(f"   ✓ {speech} ({Path(speech).stat().st_size} bytes)")

    scene_img = make_fake_scene_image(OUT / "scene_0.jpg")
    script_data = [{"sentence": TEXT, "keyword": "scene_000", "_files": [scene_img]}]

    settings = SimpleNamespace(
        ratio="9:16", voice="en-US-ChristopherNeural", subtitles=True, language="en-US",
        subtitle_style="high_retention", music="none", filter="none", vibe="suspense_cn",
        emoji_subtitles=False, watermark=False, logo_path="static/logo.png",
    )

    print("🎬 Rendering 9:16 video with subtitles (moviepy)...")
    video = engine.create_video(script_data, OUT, media_type="photo", bg_music=None, settings=settings)
    assert video and Path(video).exists() and Path(video).stat().st_size > 100_000, f"render failed: {video}"
    size_mb = Path(video).stat().st_size / 1_000_000
    print(f"✅ Rendered: {video} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    asyncio.run(main())
