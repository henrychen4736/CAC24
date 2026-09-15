"""Multi-task temporal CNN: stroke type + expert-likeness (training only; needs torch)."""

from __future__ import annotations

import torch
from torch import nn


class StrokeNet(nn.Module):
    def __init__(self, num_features: int, num_classes: int, width: int = 96, dropout: float = 0.3):
        super().__init__()

        def block(cin: int, cout: int, k: int) -> list[nn.Module]:
            return [nn.Conv1d(cin, cout, k, padding=k // 2), nn.BatchNorm1d(cout), nn.GELU()]

        self.encoder = nn.Sequential(
            *block(num_features, width, 5),
            *block(width, width, 5),
            nn.MaxPool1d(2),
            *block(width, 2 * width, 3),
            *block(2 * width, 2 * width, 3),
        )
        self.dropout = nn.Dropout(dropout)
        self.type_head = nn.Linear(4 * width, num_classes)
        self.skill_head = nn.Linear(4 * width, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """x: (batch, time, features) → (type logits, skill logit)."""
        h = self.encoder(x.transpose(1, 2))
        h = torch.cat([h.mean(dim=-1), h.amax(dim=-1)], dim=-1)
        h = self.dropout(h)
        return self.type_head(h), self.skill_head(h).squeeze(-1)
