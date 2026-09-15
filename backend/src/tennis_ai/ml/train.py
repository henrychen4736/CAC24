"""Train the stroke model with a player-level split, then export to ONNX."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..pipeline.classify import FAMILY_OF, STROKE_TYPES
from .dataset import Dataset, build_dataset
from .features import FEATURE_VERSION, NUM_FEATURES, POS, T_OUT, WINDOW_S, rotate_features


def split_players(ds: Dataset, val_frac: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Hold out whole players (stratified by skill) so validation measures generalization."""
    rng = np.random.default_rng(seed)
    val_players: set[str] = set()
    for skill in np.unique(ds.skill):
        players = np.unique(ds.player[ds.skill == skill])
        rng.shuffle(players)
        val_players |= set(players[: max(1, round(len(players) * val_frac))])
    is_val = np.array([p in val_players for p in ds.player])
    return np.where(~is_val)[0], np.where(is_val)[0]


def _augment(x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    x = rotate_features(x, float(rng.uniform(-0.5, 0.5)))           # ±30° camera yaw
    x[..., POS] *= rng.uniform(0.9, 1.1)                              # body proportions
    shift = int(rng.integers(-3, 4))                                  # contact timing error
    if shift:
        x = np.roll(x, shift, axis=0)
        if shift > 0:
            x[:shift] = x[shift]
        else:
            x[shift:] = x[shift - 1]
    return x


def auc(scores: np.ndarray, labels: np.ndarray) -> float | None:
    pos, neg = scores[labels == 1], scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _fit(ds, train_idx, classes, epochs, seed, mean, std, val_idx=None, log=print):
    import torch
    from torch import nn

    from .model import StrokeNet

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    cls_index = {c: i for i, c in enumerate(classes)}
    y_type = np.array([cls_index[s] for s in ds.stroke])
    y_skill = np.array([1.0 if s == "expert" else 0.0 for s in ds.skill], dtype=np.float32)
    has_skill = np.array([s in ("expert", "beginner") for s in ds.skill], dtype=np.float32)

    counts = np.bincount(y_type[train_idx], minlength=len(classes)).astype(float)
    class_w = torch.tensor((counts.sum() / np.maximum(counts, 1)) ** 0.5, dtype=torch.float32)
    class_w /= class_w.mean()

    model = StrokeNet(NUM_FEATURES, len(classes))
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-2)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=2e-3, total_steps=epochs * int(np.ceil(len(train_idx) / 64))
    )
    ce = nn.CrossEntropyLoss(weight=class_w, label_smoothing=0.05)
    bce = nn.BCEWithLogitsLoss(reduction="none")
    norm = lambda a: ((a - mean) / std).astype(np.float32)  # noqa: E731

    best = (-1.0, None, 0)
    for epoch in range(1, epochs + 1):
        model.train()
        order = rng.permutation(train_idx)
        for b in range(0, len(order), 64):
            idx = order[b : b + 64]
            xb = np.stack([_augment(ds.X[i], rng) for i in idx])
            xb = norm(xb) + rng.normal(0, 0.02, xb.shape).astype(np.float32)
            logits, skill = model(torch.from_numpy(xb))
            loss = ce(logits, torch.from_numpy(y_type[idx]))
            m = torch.from_numpy(has_skill[idx])
            loss = loss + 0.5 * (bce(skill, torch.from_numpy(y_skill[idx])) * m).sum() / m.sum().clamp(min=1)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()

        if val_idx is not None and (epoch % 5 == 0 or epoch == epochs):
            ev = evaluate(model, ds, val_idx, classes, mean, std)
            log(f"  epoch {epoch:3d}  val acc {ev['accuracy']:.3f}  macro-F1 {ev['macro_f1']:.3f}"
                f"  family acc {ev['family_accuracy']:.3f}  skill AUC {ev['skill_auc'] or 0:.3f}")
            if ev["macro_f1"] > best[0]:
                best = (ev["macro_f1"], {k: v.clone() for k, v in model.state_dict().items()}, epoch)
    if best[1] is not None:
        model.load_state_dict(best[1])
    return model, best[2]


def evaluate(model, ds, idx, classes, mean, std) -> dict:
    import torch

    model.eval()
    with torch.no_grad():
        logits, skill = model(torch.from_numpy(((ds.X[idx] - mean) / std).astype(np.float32)))
    pred = logits.argmax(-1).numpy()
    cls_index = {c: i for i, c in enumerate(classes)}
    true = np.array([cls_index[s] for s in ds.stroke[idx]])
    k = len(classes)
    cm = np.zeros((k, k), dtype=int)
    for t, p in zip(true, pred, strict=True):
        cm[t, p] += 1
    recall = cm.diagonal() / np.maximum(cm.sum(1), 1)
    precision = cm.diagonal() / np.maximum(cm.sum(0), 1)
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-9)
    fam = np.array([FAMILY_OF[c] for c in classes])
    skill_lbl = np.array([1 if s == "expert" else 0 if s == "beginner" else -1 for s in ds.skill[idx]])
    known = skill_lbl >= 0
    return {
        "n": int(len(idx)),
        "accuracy": float((pred == true).mean()),
        "macro_f1": float(f1[cm.sum(1) > 0].mean()),
        "family_accuracy": float((fam[pred] == fam[true]).mean()),
        "per_class_recall": {c: round(float(r), 3) for c, r in zip(classes, recall, strict=True)},
        "confusion": cm.tolist(),
        "skill_auc": auc(skill.numpy()[known], skill_lbl[known]) if known.any() else None,
    }


