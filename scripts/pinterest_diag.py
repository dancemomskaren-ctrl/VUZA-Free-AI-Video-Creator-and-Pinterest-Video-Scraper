"""One-off diagnostic v5: intercept Pinterest API responses; look for pin IDs + video URLs."""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
URL = "https://www.pinterest.com/search/videos/?q=coffee"

found_pins = {}
found_videos = {}


def dig(node, pin_out, vid_out):
    """Recursively collect pin ids and mp4 urls from arbitrary JSON."""
    if isinstance(node, dict):
        pin_id = node.get("id")
        if isinstance(pin_id, str) and pin_id.isdigit():
            pin_out[pin_id] = True
        videos = node.get("videos") if isinstance(node.get("videos"), dict) else None
        vlist = (videos or node).get("video_list") if isinstance((videos or node), dict) else None
        if isinstance(vlist, dict):
            for v in vlist.values():
                url = (v or {}).get("url")
                if isinstance(url, str) and ".mp4" in url:
                    vid_out[url] = True
        for v in node.values():
            dig(v, pin_out, vid_out)
    elif isinstance(node, list):
        for v in node:
            dig(v, pin_out, vid_out)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=UA)

        async def on_response(resp):
            ctype = resp.headers.get("content-type", "")
            if "json" not in ctype:
                return
            try:
                body = await resp.text()
                data = json.loads(body)
                dig(data, found_pins, found_videos)
            except Exception:
                pass

        page.on("response", on_response)
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            for i in range(3):
                await page.evaluate("window.scrollBy(0, 1500)")
                await page.wait_for_timeout(1200)
        finally:
            await browser.close()

    print(f"pin IDs harvested: {len(found_pins)}")
    for pid in list(found_pins)[:8]:
        print(f"  https://www.pinterest.com/pin/{pid}/")
    print(f"mp4 URLs harvested: {len(found_videos)}")
    for u in list(found_videos)[:5]:
        print(f"  {u[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
