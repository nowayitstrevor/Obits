from __future__ import annotations

import os
from pathlib import Path


def _parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = str(raw_line or "").strip()
    if not line or line.startswith("#"):
        return None

    if line.startswith("export "):
        line = line[len("export "):].strip()

    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    if not key:
        return None

    value = value.strip()
    if not value:
        return key, ""

    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        if len(value) >= 2:
            return key, value[1:-1]
        return key, ""

    hash_index = value.find(" #")
    if hash_index >= 0:
        value = value[:hash_index].strip()

    return key, value


def load_env_file(*, env_path: Path | None = None, override: bool = False) -> dict[str, str]:
    base_dir = Path(__file__).resolve().parent
    path = env_path or (base_dir / ".env")
    if not path.exists() or not path.is_file():
        return {}

    loaded: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}

    for line in lines:
        parsed = _parse_env_line(line)
        if not parsed:
            continue
        key, value = parsed

        if not override and key in os.environ:
            continue

        os.environ[key] = value
        loaded[key] = value

    return loaded
