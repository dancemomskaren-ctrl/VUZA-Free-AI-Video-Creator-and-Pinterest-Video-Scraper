import asyncio
import os
import re
import requests
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse, unquote
import yt_dlp
from tqdm import tqdm
from PIL import Image

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════
# VUZA — Video Utility for Zero-cost Automation
# Built by Ali R. | github.com/AliRash3ed
# ═══════════════════════════════════════════════════════════════

def get_async_playwright():
    try:
        from playwright.async_api import async_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError("Pinterest and URL scraping require Playwright: pip install playwright && playwright install chromium") from exc
    return async_playwright

class PinterestScraper:
    def __init__(self, output_dir="downloads/pinterest"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.seen_ids = set()

    def _get_folder(self, query):
        safe_query = re.sub(r'[^\w\-]', '_', query)[:25]
        folder = self.output_dir / safe_query
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    async def get_pin_urls(self, query, media_type="videos", scroll_count=5):
        search_url = f"https://www.pinterest.com/search/{media_type}/?q={quote(query)}"
        print(f"🔍 Searching Pinterest {media_type}: {query}")
        pins = []
        pin_ids = set()
        video_urls = set()
        image_urls = set()

        def harvest(node):
            """Recursively pull pin ids, mp4 urls and image urls from API JSON."""
            if isinstance(node, dict):
                pin_id = node.get("id")
                if isinstance(pin_id, str) and pin_id.isdigit():
                    pin_ids.add(pin_id)
                images = node.get("images")
                if isinstance(images, dict):
                    for variant in images.values():
                        url = (variant or {}).get("url") if isinstance(variant, dict) else None
                        if isinstance(url, str) and "pinimg.com" in url:
                            image_urls.add(url)
                videos = node.get("videos") if isinstance(node.get("videos"), dict) else node
                vlist = videos.get("video_list") if isinstance(videos, dict) else None
                if isinstance(vlist, dict):
                    for v in vlist.values():
                        url = (v or {}).get("url")
                        if isinstance(url, str) and ".mp4" in url:
                            video_urls.add(url)
                for v in node.values():
                    harvest(v)
            elif isinstance(node, list):
                for v in node:
                    harvest(v)

        async def on_response(resp):
            if "json" not in resp.headers.get("content-type", ""):
                return
            try:
                harvest(await resp.json())
            except Exception:
                pass

        async with get_async_playwright()() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=self.user_agent)
            page.on("response", on_response)
            try:
                # Pinterest streams background requests forever, so "networkidle" never fires
                # and page.goto would always time out. Pin data arrives via JSON API responses,
                # which we harvest above; the DOM itself no longer exposes /pin/ links logged-out.
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2000)
                for _ in range(scroll_count):
                    await page.evaluate("window.scrollBy(0, 1500)")
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"⚠️ Pinterest search failed: {e}")
            finally: await browser.close()

        self._harvested_video_urls = list(video_urls)
        self._harvested_image_urls = list(image_urls)
        pins = [f"https://www.pinterest.com/pin/{pid}/" for pid in pin_ids]
        print(f"📌 Found {len(pins)} pins, {len(video_urls)} video urls, {len(image_urls)} image urls")
        return pins

    async def search_images(self, query, num_images=5):
        urls = await self.get_pin_urls(query, media_type="pins", scroll_count=3)
        folder = self._get_folder(query)
        results = []
        # Fast path: image URLs harvested straight from API responses.
        direct = getattr(self, "_harvested_image_urls", [])[:num_images]
        if direct:
            tasks = [asyncio.to_thread(self.download_file, u, folder / f"pin_{i}.jpg") for i, u in enumerate(direct)]
            await asyncio.gather(*tasks)
            results = [str(f) for f in sorted(folder.glob("pin_*.jpg")) if f.stat().st_size > 0][:num_images]
        if len(results) >= num_images or not urls:
            return results[:num_images]
        # Fallback: visit pin pages for the remaining slots.
        for i, pin_url in enumerate(urls[:num_images*2]):
            try:
                async with get_async_playwright()() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page(user_agent=self.user_agent)
                    await page.goto(pin_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1500)
                    img_url = await page.evaluate('() => { const img = document.querySelector(\'img[srcset]\'); return img ? img.src : null; }')
                    await browser.close()
                    if img_url:
                        path = folder / f"pin_{i}.jpg"
                        if not path.exists():
                            r = requests.get(img_url, timeout=15)
                            if r.status_code == 200: path.write_bytes(r.content); results.append(str(path))
                        else: results.append(str(path))
            except: continue
            if len(results) >= num_images: break
        return results[:num_images]

    async def search_videos(self, query, num_videos=3):
        urls = await self.get_pin_urls(query, media_type="videos", scroll_count=3)
        if not urls and not getattr(self, "_harvested_video_urls", []): return []
        folder = self._get_folder(query)
        results = []
        # Fast path: download mp4s directly from harvested API URLs (no yt-dlp needed).
        direct = getattr(self, "_harvested_video_urls", [])[:num_videos*2]
        if direct:
            print(f"⚡ Downloading {min(len(direct), num_videos)} videos directly from API urls...")
            tasks = [asyncio.to_thread(self.download_file, u, folder / f"vid_{i}.mp4") for i, u in enumerate(direct)]
            await asyncio.gather(*tasks)
            results = [str(f) for f in sorted(folder.glob("vid_*.mp4")) if f.stat().st_size > 0][:num_videos]
        if len(results) >= num_videos or not urls:
            return results
        print(f"📌 Found {len(urls)} pins, downloading via yt-dlp...")
        downloader = VideoDownloader(output_dir=folder)
        return results + await downloader.download_parallel(urls, max_count=num_videos - len(results))

    def download_file(self, url, path):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                path.write_bytes(r.content); return True
        except: pass
        return False

