"""The training path end to end on synthetic poses: cache → dataset → train → ONNX → service."""

import csv

import numpy as np
import pytest
from synthetic import swing_sequence

from tennis_ai.ml.dataset import build_dataset
from tennis_ai.ml.extract import INDEX_FIELDS, load_sequence, save_sequence
from tennis_ai.ml.features import NUM_FEATURES, T_OUT
from tennis_ai.pipeline.classify import STROKE_TYPES, StrokeClassifier
from tennis_ai.pipeline.preprocess import prepare
from tennis_ai.pipeline.segment import detect_strokes

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


def test_build_dataset_and_cache(pose_dir):
    ds = build_dataset(pose_dir)
    assert ds.X.shape == (12, T_OUT, NUM_FEATURES)
    assert set(ds.heuristic) <= set(STROKE_TYPES)
    # serve clips have a windup; the label must steer the window to the actual hit
    assert set(ds.heuristic[ds.stroke == "serve"]) == {"serve"}
    cached = build_dataset(pose_dir)
    assert np.array_equal(cached.X, ds.X)
    assert list(cached.file) == list(ds.file)


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


def test_train_export_and_serve(pose_dir, tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("onnx")
    from tennis_ai.ml.train import train

    out = tmp_path / "models"
    meta = train(pose_dir, out, epochs=2, seed=0)
    assert (out / "stroke_model.onnx").exists()
    assert set(meta["classes"]) == set(KINDS.values())
    assert "heuristic_baseline" in meta["validation"]

    clf = StrokeClassifier.load(out / "stroke_model.onnx")
    assert clf.name.startswith("learned:")
    prep = prepare(swing_sequence("forehand"))
    decision = clf.classify(prep, detect_strokes(prep)[0])
    assert decision.source == "model"
    assert decision.type in meta["classes"]
    assert 0.0 <= decision.skill_score <= 1.0
    hinted = clf.classify(prep, detect_strokes(prep)[0], hint="serve")
    assert (hinted.family, hinted.source) == ("overhead", "user")

    # the expert-likeness score stays out of reports unless explicitly enabled
    from tennis_ai.pipeline.analyzer import build_report
    from tennis_ai.pipeline.feedback import load_references

    seq, refs = swing_sequence("forehand"), load_references()
    assert build_report(seq, "auto", "auto", clf, refs).strokes[0].skill_score is None
    shown = build_report(seq, "auto", "auto", clf, refs, expose_skill=True).strokes[0]
    assert shown.skill_score is not None and shown.type_source == "model"
