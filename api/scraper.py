from __future__ import annotations

import re
import asyncio
import httpx
from urllib.parse import urlparse

MAX_PROFILE_POSTS = 6
IMAGE_TIMEOUT = 20.0


def parse_shortcode(url: str) -> str | None:
    m = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def parse_username(url_or_handle: str) -> str | None:
    s = url_or_handle.strip().lstrip("@")
    if s.startswith("http"):
        path = urlparse(s).path.strip("/")
        if not path or "/" in path:
            return None
        s = path
    if re.fullmatch(r"[A-Za-z0-9_.]+", s):
        return s
    return None


async def _download(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=IMAGE_TIMEOUT, follow_redirects=True) as c:
        r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.content


async def fetch_post_images(url: str) -> list[bytes]:
    """Fetch image bytes for one Instagram post URL.

    Tries instaloader first (handles carousels), falls back to scraping og:image."""
    shortcode = parse_shortcode(url)
    if not shortcode:
        raise ValueError("Not a recognizable Instagram post URL (looking for /p/, /reel/, or /tv/).")

    urls = await _try_instaloader_post(shortcode)
    if not urls:
        urls = await _try_og_image(url)
    if not urls:
        raise RuntimeError("Could not extract any images. Instagram may be blocking scraping right now — try uploading the image directly instead.")

    return await asyncio.gather(*[_download(u) for u in urls])


async def _try_instaloader_post(shortcode: str) -> list[str]:
    try:
        import instaloader
        L = instaloader.Instaloader(download_pictures=False, download_video_thumbnails=False,
                                    download_videos=False, download_geotags=False,
                                    download_comments=False, save_metadata=False)
        loop = asyncio.get_running_loop()
        post = await loop.run_in_executor(
            None, lambda: instaloader.Post.from_shortcode(L.context, shortcode)
        )
        if post.typename == "GraphSidecar":
            urls = []
            for node in post.get_sidecar_nodes():
                if not node.is_video:
                    urls.append(node.display_url)
            return urls[:6]
        if not post.is_video:
            return [post.url]
        return []
    except Exception:
        return []


async def _try_og_image(page_url: str) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
            r = await c.get(page_url, headers={"User-Agent": "Mozilla/5.0"})
            html = r.text
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
        if m:
            return [m.group(1)]
    except Exception:
        pass
    return []


async def fetch_profile_images(username_or_url: str, limit: int = MAX_PROFILE_POSTS) -> tuple[str, list[bytes]]:
    """Fetch images from recent posts on a public profile.

    Returns (resolved_username, images). Raises on failure with a helpful message."""
    username = parse_username(username_or_url)
    if not username:
        raise ValueError("Couldn't parse a username. Give me @handle or https://instagram.com/handle.")

    try:
        import instaloader
    except ImportError:
        raise RuntimeError("instaloader is not installed. Run: pip install instaloader")

    L = instaloader.Instaloader(download_pictures=False, download_video_thumbnails=False,
                                download_videos=False, download_geotags=False,
                                download_comments=False, save_metadata=False)
    loop = asyncio.get_running_loop()

    def _crawl() -> list[str]:
        profile = instaloader.Profile.from_username(L.context, username)
        if profile.is_private:
            raise RuntimeError(f"@{username} is a private profile. P图 Detector 9000 does not do burglary.")
        urls = []
        for post in profile.get_posts():
            if len(urls) >= limit:
                break
            if post.typename == "GraphSidecar":
                for node in post.get_sidecar_nodes():
                    if not node.is_video and len(urls) < limit:
                        urls.append(node.display_url)
            elif not post.is_video:
                urls.append(post.url)
        return urls

    try:
        image_urls = await loop.run_in_executor(None, _crawl)
    except Exception as e:
        msg = str(e).lower()
        if "rate" in msg or "429" in msg or "wait" in msg or "login" in msg or "checkpoint" in msg:
            raise RuntimeError(
                "Instagram is rate-limiting or challenging this request. "
                "Try again in a few minutes, or use single-URL / upload mode instead."
            ) from e
        raise RuntimeError(f"Instagram scraping failed: {e}") from e

    if not image_urls:
        raise RuntimeError(f"Found no non-video posts on @{username}.")

    images = await asyncio.gather(*[_download(u) for u in image_urls])
    return username, images
