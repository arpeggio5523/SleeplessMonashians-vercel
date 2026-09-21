from __future__ import annotations

import json
from pathlib import Path

LEARNED = Path("data/learned_aliases.json")

def learn(field: str, label_seen: str) -> None:
    """A reviewer confirmed this label means this field."""
    LEARNED.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if LEARNED.exists():
        try:
            data = json.loads(LEARNED.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    
    aliases = data.get(field, [])
    if label_seen and label_seen not in aliases:
        aliases.append(label_seen)
        data[field] = aliases
        LEARNED.write_text(json.dumps(data, indent=2), encoding="utf-8")

def aliases_for(field: str) -> list[str]:
    """Learned labels, tried after the built-in list in extract.py."""
    if not LEARNED.exists():
        return []
    try:
        data = json.loads(LEARNED.read_text(encoding="utf-8"))
        return data.get(field, [])
    except Exception:
        return []