def heuristic_baseline(ds: Dataset, idx: np.ndarray) -> dict:
    """How the no-model fallback does on the same held-out players."""
    true, pred = ds.stroke[idx], ds.heuristic[idx]
    fam_true = np.array([FAMILY_OF[s] for s in true])
    fam_pred = np.array([FAMILY_OF[s] for s in pred])
    supported = np.isin(true, ["forehand", "backhand_1h", "backhand_2h", "serve"])
    return {
        "family_accuracy": float((fam_true == fam_pred).mean()),
        "accuracy_on_supported_types": float((true[supported] == pred[supported]).mean())
        if supported.any() else 0.0,
    }


def export_onnx(model, path: Path) -> None:
    import torch

    model.eval()
    dummy = torch.zeros(1, T_OUT, NUM_FEATURES)
    kwargs = dict(
        input_names=["x"],
        output_names=["type_logits", "skill_logit"],
        dynamic_axes={"x": {0: "batch"}, "type_logits": {0: "batch"}, "skill_logit": {0: "batch"}},
        opset_version=17,
    )
    try:
        torch.onnx.export(model, (dummy,), str(path), dynamo=False, **kwargs)
    except TypeError:  # older torch without the `dynamo` flag
        torch.onnx.export(model, (dummy,), str(path), **kwargs)


def train(pose_dir: Path, out: Path, epochs: int = 80, seed: int = 0, val_frac: float = 0.2,
          final_fit: bool = True) -> dict:
    t0 = time.time()
    ds = build_dataset(pose_dir)
    classes = [c for c in STROKE_TYPES if c in set(ds.stroke)]
    print(f"Dataset: {len(ds.X)} strokes, {len(np.unique(ds.player))} players, classes={classes}")
    train_idx, val_idx = split_players(ds, val_frac, seed)
    mean = ds.X[train_idx].reshape(-1, NUM_FEATURES).mean(0)
    std = np.maximum(ds.X[train_idx].reshape(-1, NUM_FEATURES).std(0), 1e-3)
    print(f"Train {len(train_idx)} / validation {len(val_idx)} (held-out players)")

    model, best_epoch = _fit(ds, train_idx, classes, epochs, seed, mean, std, val_idx)
    val = evaluate(model, ds, val_idx, classes, mean, std)
    val["heuristic_baseline"] = heuristic_baseline(ds, val_idx)
    print(f"Best validation (epoch {best_epoch}): acc {val['accuracy']:.3f}, "
          f"macro-F1 {val['macro_f1']:.3f}, family acc {val['family_accuracy']:.3f}, "
          f"skill AUC {val['skill_auc']}")
    hb = val["heuristic_baseline"]
    print(f"Heuristic baseline on the same players: family acc {hb['family_accuracy']:.3f}, "
          f"acc on the 4 types it can output {hb['accuracy_on_supported_types']:.3f}")

    if final_fit:
        print(f"Refitting on all {len(ds.X)} strokes for {best_epoch} epochs")
        all_idx = np.arange(len(ds.X))
        mean = ds.X.reshape(-1, NUM_FEATURES).mean(0)
        std = np.maximum(ds.X.reshape(-1, NUM_FEATURES).std(0), 1e-3)
        model, _ = _fit(ds, all_idx, classes, max(best_epoch, 10), seed, mean, std)

    out.mkdir(parents=True, exist_ok=True)
    onnx_path = out / "stroke_model.onnx"
    export_onnx(model, onnx_path)
    meta = {
        "model_version": f"v1-{datetime.now(UTC):%Y%m%d}",
        "feature_version": FEATURE_VERSION,
        "window_s": list(WINDOW_S),
        "t_out": T_OUT,
        "classes": classes,
        "feature_mean": mean.round(6).tolist(),
        "feature_std": std.round(6).tolist(),
        "validation": val,
        "trained_on": {"clips": int(len(ds.X)), "players": int(len(np.unique(ds.player))),
                       "source": str(pose_dir)},
        "created": datetime.now(UTC).isoformat(),
    }
    onnx_path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(f"Exported {onnx_path} in {time.time() - t0:.0f}s")
    return meta
