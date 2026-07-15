from __future__ import annotations

import os
import sys
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Ensure sibling modules are importable when Vercel invokes this file.
sys.path.append(str(Path(__file__).parent))

from analyzer import analyze_many
from scraper import fetch_post_images, fetch_profile_images
from ratelimit import check as rate_check, check_passcode

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

app = FastAPI(title="P图 Detector 9000")

PUBLIC_DIR = Path(__file__).parent.parent / "public"


async def _gate(request: Request):
    check_passcode(request)
    rate_check(request)


@app.post("/api/analyze/upload", dependencies=[Depends(_gate)])
async def analyze_upload(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "Send at least one image.")
    images = []
    for f in files[:8]:
        data = await f.read()
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(413, f"{f.filename} is over 15MB. Try a smaller photo.")
        images.append(data)
    result = await analyze_many(images)
    return {"source": "upload", **result}


@app.post("/api/analyze/url", dependencies=[Depends(_gate)])
async def analyze_url(url: str = Form(...)):
    try:
        images = await fetch_post_images(url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, str(e))
    result = await analyze_many(images)
    return {"source": "url", "url": url, **result}


@app.post("/api/analyze/profile", dependencies=[Depends(_gate)])
async def analyze_profile(username: str = Form(...)):
    try:
        resolved, images = await fetch_profile_images(username, limit=3)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, str(e))
    result = await analyze_many(images)
    return {"source": "profile", "username": resolved, **result}


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "api_key_set": bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")),
    }


# Local-dev static serving. On Vercel, /public is served by the edge directly
# and this code path isn't hit because vercel.json only routes /api/* here.
# The mount at "/" is added AFTER all @app routes, so API routes take priority.
if PUBLIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="root")
