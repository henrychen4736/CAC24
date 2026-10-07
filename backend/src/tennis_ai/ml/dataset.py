"""Read cached poses back as prepared, labelled strokes (for calibration)."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from ..pipeline.preprocess import Prepared, prepare
from ..pipeline.segment import StrokeWindow, strongest_stroke
from ..pipeline.strokes import FAMILY_OF, fits_family, heuristic_cues
from .extract import load_sequence, read_index


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
        family = FAMILY_OF.get(row.get("stroke", ""))

        def plausible(w, prep=prep, family=family) -> bool:
            return family is None or fits_family(heuristic_cues(prep, w), family)

        w: StrokeWindow | None = strongest_stroke(prep, accept=plausible)
        if w is None:
            continue
        yield row, prep, w

