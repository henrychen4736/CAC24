import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from synthetic import swing_sequence

from tennis_ai.api.app import create_app
from tennis_ai.config import Settings
from tennis_ai.pipeline.analyzer import build_report
from tennis_ai.pipeline.classify import StrokeClassifier
from tennis_ai.pipeline.errors import AnalysisError
from tennis_ai.pipeline.feedback import load_references


class FakeAnalyzer:
    pose = SimpleNamespace(name="fake-pose")
    classifier = StrokeClassifier()
    references = load_references()

    def __init__(self):
        self.seen = []

    def analyze(self, path, stroke_hint, handedness, progress):
        self.seen.append((path.read_bytes(), stroke_hint, handedness))
        assert path.exists()
        progress("pose", 0.5)
        if path.read_bytes() == b"no-player":
            raise AnalysisError("no_player_detected", "No player.")
        return build_report(swing_sequence(), stroke_hint, handedness, self.classifier,
                            self.references)


@pytest.fixture
def client(tmp_path):
    analyzer = FakeAnalyzer()
    app = create_app(Settings(upload_dir=tmp_path, max_upload_mb=1), analyzer=analyzer)
    with TestClient(app) as c:
        c.analyzer = analyzer
        c.upload_dir = tmp_path
        yield c


def _wait(client, job_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/v1/analyses/{job_id}").json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_health(client):
    body = client.get("/v1/health").json()
    assert body["status"] == "ok"
    assert body["classifier"] == "heuristic"
    assert body["reference"] == "default"
    assert body["auth_required"] is False


def test_upload_poll_done(client):
    r = client.post(
        "/v1/analyses",
        files={"file": ("swing.mp4", b"fake-video", "video/mp4")},
        data={"stroke_hint": "forehand", "handedness": "right"},
    )
    assert r.status_code == 202
    job = _wait(client, r.json()["id"])
    assert job["status"] == "done"
    assert job["progress"] == 1.0
    assert job["result"]["strokes"][0]["family"] == "forehand"
    assert client.analyzer.seen[0][1:] == ("forehand", "right")
    assert list(client.upload_dir.iterdir()) == []  # upload deleted after processing


def test_analysis_error_becomes_failed_job(client):
    r = client.post("/v1/analyses", files={"file": ("x.mov", b"no-player", "video/quicktime")})
    job = _wait(client, r.json()["id"])
    assert job["status"] == "failed"
    assert job["error"]["code"] == "no_player_detected"


def test_rejects_non_video(client):
    r = client.post("/v1/analyses", files={"file": ("notes.txt", b"hi", "text/plain")})
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_format"


def test_rejects_oversized_upload(client):
    r = client.post("/v1/analyses", files={"file": ("big.mp4", b"0" * (1024 * 1024 + 1), "video/mp4")})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "video_too_large"
    assert list(client.upload_dir.iterdir()) == []


def test_rejects_bad_hint(client):
    r = client.post("/v1/analyses", files={"file": ("a.mp4", b"x", "video/mp4")},
                    data={"stroke_hint": "lob"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_unknown_job_is_404(client):
    r = client.get("/v1/analyses/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_delete_job(client):
    job_id = client.post("/v1/analyses", files={"file": ("a.mp4", b"x", "video/mp4")}).json()["id"]
    _wait(client, job_id)
    assert client.delete(f"/v1/analyses/{job_id}").status_code == 204
    assert client.get(f"/v1/analyses/{job_id}").status_code == 404


def test_auth_required_rejects_missing_token(tmp_path, monkeypatch):
    import sys

    fake_auth = SimpleNamespace(verify_id_token=lambda token: {"uid": "u1"} if token == "good" else 1 / 0)
    fake_admin = SimpleNamespace(_apps={"x": 1}, initialize_app=lambda **k: None, auth=fake_auth)
    monkeypatch.setitem(sys.modules, "firebase_admin", fake_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.auth", fake_auth)
    app = create_app(Settings(upload_dir=tmp_path, auth_required=True), analyzer=FakeAnalyzer())
    with TestClient(app) as c:
        assert c.get("/v1/analyses/x").status_code == 401
        assert c.get("/v1/analyses/x", headers={"Authorization": "Bearer bad"}).status_code == 401
        assert c.get("/v1/analyses/x", headers={"Authorization": "Bearer good"}).status_code == 404
