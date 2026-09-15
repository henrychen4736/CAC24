"""Command-line entry point: ``tennis-ai <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import get_settings


def _serve(a) -> None:
    import uvicorn

    uvicorn.run("tennis_ai.api.app:create_app", factory=True, host=a.host, port=a.port)


def _analyze(a) -> None:
    from .pipeline.analyzer import Analyzer

    analyzer = Analyzer(get_settings())
    report = analyzer.analyze(
        Path(a.video), a.hint, a.handedness,
        progress=lambda stage, frac: print(f"\r{stage:9s} {frac:5.0%}", end="", file=sys.stderr),
    )
    print(file=sys.stderr)
    data = report.model_dump(mode="json")
    if a.out:
        Path(a.out).write_text(json.dumps(data, indent=2))
    s = report.summary
    print(f"{s.headline}  overall score: {s.overall_score}")
    print(f"player: {report.player.handedness} ({report.player.handedness_source}), "
          f"view: {report.player.view} ({report.player.view_confidence})")
    for w in report.quality.warnings:
        print(f"  ! {w.message}")
    for st in report.strokes:
        print(f"\n#{st.index} {st.type} ({st.type_source}, {st.type_confidence:.2f}) "
              f"contact {st.contact_s:.2f}s  score {st.score}")
        for m in st.metrics:
            ref = f"good {m.reference.good}" if m.reference else ""
            print(f"   {m.label:32s} {m.value!s:>8} {m.unit:8s} {m.rating:10s} {m.confidence:6s} {ref}")
    for p in s.priorities:
        print(f"\n→ {p.title}: {p.cue}")


def _download_models(a) -> None:
    from .pipeline.pose import ensure_pose_model

    s = get_settings()
    for v in a.variants:
        print(ensure_pose_model(s.models_dir / f"pose_landmarker_{v}.task", v))


def _fetch_thetis(a) -> None:
    from .ml.thetis import fetch

    fetch(Path(a.out), a.classes, a.max_per_class, a.workers)


def _extract(a) -> None:
    from .ml.extract import ClipSpec, extract, read_manifest
    from .ml.thetis import list_clips

    if a.thetis:
        # THETIS was filmed by a Kinect facing the player
        specs = [ClipSpec(c.path.resolve(), c.stroke, c.skill, c.player, "auto", "front")
                 for c in list_clips(Path(a.thetis))]
    else:
        specs = read_manifest(Path(a.manifest))
    if a.limit:
        specs = specs[: a.limit]
    extract(specs, Path(a.out), get_settings().models_dir, a.pose_model, a.workers)


def _train(a) -> None:
    from .ml.train import train

    train(Path(a.poses), Path(a.out), a.epochs, a.seed, final_fit=not a.no_final)


def _calibrate(a) -> None:
    from .ml.calibrate import calibrate

    calibrate(Path(a.poses), Path(a.out), a.skill, a.min_n, a.view, a.shadow)


def main(argv: list[str] | None = None) -> None:
    # Windows consoles default to cp1252, which can't print labels like "Hip–shoulder" or "→"
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(prog="tennis-ai", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the API server")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=_serve)

    s = sub.add_parser("analyze", help="analyze one video and print the report")
    s.add_argument("video")
    s.add_argument("--hint", default="auto", choices=["auto", "forehand", "backhand", "serve"])
    s.add_argument("--handedness", default="auto", choices=["auto", "right", "left"])
    s.add_argument("--out", help="write the full JSON report here")
    s.set_defaults(fn=_analyze)

    s = sub.add_parser("download-models", help="download MediaPipe pose models")
    s.add_argument("--variants", nargs="+", default=["heavy"], choices=["lite", "full", "heavy"])
    s.set_defaults(fn=_download_models)

    s = sub.add_parser("fetch-thetis", help="download the THETIS RGB clips (research use)")
    s.add_argument("--out", default="data/thetis")
    s.add_argument("--classes", nargs="*")
    s.add_argument("--max-per-class", type=int)
    s.add_argument("--workers", type=int, default=8)
    s.set_defaults(fn=_fetch_thetis)

    s = sub.add_parser("extract", help="run pose over a dataset and cache it")
    src = s.add_mutually_exclusive_group(required=True)
    src.add_argument("--thetis", help="THETIS root (from fetch-thetis)")
    src.add_argument("--manifest", help="CSV manifest: video,stroke,skill,player,handedness")
    s.add_argument("--out", default="data/poses")
    s.add_argument("--workers", type=int)
    s.add_argument("--limit", type=int)
    s.add_argument("--pose-model", default="heavy", choices=["lite", "full", "heavy"])
    s.set_defaults(fn=_extract)

    s = sub.add_parser("train", help="train the stroke model and export ONNX")
    s.add_argument("--poses", default="data/poses")
    s.add_argument("--out", default="models")
    s.add_argument("--epochs", type=int, default=80)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--no-final", action="store_true", help="skip the refit on all data")
    s.set_defaults(fn=_train)

    s = sub.add_parser("calibrate", help="build reference ranges from expert clips")
    s.add_argument("--poses", default="data/poses")
    s.add_argument("--out", default="models/reference_calibrated.json")
    s.add_argument("--skill", default="expert")
    s.add_argument("--min-n", type=int, default=12)
    s.add_argument("--view", default="auto", choices=["auto", "front", "back", "side", "oblique"],
                   help="camera position for the whole dataset (THETIS: front); "
                        "auto = per-clip 'view' column, else estimated")
    s.add_argument("--shadow", action="store_true",
                   help="clips are swings without a ball (THETIS): don't calibrate ball-dependent "
                        "metrics such as leg drive")
    s.set_defaults(fn=_calibrate)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