# ═══════════════════════════════════════════════════════════════
# PEXELS SCRAPER (PARALLEL)
# ═══════════════════════════════════════════════════════════════

class PexelsScraper:
    def __init__(self, output_dir="downloads/pexels", api_key=None):
        self.output_dir = Path(output_dir)
        self.api_key = api_key or os.environ.get("PEXELS_API_KEY", "")
        self.headers = {"Authorization": self.api_key}
        self.seen_ids = set()

    def _get_folder(self, query):
        folder = self.output_dir / re.sub(r'[^\w\-]', '_', query)[:25]
        folder.mkdir(parents=True, exist_ok=True); return folder

    async def search_images(self, query, num_images=5):
        if not self.api_key: print("⚠️ Pexels API key not set"); return []
        folder = self._get_folder(query)
        try:
            url = f"https://api.pexels.com/v1/search?query={quote(query)}&per_page={num_images}"
            data = requests.get(url, headers=self.headers, timeout=15).json()
            tasks = [asyncio.to_thread(self.download_file, p["src"]["large2x"], folder / f"p_{i}.jpg") for i, p in enumerate(data.get("photos", []))]
            await asyncio.gather(*tasks)
            return [str(f) for f in folder.glob("*.jpg")][:num_images]
        except: return []

    async def search_videos(self, query, num_videos=3):
        if not self.api_key: print("⚠️ Pexels API key not set"); return []
        print(f"🎬 Searching Pexels: {query}")
        folder = self._get_folder(query)
        try:
            url = f"https://api.pexels.com/videos/search?query={quote(query)}&per_page={num_videos*5}"
            data = requests.get(url, headers=self.headers, timeout=15).json()
            valid_vids = []
            for v in data.get("videos", []):
                vid_id = v.get("id")
                if vid_id in self.seen_ids: continue
                if 3 <= v.get("duration", 0) <= 15:
                    best = next((vf for vf in v["video_files"] if vf.get("width") and vf["width"] <= 1920 and vf.get("link")), None)
                    if best:
                        valid_vids.append((best["link"], vid_id))
                        self.seen_ids.add(vid_id)
                if len(valid_vids) >= num_videos: break

            tasks = [asyncio.to_thread(self.download_file, link, folder / f"vid_{i}.mp4") for i, (link, _) in enumerate(valid_vids)]
            await asyncio.gather(*tasks)
            return [str(f) for f in folder.glob("*.mp4")]
        except: return []

    def download_file(self, url, path):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200: path.write_bytes(r.content); return True
        except: pass
        return False

