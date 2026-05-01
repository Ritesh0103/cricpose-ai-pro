import mimetypes
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

CHUNK_SIZE = 1024 * 1024


def stream_file(request: Request, file_path: Path, media_type: str | None = None) -> StreamingResponse:
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Media file missing")

    media_type = media_type or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    start = 0
    end = file_size - 1
    status_code = 200
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": media_type,
        "Content-Length": str(file_size),
    }

    if range_header and range_header.startswith("bytes="):
        range_value = range_header.replace("bytes=", "")
        start_str, _, end_str = range_value.partition("-")
        if start_str:
            start = max(0, int(start_str))
        if end_str:
            end = min(file_size - 1, int(end_str))
        if start > end or start >= file_size:
            raise HTTPException(status_code=416, detail="Requested range not satisfiable")
        status_code = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(end - start + 1)

    def iterator():
        with file_path.open("rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(CHUNK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(iterator(), status_code=status_code, media_type=media_type, headers=headers)
