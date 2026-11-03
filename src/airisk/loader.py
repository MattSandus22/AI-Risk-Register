"""Read a register directory into raw dicts and, once valid, into the model."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Config, Control, Register, Risk, System

FILES = {
    "config": ("config.yaml", False),
    "systems": ("systems.yaml", True),
    "risks": ("risks.yaml", True),
    "governance": ("governance.yaml", False),
}


class RegisterError(Exception):
    pass


def load_raw(path: str | Path) -> dict:
    root = Path(path)
    if not root.is_dir():
        raise RegisterError(f"{root} is not a directory")
    raw: dict = {}
    for key, (name, required) in FILES.items():
        f = root / name
        if not f.exists():
            if required:
                raise RegisterError(f"{f} is required")
            raw[key] = {} if key == "config" else []
            continue
        try:
            data = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as exc:
            raise RegisterError(f"{f}: invalid YAML: {exc}") from exc
        raw[key] = data if key == "config" else (data.get(key) or [])
    return raw


def build(raw: dict) -> Register:
    return Register(
        config=Config.from_raw(raw["config"]),
        systems={s["id"]: System.from_raw(s) for s in raw["systems"]},
        risks=[Risk.from_raw(r) for r in raw["risks"]],
        governance=[Control.from_raw(g) for g in raw["governance"]],
    )
