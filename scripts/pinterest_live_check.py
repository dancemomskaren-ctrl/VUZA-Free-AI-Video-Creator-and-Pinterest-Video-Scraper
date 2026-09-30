"""Live check for the Pinterest scraper (no API key needed).

Run:  ./venv/bin/python scripts/pinterest_live_check.py [query]
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aesthetic_scraper import PinterestScraper


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "coffee pouring slow motion"
    out_dir = Path(__file__).resolve().parent.parent / "downloads" / "pinterest_live_check"
    scraper = PinterestScraper(output_dir=str(out_dir))

    print(f"🔎 Searching Pinterest videos for: {query!r}")
    videos = await scraper.search_videos(query, num_videos=1)
    print(f"✅ Downloaded {len(videos)} video(s)")
    for v in videos:
        print(f"   📹 {v}")

    print(f"🔎 Searching Pinterest images for: {query!r}")
    images = await scraper.search_images(query, num_images=2)
    print(f"✅ Downloaded {len(images)} image(s)")
    for img in images:
        print(f"   🖼  {img}")

    if videos or images:
        print("\n🎉 Pinterest scraper works end-to-end on this machine.")
    else:
        print("\n⚠️  No media downloaded. Pinterest may have blocked headless access — try again later or use another source.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
