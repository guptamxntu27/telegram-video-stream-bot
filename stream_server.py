
import os
import math
import mimetypes
import asyncio

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION = os.environ.get("TELETHON_SESSION", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
STREAM_TOKEN = os.environ.get("STREAM_TOKEN", "")

CHUNK_SIZE = 512 * 1024

app = FastAPI(title="Telegram Video Streaming Backend")
client = None


@app.on_event("startup")
async def startup():
    global client

    if not all([API_ID, API_HASH, SESSION, CHANNEL_ID, STREAM_TOKEN]):
        raise RuntimeError(
            "Set API_ID, API_HASH, TELETHON_SESSION, "
            "CHANNEL_ID and STREAM_TOKEN in Environment."
        )

    client = TelegramClient(
        StringSession(SESSION),
        API_ID,
        API_HASH,
    )
    await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError(
            "Telegram session is not authorized. Create a valid session first."
        )


@app.on_event("shutdown")
async def shutdown():
    if client and client.is_connected():
        await client.disconnect()


@app.get("/")
async def home():
    return {
        "status": "ready",
        "message": "Telegram streaming backend is running",
    }


@app.get("/video/{message_id}")
async def video(
    message_id: int,
    token: str = Query(...),
    download: bool = False,
    range_header: str | None = None,
):
    if not STREAM_TOKEN or token != STREAM_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        message = await client.get_messages(
            CHANNEL_ID,
            ids=message_id,
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Telegram request failed")

    if not message or not message.media or not message.file:
        raise HTTPException(status_code=404, detail="Video not found")

    size = message.file.size
    if not size:
        raise HTTPException(status_code=404, detail="File size unavailable")

    filename = message.file.name or f"video-{message_id}.mp4"
    mime_type = message.file.mime_type or (
        mimetypes.guess_type(filename)[0] or "application/octet-stream"
    )

    start, end = 0, size - 1
    status_code = 200

    if range_header:
        try:
            unit, value = range_header.split("=", 1)
            if unit != "bytes" or "," in value:
                raise ValueError()

            first, last = value.split("-", 1)
            if first:
                start = int(first)
                end = int(last) if last else size - 1
            else:
                suffix_length = int(last)
                start = max(0, size - suffix_length)

            if start >= size or end < start:
                raise ValueError()

            end = min(end, size - 1)
            status_code = 206
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=416,
                detail="Invalid byte range",
                headers={"Content-Range": f"bytes */{size}"},
            )

    length = end - start + 1

    async def stream_file():
        iterator = client.iter_download(
            message.media,
            offset=start,
            limit=math.ceil(length / CHUNK_SIZE),
            request_size=CHUNK_SIZE,
            chunk_size=CHUNK_SIZE,
            file_size=size,
        )

        sent = 0
        try:
            async for chunk in iterator:
                remaining = length - sent
                if remaining <= 0:
                    break

                data = bytes(chunk[:remaining])
                sent += len(data)
                yield data

                if sent >= length:
                    break
        finally:
            close = getattr(iterator, "close", None)
            if close:
                await close()

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Disposition": (
            f'attachment; filename="{filename}"'
            if download else f'inline; filename="{filename}"'
        ),
        "Cache-Control": "private, no-store",
    }

    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    return StreamingResponse(
        stream_file(),
        status_code=status_code,
        media_type=mime_type,
        headers=headers,
    )


@app.get("/health")
async def health():
    return JSONResponse({"ok": True})
