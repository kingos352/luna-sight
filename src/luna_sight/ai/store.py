"""Analiz oturumlarının saklanması ve geri çağrılması.

Oturumlar `data/cache/ai_sessions/` altına yazılır. `data/cache/` Git
tarafından izlenmez: bu dosyalar türetilmiş çıktıdır ve içlerinde modele
gönderilen görüntünün base64 gövdesi **tutulmaz**, yalnızca kökeni tutulur.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from luna_sight.ai.schema import RegionAnalysis

REPO_ROOT = Path(__file__).resolve().parents[3]
SESSION_DIR = REPO_ROOT / "data" / "cache" / "ai_sessions"

_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe(name: str) -> str:
    return _SAFE.sub("_", name)[:80] or "session"


def session_id(analysis: RegionAnalysis) -> str:
    stamp = (analysis.metadata.timestamp or "").replace(":", "").replace("-", "")
    return _safe(f"{analysis.region.id}_{stamp}")


def save(analysis: RegionAnalysis, directory: Path | None = None) -> Path:
    """Analizi JSON olarak yaz ve yolunu döndür."""
    target_dir = directory or SESSION_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{session_id(analysis)}.json"
    path.write_text(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def list_sessions(directory: Path | None = None) -> list[Path]:
    """En yeni önce olacak şekilde kayıtlı oturumlar."""
    target_dir = directory or SESSION_DIR
    if not target_dir.exists():
        return []
    return sorted(target_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def load(path: Path) -> dict:
    """Kayıtlı oturumu sözlük olarak oku."""
    return json.loads(path.read_text(encoding="utf-8"))