# ═══════════════════════════════════════════════════════════════
# PIXABAY SCRAPER (PARALLEL)
# ═══════════════════════════════════════════════════════════════

class PixabayScraper:
    def __init__(self, output_dir="downloads/pixabay", api_key=None):
        self.output_dir = Path(output_dir)
        self.api_key = api_key or os.environ.get("PIXABAY_API_KEY", "")
        self.seen_ids = set()

    def _get_folder(self, query):
        folder = self.output_dir / re.sub(r'[^\w\-]', '_', query)[:25]
        folder.mkdir(parents=True, exist_ok=True); return folder

    async def search_images(self, query, num_images=5):
        if not self.api_key: print("⚠️ Pixabay API key not set"); return []
        folder = self._get_folder(query)
        try:
            url = f"https://pixabay.com/api/?key={self.api_key}&q={quote(query)}&per_page={num_images}"
            data = requests.get(url, timeout=15).json()
            tasks = [asyncio.to_thread(self.download_file, h["largeImageURL"], folder / f"pix_{i}.jpg") for i, h in enumerate(data.get("hits", []))]
            await asyncio.gather(*tasks)
            return [str(f) for f in folder.glob("*.jpg")][:num_images]
        except: return []

    async def search_videos(self, query, num_videos=3):
        if not self.api_key: print("⚠️ Pixabay API key not set"); return []
        folder = self._get_folder(query)
        try:
            url = f"https://pixabay.com/api/videos/?key={self.api_key}&q={quote(query)}&per_page={num_videos*5}"
            data = requests.get(url, timeout=15).json()
            valid = []
            for h in data.get("hits", []):
                vid_id = h.get("id")
                if vid_id in self.seen_ids: continue
                if 3 <= h.get("duration", 0) <= 15:
                    v = h["videos"].get("medium") or h["videos"].get("small")
                    if v:
                        valid.append(v["url"])
                        self.seen_ids.add(vid_id)
                if len(valid) >= num_videos: break
            tasks = [asyncio.to_thread(self.download_file, u, folder / f"v_{i}.mp4") for i, u in enumerate(valid)]
            await asyncio.gather(*tasks)
            return [str(f) for f in folder.glob("*.mp4")]
        except: return []

    def download_file(self, url, path):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200: path.write_bytes(r.content); return True
        except: pass
        return False

# ═══════════════════════════════════════════════════════════════
# VIDEO DOWNLOADER (yt-dlp PARALLEL)
# ═══════════════════════════════════════════════════════════════

class VideoDownloader:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def download_parallel(self, urls, max_count=3):
        print(f"🚀 Downloading {max_count} videos in parallel...")
        tasks = [self._dl_one(url, i) for i, url in enumerate(urls[:max_count*2])]
        res = await asyncio.gather(*tasks)
        return [r for r in res if r][:max_count]

    async def _dl_one(self, url, idx):
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
            'outtmpl': str(self.output_dir / f'vid_{idx}_%(id)s.%(ext)s'),
            'match_filter': yt_dlp.utils.match_filter_func('duration >= 3 & duration <= 15'),
            'quiet': True, 'ignoreerrors': True
        }
        try:
            return await asyncio.to_thread(self._run_ydl, url, ydl_opts)
        except: return None

    def _run_ydl(self, url, opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info) if info else None

# ═══════════════════════════════════════════════════════════════
# LLM PROCESSOR (Custom AI Brain Support)
# ═══════════════════════════════════════════════════════════════

