# models/

Model artifacts live here and are not committed (see `backend/.gitignore`).

| File | Where it comes from | Required? |
|---|---|---|
| `pose_landmarker_heavy.task` (or `_full`, `_lite`) | `tennis-ai download-models` (also auto-downloaded on first analysis) | yes |
| `reference_calibrated.json` | `tennis-ai calibrate` | no — without it metrics are rated against the default coaching ranges |

`GET /v1/health` reports which of these the running service picked up.
