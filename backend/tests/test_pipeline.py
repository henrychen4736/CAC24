import numpy as np
import pytest
from synthetic import still_sequence, swing_sequence

from tennis_ai.pipeline.analyzer import build_report
from tennis_ai.pipeline.errors import AnalysisError
from tennis_ai.pipeline.feedback import load_references, rate
from tennis_ai.pipeline.preprocess import _fill_gaps, prepare
from tennis_ai.pipeline.segment import detect_strokes
from tennis_ai.pipeline.strokes import fits_family, heuristic_cues


def _report(seq, stroke_type="forehand", handedness="right"):
    return build_report(seq, stroke_type, handedness, load_references())


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


def test_lefty_is_mirrored_into_a_righty():
    def values(seq, hand):
        return {m.id: m.value for m in _report(seq, handedness=hand).strokes[0].metrics}

    right, left = values(swing_sequence(), "right"), values(swing_sequence(left_handed=True), "left")
    for mid in ("contact_elbow_angle", "knee_flexion", "trunk_lean"):
        assert left[mid] == pytest.approx(right[mid], abs=2.0)


def test_user_handedness_overrides_detection():
    prep = prepare(swing_sequence(), handedness="left")
    assert (prep.handedness, prep.handedness_source) == ("left", "user")


def test_detects_each_stroke_near_its_contact():
    seq = swing_sequence(contacts_s=(1.5, 4.0, 6.5), duration_s=8.0)
    strokes = detect_strokes(prepare(seq))
    assert [round(w.contact / seq.fps, 1) for w in strokes] == pytest.approx([1.5, 4.0, 6.5], abs=0.1)


def test_no_strokes_when_player_stands_still():
    assert detect_strokes(prepare(still_sequence())) == []


@pytest.mark.parametrize("kind,fits,misfit", [
    ("forehand", "forehand", "overhead"), ("backhand", "backhand", "overhead"),
    ("serve", "overhead", "forehand"),
])
def test_plausibility_check_matches_family(kind, fits, misfit):
    prep = prepare(swing_sequence(kind))
    cues = heuristic_cues(prep, detect_strokes(prep)[0])
    assert fits_family(cues, fits)
    assert not fits_family(cues, misfit)


@pytest.mark.parametrize("stroke_type,family", [
    ("forehand_slice", "forehand"), ("backhand_1h", "backhand"), ("backhand_volley", "backhand"),
])
def test_user_stroke_type_is_used_as_given(stroke_type, family):
    kind = "forehand" if family == "forehand" else "backhand"
    stroke = _report(swing_sequence(kind), stroke_type).strokes[0]
    assert (stroke.type, stroke.family) == (stroke_type, family)


def test_rejects_auto_stroke_type_and_handedness():
    with pytest.raises(ValueError):
        _report(swing_sequence(), stroke_type="auto")
    with pytest.raises(ValueError):
        _report(swing_sequence(), handedness="auto")


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


def test_report_end_to_end_is_json_ready():
    seq = swing_sequence(contacts_s=(1.5, 4.0), duration_s=6.0)
    data = _report(seq).model_dump(mode="json")
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
        r = _report(seq)
        return next(m["value"] for m in r.model_dump()["strokes"][0]["metrics"]
                    if m["id"] == "shoulder_rotation")

    assert rotation(swing_sequence()) == pytest.approx(
        rotation(swing_sequence(camera_yaw=np.radians(80))), abs=3.0)


def test_strokes_that_cannot_match_the_users_choice_are_dropped():
    # a forehand can't be a serve (contact far below the head) -> dropped
    assert _report(swing_sequence("forehand"), "serve").strokes == []
    # a serve can't be a forehand (a clear overhead) -> dropped
    assert _report(swing_sequence("serve"), "forehand").strokes == []
    serve = _report(swing_sequence("serve"), "serve").strokes
    assert [(s.type, s.family) for s in serve] == [("serve", "overhead")]


def test_serve_contact_snaps_to_highest_reach():
    stroke = _report(swing_sequence("serve"), "serve").strokes[0]
    assert stroke.family == "overhead"
    height = next(m.value for m in stroke.metrics if m.id == "contact_height")
    assert height > 0.5


def test_serve_windup_is_not_a_separate_stroke():
    seq = swing_sequence("serve", contacts_s=(2.0,), duration_s=3.5, windup=True)
    # the raw detector sees two fast motions: the windup and the hit
    assert len(detect_strokes(prepare(seq))) == 2
    report = _report(seq, "serve")
    assert [(s.family, round(s.contact_s, 1)) for s in report.strokes] == [("overhead", 2.0)]


def test_no_player_is_an_error():
    seq = swing_sequence()
    seq.valid[:] = False
    with pytest.raises(AnalysisError) as e:
        _report(seq)
    assert e.value.code == "no_player_detected"


def test_still_video_reports_no_strokes_warning():
    report = _report(still_sequence())
    assert report.strokes == []
    assert report.summary.overall_score is None
    assert "no_strokes" in [w.code for w in report.quality.warnings]