class LLMProcessor:
    OPENROUTER_MODEL_ALIASES = {
        "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
        "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
        "deepseek-v3.2": "deepseek/deepseek-v3.2",
        "deepseek-v3.2-exp": "deepseek/deepseek-v3.2-exp",
        "deepseek-chat-v3.1": "deepseek/deepseek-chat-v3.1",
        "deepseek-r1": "deepseek/deepseek-r1",
        "deepseek-chat": "deepseek/deepseek-chat",
    }
    DEEPSEEK_MODEL_ALIASES = {
        "deepseek/deepseek-v4-pro": "deepseek-v4-pro",
        "deepseek/deepseek-v4-flash": "deepseek-v4-flash",
        "deepseek/deepseek-chat": "deepseek-chat",
        "deepseek/deepseek-reasoner": "deepseek-reasoner",
    }

    def __init__(self, api_key=None, api_url=None, model=None):
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.api_url = self._normalize_api_url(api_url or os.environ.get("LLM_API_URL", ""))
        self.last_error = ""
        custom_model = self._normalize_model(model or os.environ.get("LLM_MODEL", ""))
        if custom_model:
            self.models = [custom_model]
        elif self._is_deepseek_api():
            self.models = ["deepseek-v4-pro", "deepseek-chat"]
        else:
            self.models = [
                "qwen/qwen3-coder:free",
                "openai/gpt-oss-20b:free",
                "z-ai/glm-4.5-air:free",
                "meta-llama/llama-3.3-70b-instruct:free"
            ]

    def _normalize_api_url(self, api_url):
        url = (api_url or "").strip().rstrip("/")
        default = "https://openrouter.ai/api/v1/chat/completions"
        if not url:
            return default

        if "openrouter.ai" in url and not url.endswith("/chat/completions"):
            return default

        if "api.deepseek.com" in url and not url.endswith("/chat/completions"):
            return f"{url}/chat/completions"

        if url.endswith("/v1"):
            return f"{url}/chat/completions"

        return url

    def _is_deepseek_api(self):
        return "api.deepseek.com" in self.api_url

    def _is_openrouter_api(self):
        return "openrouter.ai" in self.api_url

    def _normalize_model(self, model):
        model = (model or "").strip()
        if not model:
            return ""

        if self._is_deepseek_api():
            if model in self.DEEPSEEK_MODEL_ALIASES:
                return self.DEEPSEEK_MODEL_ALIASES[model]
            if model.startswith("deepseek/"):
                return model.split("/", 1)[1]
            return model

        if self._is_openrouter_api() and model in self.OPENROUTER_MODEL_ALIASES:
            return self.OPENROUTER_MODEL_ALIASES[model]
        if self._is_openrouter_api() and "/" not in model and model.startswith("deepseek-"):
            return f"deepseek/{model}"
        return model

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://vuza.local",
            "X-Title": "VUZA AI Video Creator"
        }

    def _format_api_error(self, response):
        try:
            data = response.json()
            if isinstance(data, dict):
                err = data.get("error") or data.get("detail") or data
                if isinstance(err, dict):
                    return err.get("message") or json.dumps(err, ensure_ascii=False)[:300]
                return str(err)[:300]
        except Exception:
            pass
        return response.text[:300] if response.text else response.reason

    def _request_timeout(self, timeout):
        read_timeout = timeout or 40
        if self._is_deepseek_api():
            read_timeout = max(read_timeout, 180)
        return (20, read_timeout)

    def _chat(self, model, messages, timeout=40, max_tokens=None):
        payload = {"model": model, "messages": messages}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        attempts = 3 if self._is_deepseek_api() else 2
        response = None
        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=self._request_timeout(timeout)
                )
            except requests.Timeout as exc:
                self.last_error = (
                    f"AI API timed out (attempt {attempt}/{attempts}): {exc}. "
                    "If it keeps timing out, try deepseek-chat, retry later, or switch to OpenRouter."
                )
                print(f"❌ {self.last_error}")
                if attempt < attempts:
                    time.sleep(4 * attempt)
                    continue
                return None
            except requests.ConnectionError as exc:
                self.last_error = (
                    f"Could not connect to the AI API (attempt {attempt}/{attempts}): {exc}. "
                    "Check your network/proxy or retry later."
                )
                print(f"❌ {self.last_error}")
                if attempt < attempts:
                    time.sleep(4 * attempt)
                    continue
                return None
            except requests.RequestException as exc:
                self.last_error = f"Could not connect to the AI API: {exc}"
                print(f"❌ LLM request failed: {exc}")
                return None

            if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts:
                self.last_error = f"AI API busy (HTTP {response.status_code}), retrying {attempt}/{attempts}..."
                print(f"⚠️ {self.last_error}")
                time.sleep(4 * attempt)
                continue
            break

        if response.status_code != 200:
            if response.status_code == 404:
                if self._is_deepseek_api():
                    self.last_error = (
                        f"DeepSeek API URL or model not found (HTTP 404). Current URL: {self.api_url}; "
                        f"current model: {model}. Official DeepSeek URL: https://api.deepseek.com, "
                        "example model: deepseek-v4-pro."
                    )
                else:
                    self.last_error = (
                        f"AI API URL or model not found (HTTP 404). Current URL: {self.api_url}; "
                        f"current model: {model}. The OpenRouter URL should be https://openrouter.ai/api/v1/chat/completions, "
                        "example model: deepseek/deepseek-v4-pro."
                    )
            else:
                self.last_error = f"Model {model} call failed (HTTP {response.status_code}): {self._format_api_error(response)}"
            print(f"❌ {self.last_error}")
            return None

        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            self.last_error = f"AI returned an unexpected format: {exc}"
            print(f"❌ {self.last_error}")
            return None

    def extract_keywords(self, script, vibe="aesthetic"):
        if not self.api_key:
            self.last_error = "No AI API key received. Add your key in API Settings first."
            print("⚠️ LLM API key not set! Please add your AI API key in settings.")
            return []

        prompts = {
            "aesthetic": "Break script into sentences. For each, give 1 aesthetic keyword (2-4 words, end with 'aesthetic'). Return: Sentence → keyword",
            "lofi": """Break script into sentences. For each, give 1 keyword (2-4 words before adding 'lofi art', end with 'lofi art').
Match lofi-style visuals (rain, solitude, late night, healing, reflection). Return: Sentence → keyword""",
            "general": """Break this script into sentences. For each sentence, give 1 simple and general keyword (1-3 words) that visually represents the meaning of that sentence.
Rules:
- Use the MOST COMMON and EASIEST words possible (e.g. 'sunset', 'walking alone', 'ocean waves', 'city lights', 'happy people', 'rain falling').
- Do NOT add 'aesthetic', 'lofi', 'art', or any style suffix.
- Keywords must be generic enough to easily find stock photos/videos on Pexels or Pixabay.
- Think like a stock video searcher: what simple word would find a matching clip?
- Avoid abstract or poetic words. Use concrete, visual, real-world words.
Return format: Sentence → keyword""",
            "suspense": """Split this suspense narration into short lines that pair well with visuals.
For each line, generate 1 English stock-media search keyword that matches concrete, easy-to-find footage on Pexels/Pixabay.
Rules:
- Left side: keep the original narration line exactly.
- Right side: English keyword only, 1-4 words, no abstract words.
- Favor suspense-adjacent visuals: night, empty rooms, hallways, phones, doors, windows, shadows, rain, security cameras, footsteps, old photos.
- No explanations, numbering, scene descriptions, or character names.
Return format strictly: narration line → english keyword""",
            "futuristic": "Break script into sentences. For each, give 1 futuristic/cyberpunk keyword (2-4 words, end with 'futuristic'). Return: Sentence → keyword",
            "black_and_white": "Break script into sentences. For each, give 1 noir/vintage keyword (2-4 words, end with 'black and white'). Return: Sentence → keyword"
        }
        prompt = prompts.get(vibe, prompts["aesthetic"])
        if vibe == "suspense_cn":  # legacy key from the Chinese edition
            prompt = prompts["suspense"]
        for m in self.models:
            print(f"🤖 LLM ({m}) | Vibe: {vibe}")
            content = self._chat(
                m,
                [{"role": "system", "content": prompt}, {"role": "user", "content": script}],
                timeout=120 if len(script) >= 1000 else 40,
                max_tokens=6000 if len(script) >= 1000 else 1500
            )
            if content:
                parsed = self._parse(content)
                if parsed:
                    return parsed
                self.last_error = f"AI returned content but not in the 'line → keyword' format: {content[:200]}"
        return []

    def generate_viral_metadata(self, script):
        if not self.api_key:
            self.last_error = "No AI API key received. Add your key in API Settings first."
            return None
        prompt = """Analyze the following video script and act as a viral YouTube expert.
Generate:
1. A viral, high-click-through-rate Title.
2. An engaging Description including a summary and relevant keywords.
3. 5-10 trending Hashtags.
4. A detailed AI Image Generation Prompt for a high-CTR thumbnail (for Midjourney/DALL-E).

Format your response exactly like this:
TITLE: [Your Title]
DESCRIPTION: [Your Description]
HASHTAGS: [Your Hashtags]
THUMBNAIL_PROMPT: [Your AI Image Prompt]"""
        for m in self.models:
            try:
                r = requests.post(self.api_url,
                                  headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                                  data=json.dumps({"model": m, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": script}]}), timeout=30)
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    return self._parse_youtube(content)
            except: continue
        return None

    def generate_full_script(self, topic, vibe="general"):
        if not self.api_key:
            self.last_error = "No AI API key received. Add your key in API Settings first."
            return None
        if vibe in ("suspense", "suspense_cn"):
            is_long_source = len(topic) >= 600
            if is_long_source:
                prompt = """You are a viral short-form suspense storyteller who adapts long stories into high-retention narration.
The user gives you a full story. Rewrite it as a narration script suited for automatic scene-by-scene video generation.
Goals:
- Keep the main plotline; do NOT compress it into a summary.
- Cover the key plot beats, twists, crisis moments, resolutions, and the ending reversal.
- Suitable for a 3-6 minute vertical suspense narration video.
Structure:
- Open with a strong 1-2 line hook.
- Advance events in order through the middle, keeping tension.
- Write at least 4-8 lines for each major crisis scene; don't rush past them.
- Keep the original story's aftertaste or suspense at the end.
Format rules:
- Output 45-80 narration lines, one per line.
- Each line roughly 8-20 words, so one line pairs with one visual.
- Output only narration that can be read aloud.
- No titles, episode headers, camera directions, numbering, bullets, or character-name labels.
- No meta phrases like "Chapter 1", "next scene", or "the image shows".
- Do not invent key settings absent from the source."""
                max_tokens = 5000
            else:
                prompt = """You are a viral short-form suspense writer for TikTok/Reels/YouTube Shorts.
The user gives you a topic or suspense idea. Write an original 30-60 second suspense narration.
Structure: 3-second hook -> unsettling detail -> twist or open question -> cliffhanger ending.
Rules:
- Output 8-12 narration lines, each on its own line.
- Each line 8-18 words, so one line pairs with one visual.
- Output ONLY spoken narration: no titles, no scene directions, no character-name labels, no numbering.
- Keep the tone restrained, tense, and visual; avoid gore and references to real cases.
- The final line must leave the audience wanting the next part."""
                max_tokens = 1200

            for m in self.models:
                content = self._chat(
                    m,
                    [{"role": "system", "content": prompt}, {"role": "user", "content": topic}],
                    timeout=90 if is_long_source else 40,
                    max_tokens=max_tokens
                )
                if content:
                    return content
            return None

        vibe_instr = "educational and informative" if vibe == "educational" else "inspiring and fast-paced" if vibe == "motivational" else "poetic and slow" if vibe == "lofi" else "engaging and viral"
        prompt = f"""Act as a professional viral script writer for TikTok/Reels/Shorts.
Write a complete, high-retention video script about the following topic: '{topic}'.
The vibe should be {vibe_instr}.
Rules:
- Length: 5-10 punchy sentences.
- Each sentence should be on a NEW line.
- Do NOT include scene descriptions or speaker names. ONLY the text to be spoken.
- Make it highly engaging with a strong hook at the beginning."""
        for m in self.models:
            content = self._chat(m, [{"role": "system", "content": prompt}, {"role": "user", "content": topic}], timeout=40)
            if content:
                return content
        return None

    def _parse_youtube(self, text):
        data = {"title": "", "description": "", "hashtags": "", "thumbnail_prompt": ""}
        title_match = re.search(r'TITLE:\s*(.*)', text, re.IGNORECASE)
        desc_match = re.search(r'DESCRIPTION:\s*([\s\S]*?)(?=HASHTAGS:|$)', text, re.IGNORECASE)
        hash_match = re.search(r'HASHTAGS:\s*([\s\S]*?)(?=THUMBNAIL_PROMPT:|$)', text, re.IGNORECASE)
        thumb_match = re.search(r'THUMBNAIL_PROMPT:\s*(.*)', text, re.IGNORECASE)

        if title_match: data["title"] = title_match.group(1).strip()
        if desc_match: data["description"] = desc_match.group(1).strip()
        if hash_match: data["hashtags"] = hash_match.group(1).strip()
        if thumb_match: data["thumbnail_prompt"] = thumb_match.group(1).strip()
        return data

    def _parse(self, text):
        res = []
        for line in text.split('\n'):
            if '→' in line or '->' in line:
                arrow = '→' if '→' in line else '->'
                p = line.split(arrow, 1)
                sentence = re.sub(r'^\s*[\-\*\d\.\)\uff08\uff09、]+\s*', '', p[0]).strip()
                keyword = p[1].strip().strip('"').strip("'")
                if sentence and keyword:
                    res.append({"sentence": sentence, "keyword": keyword})
        return res

    def summarize_url(self, content):
        """Summarizes scraped web content into a video script."""
        if not self.api_key: return None
        prompt = "Act as a viral script writer. Summarize the following web content into a 5-10 sentence punchy video script for TikTok/Shorts. Return ONLY the script sentences, one per line. No scene descriptions."
        for m in self.models:
            try:
                r = requests.post(self.api_url,
                                  headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                                  data=json.dumps({"model": m, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": content[:10000]}]}), timeout=30)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            except: continue
        return None

    def generate_image_description(self, sentence):
        """Generates a detailed visual description for AI image generation fallback."""
        if not self.api_key:
            self.last_error = "No AI API key received. Add your key in API Settings first."
            return None
        prompt = "Describe a high-quality, cinematic suspense illustration representing this sentence. Return ONLY the description (max 28 words)."
        for m in self.models:
            content = self._chat(m, [{"role": "system", "content": prompt}, {"role": "user", "content": sentence}], timeout=30, max_tokens=120)
            if content:
                return content
        if not self.last_error:
            self.last_error = "AI did not produce a usable image description."
        return None

    def generate_character_profile(self, script):
        """Builds a reusable English protagonist profile for consistent AI scenes."""
        if not self.api_key:
            self.last_error = "No AI API key received. Add your key in API Settings first."
            return None

        prompt = """Read the suspense story and infer the main on-screen protagonist/narrator.
Return one concise English visual character profile for consistent image generation.
Include: gender, age range, face, hair, clothes, mood, and 2-3 signature visual details.
Do not mention names. Do not include explanations. Max 45 words."""
        for m in self.models:
            content = self._chat(m, [{"role": "system", "content": prompt}, {"role": "user", "content": script[:12000]}], timeout=40, max_tokens=180)
            if content:
                return content.strip()
        if not self.last_error:
            self.last_error = "AI did not produce a usable character profile."
        return None

    def _parse_json_array(self, text):
        cleaned = (text or "").strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]
        return json.loads(cleaned)

    def generate_scene_prompts(self, scene_items, character_profile="", vibe="suspense"):
        """Generate high-quality Seedream image prompts for already-split narration rows."""
        if not self.api_key:
            self.last_error = "AI image mode needs a DeepSeek/compatible LLM API key to generate image prompts."
            return None

        prompted_items = []
        batch_size = 10
        system_prompt = f"""You are a storyboard prompt director for Seedream 4.5 suspense short videos.
Task: for each narration line, write a high-quality vertical (9:16) image prompt for AI image generation.
Series protagonist: {character_profile or "keep the same suspense-story protagonist across scenes, realistic cinematic look."}
Requirements:
- Each prompt must concretely describe the subject, setting, lighting, camera, mood, and a suspense detail.
- Suited for 9:16 vertical video with a realistic cinematic-film look; dark and moody but clearly readable.
- When the line refers to the same "I/protagonist", keep their appearance, clothing, and vibe consistent.
- Do not generate subtitles, text, watermarks, logos, or UI artifacts.
- Avoid gore, excessive horror, and real identifiable people.
- Write image_prompt in English.
- Write keyword as a short English folder name, 2-5 words, joined with underscores.
Output ONLY a JSON array, no explanations. Format:
[{{"id":1,"keyword":"dark_room_phone","image_prompt":"..."}}]"""

        for start in range(0, len(scene_items), batch_size):
            batch = scene_items[start:start + batch_size]
            payload = [
                {"id": idx + 1, "sentence": item["sentence"]}
                for idx, item in enumerate(batch)
            ]
            content = None
            for m in self.models:
                content = self._chat(
                    m,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                    ],
                    timeout=180,
                    max_tokens=3500
                )
                if content:
                    break
            if not content:
                return None

            try:
                parsed = self._parse_json_array(content)
            except Exception as exc:
                self.last_error = f"Scene-prompt response had an unexpected format: {exc}; snippet: {content[:200]}"
                return None

            by_id = {}
            for row in parsed:
                try:
                    by_id[int(row.get("id"))] = row
                except Exception:
                    continue

            for idx, item in enumerate(batch):
                row = by_id.get(idx + 1, {})
                keyword = (row.get("keyword") or item.get("keyword") or f"scene_{start + idx + 1:03d}").strip()
                keyword = re.sub(r"[^\w\-]+", "_", keyword)[:40] or f"scene_{start + idx + 1:03d}"
                prompt = (row.get("image_prompt") or "").strip()
                if not prompt:
                    self.last_error = f"AI did not return an image prompt for line {start + idx + 1}."
                    return None
                prompted_items.append({
                    "sentence": item["sentence"],
                    "keyword": keyword,
                    "image_prompt": prompt
                })

        return prompted_items

# ═══════════════════════════════════════════════════════════════
# WEB SCRAPER (FOR URL TO VIDEO)
# ═══════════════════════════════════════════════════════════════

class WebScraper:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    async def scrape_url(self, url):
        """Extracts text content from a URL using Playwright."""
        print(f"🌐 Scraping URL: {url}")
        content = ""
        async with get_async_playwright()() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=self.user_agent)
            try:
                # Many article pages stream requests indefinitely; networkidle can never fire.
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2500)
                # Remove script/style tags
                await page.evaluate('''() => {
                    const elements = document.querySelectorAll("script, style, nav, footer, header");
                    for (const el of elements) el.remove();
                }''')
                content = await page.evaluate('() => document.body.innerText')
                # Clean up whitespace
                content = re.sub(r'\s+', ' ', content).strip()
            except Exception as e:
                print(f"❌ Scrape Error: {e}")
            finally:
                await browser.close()
        return content
