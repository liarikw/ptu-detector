from __future__ import annotations

import base64
import json
import os
import asyncio
import httpx

MODEL = os.getenv("PTU_MODEL", "gemini-flash-latest")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

# ────────────────────────────────────────────────────────────────
# EDIT ME: What the scanner should look for and how it should sound.
# Just tweak the sections below and restart uvicorn — no other changes needed.
# ────────────────────────────────────────────────────────────────

PERSONA = """You are P图 Detector 9000 — a quirky, playful vision agent that inspects photos for signs of digital editing (Photoshop, FaceApp, Facetune, AI touch-ups, filters, warping, liquify, etc.). Your job is to be FUN, not cruel — you roast the *photo* (the pixels, the geometry, the lighting), never the person."""

TELLS_TO_LOOK_FOR = """Look carefully for these specific editing tells, and mention any you actually see:

FACE & SKIN
- Over-smoothed skin with no pores (the "rice cooker" or "wax figure" look)
- Enlarged/reshaped eyes, or eyes that don't quite match each other
- Sharpened eyelashes or unnaturally symmetric eyebrows
- Skin tone that's uniformly too pale, too warm, or too smooth to be real
- Teeth that look like a piano-key stock photo — flat, uniform, unnaturally white
- Jawline / chin edges that don't blend into the neck naturally
- Nose bridge or nostril edges that look "carved" or too crisp

BODY & PROPORTION
- Waist that pulls a wall/doorframe/tile inward behind it (liquify tell)
- Legs that look stretched relative to torso
- Fingers or hands with weird count, blurred edges, or floating jewelry
- Arms that taper too smoothly, like a Snapchat filter

COLOR & LIGHTING
- Over-saturated colors, or the opposite: unnaturally muted / desaturated (heavy filter)
- Skin lit from one direction but background lit from another (composite tell)
- Shadows that don't match where the highlights are
- HDR crunch — everything equally sharp with no natural depth-of-field
- Halo edges around hair or shoulders where the subject was cut out and re-laid
- Skin tone that's ghostly-pale in a way that doesn't match the ambient lighting
- Instagram-orange skin tones that look spray-tanned by the algorithm
- Colors that all sit in the same narrow band (a filter "preset" tell)

BACKGROUND & GEOMETRY
- Straight lines that bend near the subject (doorframes, tiles, brick lines, window frames)
- Repeated textures where healing/clone brush was used
- Warping in reflective surfaces (mirrors, phone screens, tile floors)
- Objects behind the subject that partially disappear or blur unnaturally

If none of the above are present, say so directly and give a LOW sus score."""

TONE_RULES = """Ground rules:
- NEVER comment on the person's appearance, weight, attractiveness, or identity. Never say anything demeaning about how someone looks naturally.
- ONLY roast the technical signs of editing listed above.
- Be playful and quirky. Wordplay, absurd metaphors, mock-serious forensic voice. Think "P图 Detective in a raincoat" not "internet troll".
- If the photo looks unedited, celebrate that! Give a low sus score and compliment the photo integrity."""

SCORE_BANDS = """Return a Sus Score from 0 to 100:
- 0-20: "Certified Raw Dog" (looks totally untouched)
- 21-40: "A Whisper of Facetune" (minor cleanup — maybe a single soft filter)
- 41-60: "Suspicious Activity" (something's off — mild reshaping or color work)
- 61-80: "Heavily P图'd" (multiple obvious tells)
- 81-100: "Uncanny Valley Alert" (this is basically CGI now)"""

# ────────────────────────────────────────────────────────────────
# Assembled prompt — you probably don't need to touch this line.
# ────────────────────────────────────────────────────────────────
SYSTEM = f"""{PERSONA}

{TELLS_TO_LOOK_FOR}

{TONE_RULES}

{SCORE_BANDS}

Output only the JSON matching the schema — no preamble, no markdown fences."""

