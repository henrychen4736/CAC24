# Henry Tennis — analysis service

Upload a tennis video, get back detected strokes, biomechanical metrics, and
coaching cues. Design and API contract: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

```
video → MediaPipe Pose Landmarker (2D + 3D) → player tracking → smoothing / mirroring
      → stroke detection (filtered to swings that can be the chosen stroke) → phases
      → metrics → rated against reference ranges → report JSON
```

The caller chooses the stroke type (`forehand`, `forehand_slice`, `forehand_volley`,
`backhand_1h`, `backhand_2h`, `backhand_slice`, `backhand_volley`, `serve`, `smash`)
and the hitting hand (`right` / `left`); every swing found is analyzed as that stroke.

```
```

## Quick start

Python 3.11 or 3.12 (mediapipe has no wheels for newer versions yet).

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
tennis-ai download-models         # ~30 MB MediaPipe pose model into models/
tennis-ai serve                   # http://localhost:8000, docs at /docs
```

Analyze a file from the command line (prints a summary, optionally writes the full report):

```bash
tennis-ai analyze my_forehand.mp4 --stroke forehand --handedness right --out report.json
```

From the app: the Android emulator reaches your machine at `http://10.0.2.2:8000`,
the iOS simulator at `http://localhost:8000`, and a physical phone at
`http://<your-computer's-LAN-IP>:8000` (set it in the app's Profile → Server).

## Configuration

Environment variables (or a `.env` file in `backend/`):

| Variable | Default | |
|---|---|---|
| `TENNIS_POSE_MODEL` | `heavy` | `lite` / `full` / `heavy` — speed vs accuracy |
| `TENNIS_MAX_VIDEO_SECONDS` | `60` | longer uploads are rejected |
| `TENNIS_MAX_UPLOAD_MB` | `300` | |
| `TENNIS_WORKERS` | `1` | concurrent analyses |
| `TENNIS_AUTH_REQUIRED` | `false` | `true` = require a Firebase ID token (`pip install -e ".[auth]"`) |
| `TENNIS_FIREBASE_PROJECT_ID` | — | e.g. `henry-tennis-q8mkn` |
| `TENNIS_MODELS_DIR` | `backend/models` | |

On a laptop CPU the heavy model runs at roughly 10–15 frames/s, so a 10 s clip
at 30 fps takes about 25 s. Use `full` for ~2× speed at a small accuracy cost.

## Calibrating on THETIS (or your own data)

Reference ranges are calibrated from expert strokes (no extra install beyond `.[dev]`):

```bash
tennis-ai fetch-thetis --out data/thetis          # 1,980 clips, ~4 GB
tennis-ai extract --thetis data/thetis --out data/poses    # pose once, cached (~1 h on 8 cores)
tennis-ai calibrate --poses data/poses --view front --shadow --out models/reference_calibrated.json
```

`--view front` tells calibration where THETIS's camera stood. Depth-dependent
metrics (rotations, stance width, contact depth) aren't trustworthy from a
front-facing camera, so those keep their coaching defaults. `--shadow` says the
clips are swings without a ball, so metrics that only mean something when you
strike one (leg drive) keep their defaults too.

Bring your own clips with a CSV manifest instead of `--thetis`
(`video,stroke,skill,player,handedness,view`; format in ARCHITECTURE.md §5):

```bash
tennis-ai extract --manifest my_clips/manifest.csv --out data/my_poses
tennis-ai calibrate --poses data/my_poses --out models/reference_calibrated.json
```

**License note:** THETIS is published "freely available for research purposes"
with no explicit license. Treat ranges calibrated on it as research artifacts and
recalibrate on data you have rights to before any commercial release.

## Tests

```bash
pytest
```

The tests use synthetic skeletons (no video or model downloads needed): stroke
detection, handedness mirroring, the stroke plausibility checks, camera-angle
invariance of the rotation metrics, rating, calibration, and the full HTTP job
flow (including required `stroke_type` / `handedness` validation).

## Deploying

`Dockerfile` builds a CPU image that listens on `$PORT` (Cloud Run friendly):

```bash
docker build -t henry-tennis-api .
docker run -p 8080:8080 -e TENNIS_AUTH_REQUIRED=true -e TENNIS_FIREBASE_PROJECT_ID=henry-tennis-q8mkn henry-tennis-api
```

Jobs are kept in memory, so run a single instance (or move the job store to
Firestore/Redis and the queue to Cloud Tasks before scaling out).
