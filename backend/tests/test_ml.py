"""Dataset tooling end to end on synthetic poses: pose cache → prepared clips → calibration."""

import csv

import numpy as np
import pytest
from synthetic import swing_sequence

from tennis_ai.ml.extract import INDEX_FIELDS, load_sequence, save_sequence

KINDS = {"forehand": "forehand", "backhand": "backhand_2h", "serve": "serve"}


@pytest.fixture
def pose_dir(tmp_path):
    rows = []
    for player, skill in [("e0", "expert"), ("e1", "expert"), ("b0", "beginner"), ("b1", "beginner")]:
        for kind, stroke in KINDS.items():
            name = f"{player}_{kind}.npz"
            seq = (swing_sequence(kind, contacts_s=(2.0,), duration_s=3.5, windup=True)
                   if kind == "serve" else swing_sequence(kind))
            save_sequence(seq, tmp_path / name)
            rows.append([name, "", stroke, skill, player, ""])
    with (tmp_path / "index.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(INDEX_FIELDS)
        w.writerows(rows)
    return tmp_path


def test_pose_cache_roundtrip(tmp_path):
    seq = swing_sequence()
    save_sequence(seq, tmp_path / "a.npz")
    back = load_sequence(tmp_path / "a.npz")
    assert np.allclose(back.kp3d, seq.kp3d) and back.fps == seq.fps and back.model == seq.model


def test_prepared_clips_pick_the_labelled_stroke(pose_dir):
    from tennis_ai.ml.dataset import prepared_clips

    clips = list(prepared_clips(pose_dir))
    assert len(clips) == 12
    # serve clips have a windup; the label must steer the window to the actual hit
    for row, prep, w in clips:
        if row["stroke"] == "serve":
            assert round(w.contact / prep.fps, 1) == 2.0


def test_calibrate_writes_ranges_the_service_uses(pose_dir, tmp_path):
    from tennis_ai.ml.calibrate import calibrate
    from tennis_ai.pipeline.feedback import load_references

    out = tmp_path / "reference_calibrated.json"
    doc = calibrate(pose_dir, out, skill="expert", min_n=2)
    assert doc["clips"] == 6  # 2 expert players x 3 strokes
    fam = doc["families"]["forehand"]
    assert "swing_speed" not in fam  # informational in the defaults -> stays informational
    # the synthetic clips are filmed from behind: depth-dependent metrics keep their defaults
    assert "shoulder_rotation" not in fam and "stance_width" not in fam
    for rng in fam.values():
        assert rng["good"][1] is None or rng["good"][0] is None or rng["good"][0] <= rng["good"][1]

    # swings without a ball say nothing about leg drive into a ball
    shadow = calibrate(pose_dir, tmp_path / "shadow.json", skill="expert", min_n=2, shadow=True)
    assert "leg_drive" in doc["families"].get("overhead", {})
    assert "leg_drive" not in shadow["families"].get("overhead", {})

    refs = load_references(out)
    assert refs.source == "calibrated"
    entry, source = refs.lookup("forehand", "forehand", "knee_flexion")
    assert source == "calibrated" and entry["good"] == fam["knee_flexion"]["good"]