SCHEMA = {
    "type": "object",
    "properties": {
        "sus_score": {
            "type": "integer",
            "description": "Sus Score 0-100",
        },
        "verdict": {
            "type": "string",
            "enum": [
                "Certified Raw Dog",
                "A Whisper of Facetune",
                "Suspicious Activity",
                "Heavily P图'd",
                "Uncanny Valley Alert",
            ],
        },
        "roast": {
            "type": "string",
            "description": "Playful 2-4 sentence roast of the photo's editing tells. Focus on pixels/geometry/lighting, never the person.",
        },
        "findings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 short bullet observations about editing tells or the lack thereof",
        },
    },
    "required": ["sus_score", "verdict", "roast", "findings"],
}


def _api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) is not set. "
            "Grab a free key at https://aistudio.google.com/apikey and export it."
        )
    return key


def _guess_media_type(image_bytes: bytes) -> str:
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


async def analyze_image(image_bytes: bytes) -> dict:
    """Analyze a single image via Gemini and return sus_score/verdict/roast/findings."""
    api_key = _api_key()
    media_type = _guess_media_type(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": media_type, "data": b64}},
                    {
                        "text": "Inspect this photo for signs of P图 (photoshop / facetune / AI edits). "
                                "Focus purely on technical editing tells in the pixels — do not "
                                "describe the person. Return the JSON matching the schema."
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.9,
            "response_mime_type": "application/json",
            "response_schema": SCHEMA,
        },
        # Loosen safety filters — this is a benign photo-forensics use case
        # and Gemini's defaults over-block on ordinary photos of people.
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }

    # Use ?key= query-param auth — the method the AI Studio docs use;
    # works universally across API key formats.
    url = f"{ENDPOINT}/{MODEL}:generateContent"
    headers = {"content-type": "application/json"}
    params = {"key": api_key}

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, params=params, json=payload)

    print(f"[analyzer] Gemini status={r.status_code}, body_preview={r.text[:600]!r}", flush=True)

    if r.status_code >= 400:
        raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:500]}")

    data = r.json()

    # Check for prompt-level block (Gemini refused the whole request)
    block = data.get("promptFeedback", {}).get("blockReason")
    if block:
        raise RuntimeError(f"Gemini blocked the request (blockReason={block}).")

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates. Raw: {json.dumps(data)[:400]}")

    cand = candidates[0]
    finish = cand.get("finishReason", "")
    parts = cand.get("content", {}).get("parts", [])

    if not parts:
        raise RuntimeError(
            f"Gemini returned an empty response (finishReason={finish}). "
            f"Often this means the photo tripped a safety filter — try a different photo."
        )

    text = parts[0].get("text", "")
    if not text:
        raise RuntimeError(f"Gemini returned no text (finishReason={finish}).")

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gemini returned non-JSON: {e}. Raw text: {text[:300]}")

    if "sus_score" not in result:
        raise RuntimeError(
            f"Gemini didn't follow the schema (finishReason={finish}). "
            f"Got keys: {list(result.keys())}. Raw: {json.dumps(result)[:300]}"
        )

    return result


async def analyze_many(images: list[bytes]) -> dict:
    """Analyze multiple images and produce a combined verdict.

    Gemini free tier is ~15 req/min for Flash — serialize to stay comfortably under it."""
    per_image: list[dict] = []
    for i, img in enumerate(images):
        try:
            result = await analyze_image(img)
            per_image.append({"index": i, **result})
        except Exception as e:
            per_image.append({"index": i, "error": str(e)})
        if i < len(images) - 1:
            await asyncio.sleep(0.5)

    scored = [p for p in per_image if "sus_score" in p]
    if not scored:
        return {"images": per_image, "aggregate_score": None, "aggregate_verdict": "Inconclusive"}

    avg = round(sum(p["sus_score"] for p in scored) / len(scored))
    if avg <= 20:
        agg_verdict = "Certified Raw Dog"
    elif avg <= 40:
        agg_verdict = "A Whisper of Facetune"
    elif avg <= 60:
        agg_verdict = "Suspicious Activity"
    elif avg <= 80:
        agg_verdict = "Heavily P图'd"
    else:
        agg_verdict = "Uncanny Valley Alert"

    return {
        "images": per_image,
        "aggregate_score": avg,
        "aggregate_verdict": agg_verdict,
        "image_count": len(images),
    }
