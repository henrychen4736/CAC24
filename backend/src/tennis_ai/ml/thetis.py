"""THETIS dataset: download, file-name parsing, and label mapping.

THETIS (Gourgari et al., CVPRW 2013) — https://github.com/THETIS-dataset/dataset
1,980 RGB clips, 55 players (p1–p31 beginners, p32–p55 experts), 12 shot classes.
The authors state it is freely available for research purposes; cite the paper.
"""

from __future__ import annotations

import csv
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

API_ROOT = "https://api.github.com/repos/THETIS-dataset/dataset/contents/VIDEO_RGB"

# THETIS folder name -> app stroke type
CLASS_TO_STROKE: dict[str, str] = {
    "forehand_flat": "forehand",
    "forehand_openstands": "forehand",
    "forehand_slice": "forehand_slice",
    "forehand_volley": "forehand_volley",
    "backhand": "backhand_1h",
    "backhand2hands": "backhand_2h",
    "backhand_slice": "backhand_slice",
    "backhand_volley": "backhand_volley",
    "flat_service": "serve",
    "kick_service": "serve",
    "slice_service": "serve",
    "smash": "smash",
}

LAST_BEGINNER = 31  # p1..p31 beginners, p32..p55 experts

_NAME_RE = re.compile(r"^p(\d+)_([a-z0-9]+)_s(\d+)\.avi$", re.IGNORECASE)


@dataclass(frozen=True)
class ThetisClip:
    path: Path
    thetis_class: str
    stroke: str
    player: str
    skill: str
    repeat: int


def parse_clip(path: Path) -> ThetisClip | None:
    """Parse ``<root>/<class>/p12_foreflat_s2.avi``; returns None for unrelated files."""
    m = _NAME_RE.match(path.name)
    thetis_class = path.parent.name
    if not m or thetis_class not in CLASS_TO_STROKE:
        return None
    player_num = int(m.group(1))
    return ThetisClip(
        path=path,
        thetis_class=thetis_class,
        stroke=CLASS_TO_STROKE[thetis_class],
        player=f"p{player_num}",
        skill="beginner" if player_num <= LAST_BEGINNER else "expert",
        repeat=int(m.group(3)),
    )


def list_clips(root: Path) -> list[ThetisClip]:
    clips = [c for p in sorted(root.glob("*/*.avi")) if (c := parse_clip(p))]
    return clips


def write_manifest(root: Path, out_csv: Path) -> int:
    """Write a bring-your-own style manifest for the downloaded clips."""
    clips = list_clips(root)
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["video", "stroke", "skill", "player", "handedness"])
        for c in clips:
            w.writerow([c.path.relative_to(root).as_posix(), c.stroke, c.skill, c.player, ""])
    return len(clips)


# --------------------------------------------------------------------------- download


def _get_json(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _download(url: str, dest: Path, size: int) -> bool:
    if dest.exists() and dest.stat().st_size == size:
        return False
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
    tmp.replace(dest)
    return True


def fetch(
    out: Path,
    classes: list[str] | None = None,
    max_per_class: int | None = None,
    workers: int = 8,
) -> int:
    """Download THETIS RGB clips into ``out/<class>/``. Re-running skips finished files."""
    classes = classes or list(CLASS_TO_STROKE)
    unknown = set(classes) - set(CLASS_TO_STROKE)
    if unknown:
        raise ValueError(f"Unknown THETIS classes: {sorted(unknown)}")

    jobs: list[tuple[str, Path, int]] = []
    for cls in classes:
        entries = [e for e in _get_json(f"{API_ROOT}/{cls}") if e["name"].lower().endswith(".avi")]
        entries.sort(key=lambda e: e["name"])
        if max_per_class:
            entries = entries[:max_per_class]
        (out / cls).mkdir(parents=True, exist_ok=True)
        jobs += [(e["download_url"], out / cls / e["name"], e["size"]) for e in entries]

    total_mb = sum(s for _, _, s in jobs) / 1e6
    print(f"THETIS: {len(jobs)} clips in {len(classes)} classes ({total_mb:.0f} MB)")
    done = downloaded = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download, url, dest, size): dest for url, dest, size in jobs}
        for fut in as_completed(futures):
            downloaded += fut.result()
            done += 1
            if done % 50 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)} ({downloaded} new)", flush=True)

    n = write_manifest(out, out / "manifest.csv")
    print(f"Wrote {out / 'manifest.csv'} ({n} clips)")
    return n
