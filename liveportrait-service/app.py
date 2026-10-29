"""KaiCamp LivePortrait adapter.

This service is a first integration milestone: it accepts a source portrait and a
short camera-recorded driving video, runs the official LivePortrait inference
script, and returns the generated MP4. It is not a real-time webcam stream.
"""
from __future__ import annotations

import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

APP_DIR = Path(__file__).resolve().parent
LIVEPORTRAIT_HOME = Path(os.environ.get("LIVEPORTRAIT_HOME", "/opt/LivePortrait"))
INFERENCE_SCRIPT = LIVEPORTRAIT_HOME / "inference.py"
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(30 * 1024 * 1024)))
API_TOKEN = os.environ.get("KAICAMP_API_TOKEN", "")

app = FastAPI(title="KaiCamp LivePortrait Adapter", version="0.1.0")


def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
    # Do not expose an upload/inference endpoint publicly without a token.
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="Service is not configured: set KAICAMP_API_TOKEN.")
    expected = f"Bearer {API_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token.")


@app.get("/health")
def health():
    return {
        "ok": True,
        "engine": "LivePortrait",
        "inference_script_present": INFERENCE_SCRIPT.is_file(),
        "mode": "photo-plus-driving-video",
        "realtime": False,
    }


async def read_limited(upload: UploadFile, suffixes: tuple[str, ...]) -> bytes:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in suffixes:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix or 'none'}.")
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds the configured size limit.")
    return data


@app.post("/animate", dependencies=[Depends(require_token)])
async def animate(
    source: Annotated[UploadFile, File(description="Source portrait: JPG, JPEG, or PNG")],
    driving: Annotated[UploadFile, File(description="Short camera video: MP4, MOV, or WEBM")],
):
    if not INFERENCE_SCRIPT.is_file():
        raise HTTPException(status_code=503, detail=f"LivePortrait inference.py not found at {INFERENCE_SCRIPT}.")

    source_bytes = await read_limited(source, (".jpg", ".jpeg", ".png", ".webp"))
    driving_bytes = await read_limited(driving, (".mp4", ".mov", ".webm", ".m4v"))

    with tempfile.TemporaryDirectory(prefix="kaicamp-lp-") as temp:
        work = Path(temp)
        source_path = work / ("source" + Path(source.filename or "source.jpg").suffix.lower())
        driving_path = work / ("driving" + Path(driving.filename or "driving.mp4").suffix.lower())
        source_path.write_bytes(source_bytes)
        driving_path.write_bytes(driving_bytes)

        # Each request gets an isolated working directory to avoid mixing outputs.
        output_dir = work / "animations"
        output_dir.mkdir()
        cmd = [
            os.environ.get("PYTHON", "python"),
            str(INFERENCE_SCRIPT),
            "-s", str(source_path),
            "-d", str(driving_path),
            "--flag_crop_driving_video",
        ]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(LIVEPORTRAIT_HOME),
                env=env,
                capture_output=True,
                text=True,
                timeout=int(os.environ.get("INFERENCE_TIMEOUT_SECONDS", "240")),
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="LivePortrait inference timed out.")
        if proc.returncode != 0:
            # Keep details in server logs; do not return environment paths to clients.
            print("LivePortrait failed:", proc.stderr[-5000:])
            raise HTTPException(status_code=500, detail="LivePortrait inference failed. Check service logs.")

        # Official CLI versions commonly write output under animations/. Search only
        # this request's work directory; never return another user's generated file.
        candidates = list(work.rglob("*.mp4"))
        if not candidates:
            print("LivePortrait stdout:", proc.stdout[-3000:])
            print("LivePortrait stderr:", proc.stderr[-3000:])
            raise HTTPException(status_code=500, detail="Inference completed but no MP4 output was found.")

        result = max(candidates, key=lambda p: p.stat().st_mtime)
        # FileResponse streams the file; the temporary directory is removed afterward.
        persistent = APP_DIR / "outputs" / f"{secrets.token_hex(12)}.mp4"
        persistent.parent.mkdir(parents=True, exist_ok=True)
        persistent.write_bytes(result.read_bytes())

    return FileResponse(
        persistent,
        media_type="video/mp4",
        filename="kaicamp-liveportrait-result.mp4",
        background=BackgroundTask(lambda: persistent.unlink(missing_ok=True)),
    )
