"""Turn cached poses into training arrays (features + labels)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..pipeline.classify import FAMILY_OF, fits_hint, heuristic_cues, heuristic_decision
from ..pipeline.preprocess import Prepared, prepare
from ..pipeline.segment import StrokeWindow, strongest_stroke
from .extract import load_sequence, read_index
from .features import FEATURE_VERSION, stroke_features

DATASET_VERSION = 2  # bump when the choice of stroke window per clip changes (invalidates caches)
_HINT_FOR_FAMILY = {"forehand": "forehand", "backhand": "backhand", "overhead": "serve"}


@dataclass
class Dataset:
    X: np.ndarray            # (N, T, F) float32
    stroke: np.ndarray       # (N,) str
    skill: np.ndarray        # (N,) str: expert | beginner | ""
    player: np.ndarray       # (N,) str
    file: np.ndarray         # (N,) str
    heuristic: np.ndarray    # (N,) str: the heuristic classifier's prediction (baseline)


def player_handedness(pose_dir: Path, rows: list[dict]) -> dict[str, str]:
    """Majority vote of confident per-clip detections, per player.

    Handedness is a property of the player, not the clip. Backhands are
    ambiguous on their own (the free arm swings fast too), so only forehands
    and overheads vote, and the result applies to all of the player's clips.
    """
    votes: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        if not row.get("player") or row.get("handedness", "auto") not in ("", "auto"):
            continue
        if FAMILY_OF.get(row.get("stroke", ""), "backhand") == "backhand":
            continue
        seq = load_sequence(pose_dir / row["file"])
        if not seq.valid.any():
            continue
        prep = prepare(seq, "auto")
        if prep.handedness_source == "detected":
            votes[row["player"]][prep.handedness] += 1
    return {p: c.most_common(1)[0][0] for p, c in votes.items()}


def prepared_clips(pose_dir: Path, min_valid: float = 0.5):
    """Yield (index row, Prepared, StrokeWindow) for every usable cached clip."""
    rows = read_index(pose_dir)
    hands = player_handedness(pose_dir, rows)
    for row in rows:
        seq = load_sequence(pose_dir / row["file"])
        if seq.num_frames == 0 or seq.valid.mean() < min_valid:
            continue
        hand = row.get("handedness") or "auto"
        if hand == "auto":
            hand = hands.get(row.get("player", ""), "auto")
        prep: Prepared = prepare(seq, hand)
        # the label is known: only pick a swing that can be that stroke (a serve's
        # windup must not be mistaken for the hit)
        hint = _HINT_FOR_FAMILY.get(FAMILY_OF.get(row.get("stroke", ""), ""), "auto")

        def plausible(w, prep=prep, hint=hint) -> bool:
            return fits_hint(heuristic_cues(prep, w), hint)

        w: StrokeWindow | None = strongest_stroke(prep, accept=plausible)
        if w is None:
            continue
        yield row, prep, w


def build_dataset(pose_dir: Path, cache: Path | None = None) -> Dataset:
    cache = cache or pose_dir / f"dataset_f{FEATURE_VERSION}_d{DATASET_VERSION}.npz"
    index_mtime = (pose_dir / "index.csv").stat().st_mtime
    if cache.exists() and cache.stat().st_mtime > index_mtime:
        d = np.load(cache, allow_pickle=False)
        return Dataset(d["X"], d["stroke"], d["skill"], d["player"], d["clip_file"], d["heuristic"])

    xs, strokes, skills, players, files, heur = [], [], [], [], [], []
    for row, prep, w in prepared_clips(pose_dir):
        if not row["stroke"]:
            continue
        xs.append(stroke_features(prep, w.contact))
        strokes.append(row["stroke"])
        skills.append(row.get("skill", ""))
        players.append(row.get("player", "") or row["file"])
        files.append(row["file"])
        heur.append(heuristic_decision(prep, w).type)
    ds = Dataset(np.stack(xs), np.array(strokes), np.array(skills), np.array(players),
                 np.array(files), np.array(heur))
    # (key can't be "file": that's savez_compressed's own first parameter)
    np.savez_compressed(cache, X=ds.X, stroke=ds.stroke, skill=ds.skill, player=ds.player,
                        clip_file=ds.file, heuristic=ds.heuristic)
    return ds
