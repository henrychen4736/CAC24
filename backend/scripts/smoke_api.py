"""End-to-end smoke test against a real server: start it, upload a clip, poll, print.

    python scripts/smoke_api.py path/to/clip.mp4 [--hint serve] [--handedness right]

Uses only the standard library on the client side so it exercises the same
multipart upload + polling flow the app uses.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def _request(url: str, data: bytes | None = None, headers: dict | None = None, method: str = "GET"):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def _multipart(fields: dict[str, str], file_field: str, path: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
        f'filename="{path.name}"\r\nContent-Type: video/mp4\r\n\r\n'.encode()
        + path.read_bytes()
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--hint", default="auto")
    ap.add_argument("--handedness", default="auto")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    base = f"http://127.0.0.1:{a.port}"

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tennis_ai.api.app:create_app", "--factory",
         "--port", str(a.port), "--log-level", "warning"],
    )
    try:
        deadline = time.time() + 60
        while True:
            try:
                status, health = _request(f"{base}/v1/health")
                break
            except (urllib.error.URLError, ConnectionError):
                if time.time() > deadline:
                    print("server did not start")
                    return 1
                time.sleep(0.5)
        print("health:", status, health)

        body, ctype = _multipart({"stroke_hint": a.hint, "handedness": a.handedness}, "file", a.video)
        status, job = _request(f"{base}/v1/analyses", body, {"Content-Type": ctype}, "POST")
        print("upload:", status, {k: job[k] for k in ("id", "status", "stage", "progress")})
        if status != 202:
            return 1

        t0, last = time.time(), None
        while job["status"] not in ("done", "failed"):
            time.sleep(1.0)
            _, job = _request(f"{base}/v1/analyses/{job['id']}")
            now = (job["stage"], round(job["progress"], 2))
            if now != last:
                print(f"  {time.time() - t0:5.1f}s  {job['status']:10s} {now[0]:9s} {now[1]:.2f}")
                last = now

        if job["status"] == "failed":
            print("failed:", job["error"])
            return 1
        r = job["result"]
        print("headline:", r["summary"]["headline"], "| overall", r["summary"]["overall_score"])
        print("strokes:", [(s["type"], s["contact_s"], s["score"]) for s in r["strokes"]])
        for p in r["summary"]["priorities"]:
            print(f"  priority: {p['title']} ({p['severity']}): {p['cue']}")

        status, _ = _request(f"{base}/v1/analyses/{job['id']}", method="DELETE")
        print("delete:", status, "| get after delete:", _request(f"{base}/v1/analyses/{job['id']}")[0])
        return 0
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
