from __future__ import annotations

from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as torch_functional


def irt2pl(theta, discrimination, difficulty, *, tensor_api=torch):
    return 1 / (
        1
        + tensor_api.exp(
            -tensor_api.sum(tensor_api.multiply(discrimination, theta), axis=-1)
            + difficulty
        )
    )


class MIRTNet(nn.Module):
    def __init__(
        self,
        llm_input_dim: int,
        item_input_dim: int,
        latent_dim: int,
        a_range: float | None = None,
        theta_range: float | None = None,
    ) -> None:
        super().__init__()
        self.theta = nn.Linear(llm_input_dim, latent_dim, bias=False)
        self.discrimination = nn.Linear(item_input_dim, latent_dim, bias=False)
        self.difficulty = nn.Linear(item_input_dim, 1, bias=False)
        self.a_range = a_range
        self.theta_range = theta_range

    def forward(self, llm: torch.Tensor, item: torch.Tensor):
        theta = torch.squeeze(self.theta(llm), dim=-1)
        discrimination = torch.squeeze(self.discrimination(item), dim=-1)
        if self.theta_range is not None:
            theta = self.theta_range * torch.sigmoid(theta)
        if self.a_range is not None:
            discrimination = self.a_range * torch.sigmoid(discrimination)
        else:
            discrimination = torch_functional.softplus(discrimination)
        difficulty = torch.squeeze(self.difficulty(item), dim=-1)
        if not all(
            torch.isfinite(value).all()
            for value in (theta, discrimination, difficulty)
        ):
            raise ValueError("MIRT intermediate values contain non-finite numbers")
        prediction = irt2pl(theta, discrimination, difficulty)
        return prediction, theta, discrimination, difficulty


class MIRT:
    def __init__(
        self,
        llm_input_dim: int,
        item_input_dim: int,
        latent_dim: int,
    ) -> None:
        self.network = MIRTNet(llm_input_dim, item_input_dim, latent_dim)

    def load(self, path: Path) -> None:
        try:
            state = torch.load(path, map_location="cpu", weights_only=True)
        except TypeError:
            state = torch.load(path, map_location="cpu")
        # The reference snapshot uses the original a/b layer names.
        normalized = {}
        for key, value in state.items():
            if key.startswith("a."):
                key = "discrimination." + key[2:]
            elif key.startswith("b."):
                key = "difficulty." + key[2:]
            normalized[key] = value
        self.network.load_state_dict(normalized)
        self.network.eval()

    def generate(
        self,
        llm_vector,
        query_vector,
        *,
        device: str = "cpu",
    ) -> float:
        self.network = self.network.to(device)
        llm_tensor = torch.as_tensor(llm_vector, dtype=torch.float32, device=device)
        query_tensor = torch.as_tensor(query_vector, dtype=torch.float32, device=device)
        with torch.no_grad():
            prediction, _, _, _ = self.network(llm_tensor, query_tensor)
        value = float(prediction.detach().cpu().item())
        if not 0 <= value <= 1:
            raise ValueError("MIRT prediction is outside [0, 1]")
        return value
