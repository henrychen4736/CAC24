import numpy as np
import pytest
from synthetic import still_sequence, swing_sequence

from tennis_ai.ml.features import NUM_FEATURES, T_OUT, rotate_features, stroke_features
from tennis_ai.pipeline.analyzer import build_report
from tennis_ai.pipeline.classify import StrokeClassifier, heuristic_decision
from tennis_ai.pipeline.errors import AnalysisError
from tennis_ai.pipeline.feedback import load_references, rate
from tennis_ai.pipeline.preprocess import _fill_gaps, prepare
from tennis_ai.pipeline.segment import detect_strokes


def test_fill_gaps_only_fills_short_interior_gaps():
    x = np.arange(20, dtype=float)[:, None]
    x[3:5] = np.nan     # short interior gap -> filled
    x[10:17] = np.nan   # long gap -> kept
    x[0] = np.nan       # leading edge -> kept
    out = _fill_gaps(x, max_gap=3)
    assert np.allclose(out[3:5, 0], [3, 4])
    assert np.isnan(out[10:17]).all()
    assert np.isnan(out[0, 0])


def test_handedness_detected_and_mirrored():
    right = prepare(swing_sequence())
    left = prepare(swing_sequence(left_handed=True))
    assert (right.handedness, right.handedness_source) == ("right", "detected")
    assert (left.handedness, left.handedness_source) == ("left", "detected")
    # after mirroring, a lefty forehand looks like a righty forehand
    assert heuristic_decision(left, detect_strokes(left)[0]).family == "forehand"


def test_user_handedness_overrides_detection():
    prep = prepare(swing_sequence(), handedness="left")
    assert (prep.handedness, prep.handedness_source) == ("left", "user")


def test_detects_each_stroke_near_its_contact():
    seq = swing_sequence(contacts_s=(1.5, 4.0, 6.5), duration_s=8.0)
    strokes = detect_strokes(prepare(seq))
    assert [round(w.contact / seq.fps, 1) for w in strokes] == pytest.approx([1.5, 4.0, 6.5], abs=0.1)


def test_no_strokes_when_player_stands_still():
    assert detect_strokes(prepare(still_sequence())) == []


@pytest.mark.parametrize("kind,family", [
    ("forehand", "forehand"), ("backhand", "backhand"), ("serve", "overhead"),
])
def test_heuristic_family(kind, family):
    prep = prepare(swing_sequence(kind))
    decision = heuristic_decision(prep, detect_strokes(prep)[0])
    assert decision.family == family
    assert decision.source == "heuristic"


def test_two_handed_backhand_detected():
    prep = prepare(swing_sequence("backhand"))
    assert heuristic_decision(prep, detect_strokes(prep)[0]).type == "backhand_2h"


def test_user_hint_wins_over_heuristic():
    prep = prepare(swing_sequence("forehand"))
    d = heuristic_decision(prep, detect_strokes(prep)[0], hint="serve")
    assert (d.type, d.family, d.source) == ("serve", "overhead", "user")


@pytest.mark.parametrize("value,expected", [
    (0.5, ("good", 100)), (0.2, ("fair", None)), (0.0, ("needs_work", None)),
])
def test_rate_bands(value, expected):
    rating, score, _ = rate(value, [0.25, None], [0.1, None])
    assert rating == expected[0]
    if expected[1] is not None:
        assert score == expected[1]
    assert 0 <= score <= 100


def test_rate_score_decreases_with_distance():
    scores = [rate(v, [10, 20], [5, 25])[1] for v in (20, 22, 25, 28, 40)]
    assert scores == sorted(scores, reverse=True)


def test_features_are_camera_yaw_invariant():
    a = prepare(swing_sequence())
    b = prepare(swing_sequence(camera_yaw=np.radians(70)))
    fa = stroke_features(a, detect_strokes(a)[0].contact)
    fb = stroke_features(b, detect_strokes(b)[0].contact)
    assert fa.shape == (T_OUT, NUM_FEATURES)
    assert np.abs(fa - fb).max() < 0.05


def test_features_are_frame_rate_invariant():
    """THETIS trains at ~18 fps; phones film at 30–60. The same swing must look the same."""
    from tennis_ai.ml.features import POS, VEL

    def feats(fps):
        prep = prepare(swing_sequence(fps=fps))
        return stroke_features(prep, detect_strokes(prep)[0].contact)

    d = np.abs(feats(18.0) - feats(60.0))
    assert d[:, POS].max() < 0.1
    assert d[:, VEL].mean() < 0.005


def test_rotate_features_roundtrip():
    prep = prepare(swing_sequence())
    x = stroke_features(prep, detect_strokes(prep)[0].contact)
    assert np.allclose(rotate_features(rotate_features(x, 0.4), -0.4), x, atol=1e-5)


def test_report_end_to_end_is_json_ready():
    seq = swing_sequence(contacts_s=(1.5, 4.0), duration_s=6.0)
    report = build_report(seq, "auto", "auto", StrokeClassifier(), load_references())
    data = report.model_dump(mode="json")
    assert len(data["strokes"]) == 2
    assert data["summary"]["overall_score"] is not None
    assert len(data["pose_track"]["frames"]) == seq.num_frames
    assert len(data["pose_track"]["frames"][0]) == 2 * len(data["pose_track"]["joints"])
    priority_ids = [p["metric_id"] for p in data["summary"]["priorities"]]
    assert len(priority_ids) == len(set(priority_ids))
    stroke = data["strokes"][0]
    assert stroke["family"] == "forehand"
    assert {m["id"] for m in stroke["metrics"]} >= {"shoulder_rotation", "contact_elbow_angle"}
    for m in stroke["metrics"]:
        assert m["rating"] in ("good", "fair", "needs_work", "info")
        assert (m["cue"] is None) == (m["rating"] in ("good", "info"))


def test_report_rotation_metric_is_camera_independent():
    def rotation(seq):
        r = build_report(seq, "auto", "auto", StrokeClassifier(), load_references())
        return next(m["value"] for m in r.model_dump()["strokes"][0]["metrics"]
                    if m["id"] == "shoulder_rotation")

    assert rotation(swing_sequence()) == pytest.approx(
        rotation(swing_sequence(camera_yaw=np.radians(80))), abs=3.0)


def test_hint_drops_strokes_that_cannot_match():
    refs, clf = load_references(), StrokeClassifier()
    # a forehand can't be a serve (contact far below the head) -> dropped
    assert build_report(swing_sequence("forehand"), "serve", "auto", clf, refs).strokes == []
    # a real serve survives the serve hint and is classified as one
    serve = build_report(swing_sequence("serve"), "serve", "auto", clf, refs).strokes
    assert [s.family for s in serve] == ["overhead"]


def test_serve_contact_snaps_to_highest_reach():
    report = build_report(swing_sequence("serve"), "auto", "auto", StrokeClassifier(),
                          load_references())
    stroke = report.strokes[0]
    assert stroke.family == "overhead"
    height = next(m.value for m in stroke.metrics if m.id == "contact_height")
    assert height > 0.5


def test_serve_windup_is_not_a_separate_stroke():
    seq = swing_sequence("serve", contacts_s=(2.0,), duration_s=3.5, windup=True)
    # the raw detector sees two fast motions: the windup and the hit
    assert len(detect_strokes(prepare(seq))) == 2
    report = build_report(seq, "auto", "auto", StrokeClassifier(), load_references())
    assert [(s.family, round(s.contact_s, 1)) for s in report.strokes] == [("overhead", 2.0)]


def test_no_player_is_an_error():
    seq = swing_sequence()
    seq.valid[:] = False
    with pytest.raises(AnalysisError) as e:
        build_report(seq, "auto", "auto", StrokeClassifier(), load_references())
    assert e.value.code == "no_player_detected"


def test_still_video_reports_no_strokes_warning():
    report = build_report(still_sequence(), "auto", "auto", StrokeClassifier(), load_references())
    assert report.strokes == []
    assert report.summary.overall_score is None
    assert "no_strokes" in [w.code for w in report.quality.warnings]
