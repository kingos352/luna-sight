"""AI yüzey analizi için tipli şema ve doğrulama.

Model serbest metin döndürür; JSON döndüreceği **varsayılmaz**. Bu modül
modelin çıktısını sabit bir yapıya indirger, tanımadığı alanları atar ve
eksik alanları açıkça `None` bırakır.

Bilimsel bütünlük kuralı: `AiAnalysis` içinde **sayısal ölçüm tutulmaz**.
Krater çapı, eğim, yükseklik, tehlike olasılığı gibi değerler yalnızca
`ScientificAnalysis` içinde, doğrulanmış modüllerden gelir. Modelin
metninde sayı geçse bile buraya taşınmaz; gözlem alanları metinseldir.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from math import isfinite
from typing import Any

MODEL_ID = "nvidia/nemotron-3.5-super-vl-120b-a12b"

#: Gözlem kesinliği. Yüzde verilmez: modelin ürettiği bir güven yüzdesinin
#: teknik dayanağı olmaz. Nitel kategori kullanılır (spec bölüm 13).
CERTAINTY_LEVELS = ("observed", "inferred", "uncertain")
DEFAULT_CERTAINTY = "uncertain"

#: Tanınan özellik etiketleri. Model başka bir şey derse `other` olur ve
#: ham etiket açıklamaya yazılır; uydurma kategori üretilmez.
FEATURE_LABELS = (
    "impact_crater",
    "crater_rim",
    "boulder",
    "boulder_field",
    "ridge",
    "texture_variation",
    "discontinuity",
    "shadowed_region",
    "roughness",
    "other",
)

STATUS_VALUES = ("completed", "partial", "failed")


@dataclass(frozen=True)
class RegionRef:
    """Analiz edilen bölgenin kimliği ve konumu."""

    id: str
    latitude: float | None = None
    longitude: float | None = None
    image_source: str | None = None


@dataclass(frozen=True)
class Observation:
    """Tek bir görsel gözlem. Sayısal ölçüm içermez."""

    feature: str
    description: str
    evidence: str = ""
    certainty: str = DEFAULT_CERTAINTY
    location_in_image: str | None = None
    box: tuple[float, float, float, float] | None = None
    point: tuple[float, float] | None = None


@dataclass(frozen=True)
class AiAnalysis:
    """Modelin yorum katmanı. Ölçüm değil, gözlem ve sınır beyanı."""

    summary: str = ""
    observations: tuple[Observation, ...] = ()
    terrain_interpretation: str = ""
    potential_hazards: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScientificAnalysis:
    """Doğrulanmış modüllerden gelen sayısal sonuçlar.

    Değer yoksa `None` kalır ve arayüzde "ölçüm yok" olarak gösterilir;
    tahminle doldurulmaz.
    """

    elevation_m: float | None = None
    slope_deg: float | None = None
    horizon_mean_deg: float | None = None
    horizon_max_deg: float | None = None
    joint_visible_fraction: float | None = None
    longest_joint_window_hours: float | None = None
    crater_metrics: tuple[dict[str, Any], ...] = ()
    additional: dict[str, Any] = field(default_factory=dict)
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisMetadata:
    model: str = MODEL_ID
    timestamp: str | None = None
    status: str = "completed"
    endpoint: str | None = None
    inference_executed: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegionAnalysis:
    """Birleşik sonuç: bilimsel ölçüm + AI yorumu, ayrı tutulur."""

    region: RegionRef
    ai_analysis: AiAnalysis
    scientific_analysis: ScientificAnalysis
    metadata: AnalysisMetadata
    conflicts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Spec bölüm 7'deki yapıya yakın, JSON'a yazılabilir sözlük."""
        return {
            "region": {
                "id": self.region.id,
                "latitude": self.region.latitude,
                "longitude": self.region.longitude,
                "imageSource": self.region.image_source,
            },
            "aiAnalysis": {
                "summary": self.ai_analysis.summary,
                "observations": [
                    {
                        "feature": item.feature,
                        "description": item.description,
                        "evidence": item.evidence,
                        "certainty": item.certainty,
                        "locationInImage": item.location_in_image,
                        "box": item.box,
                        "point": item.point,
                    }
                    for item in self.ai_analysis.observations
                ],
                "terrainInterpretation": self.ai_analysis.terrain_interpretation,
                "potentialHazards": list(self.ai_analysis.potential_hazards),
                "limitations": list(self.ai_analysis.limitations),
            },
            "scientificAnalysis": {
                key: value
                for key, value in asdict(self.scientific_analysis).items()
                if key != "additional"
            }
            | {"additionalMetrics": self.scientific_analysis.additional},
            "metadata": {
                "model": self.metadata.model,
                "timestamp": self.metadata.timestamp,
                "status": self.metadata.status,
                "endpoint": self.metadata.endpoint,
                "inferenceExecuted": self.metadata.inference_executed,
                "notes": list(self.metadata.notes),
            },
            "conflicts": list(self.conflicts),
        }


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_text(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _clean_texts(value: Any, limit: int = 300) -> tuple[str, ...]:
    """Listeyi boş olmayan kısa metinlere indirge."""
    return tuple(text for text in (_as_text(item, limit) for item in _as_list(value)) if text)


def extract_json_block(raw: str) -> dict[str, Any] | None:
    """Serbest metin içinden ilk JSON nesnesini çıkar.

    Model markdown çiti veya açıklama cümlesi ekleyebilir. Hiçbiri
    ayrıştırılamazsa `None` döner ve çağıran metin yoluna düşer.
    """
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    candidates = [fenced.group(1)] if fenced else []
    brace = re.search(r"\{.*\}", raw, re.S)
    if brace:
        candidates.append(brace.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def normalize_observation(payload: Any) -> Observation | None:
    """Tek gözlemi şemaya indirge. Kullanılabilir açıklama yoksa atla."""
    if isinstance(payload, str):
        text = _as_text(payload)
        return Observation(feature="other", description=text) if text else None
    if not isinstance(payload, dict):
        return None

    raw_feature = _as_text(payload.get("feature") or payload.get("type"), 64).lower()
    feature = raw_feature if raw_feature in FEATURE_LABELS else "other"
    description = _as_text(payload.get("description") or payload.get("text"))
    if feature == "other" and raw_feature and raw_feature not in FEATURE_LABELS:
        # Tanınmayan etiket uydurulmuş kategoriye dönüştürülmez, metne yazılır.
        description = f"[{raw_feature}] {description}".strip()
    if not description:
        return None

    certainty = _as_text(payload.get("certainty"), 32).lower()
    if certainty not in CERTAINTY_LEVELS:
        certainty = DEFAULT_CERTAINTY

    location = payload.get("locationInImage") or payload.get("location_in_image")
    return Observation(
        feature=feature,
        description=description,
        evidence=_as_text(payload.get("evidence")),
        certainty=certainty,
        location_in_image=_as_text(location, 200) or None,
        box=_normalized_coordinates(payload.get("box"), 4),
        point=_normalized_coordinates(payload.get("point"), 2),
    )


def _normalized_coordinates(value: Any, length: int) -> tuple | None:
    """Yalnızca görüntü içindeki göreli konum; fiziksel ölçüm değildir."""
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    if any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not isfinite(item)
        or not 0 <= item <= 1
        for item in value
    ):
        return None
    if length == 4 and (value[0] >= value[2] or value[1] >= value[3]):
        return None
    return tuple(float(item) for item in value)


def normalize_ai_payload(raw_text: str) -> tuple[AiAnalysis, list[str]]:
    """Model çıktısını `AiAnalysis` yapısına indirge.

    Dönüş: (analiz, notlar). Notlar, ayrıştırmada ne olduğunu kaydeder;
    arayüzde şeffaflık için gösterilir.
    """
    raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.S).strip()
    if "<think>" in raw_text:
        raw_text = raw_text.split("<think>", 1)[0].strip()
    notes: list[str] = []
    payload = extract_json_block(raw_text)
    if payload is None:
        # JSON yok: metnin tamamı özet sayılır, gözlem üretilmez.
        notes.append("Model JSON döndürmedi; yanıt özet olarak alındı, gözlem çıkarılmadı.")
        return AiAnalysis(summary=_as_text(raw_text)), notes

    observations: list[Observation] = []
    for item in _as_list(payload.get("observations")):
        normalized = normalize_observation(item)
        if normalized is not None:
            observations.append(normalized)
    dropped = len(_as_list(payload.get("observations"))) - len(observations)
    if dropped > 0:
        notes.append(f"{dropped} gözlem açıklaması boş olduğu için atıldı.")

    analysis = AiAnalysis(
        summary=_as_text(payload.get("summary")),
        observations=tuple(observations),
        terrain_interpretation=_as_text(payload.get("terrainInterpretation")),
        potential_hazards=_clean_texts(payload.get("potentialHazards")),
        limitations=_clean_texts(payload.get("limitations")),
    )
    if not analysis.summary and not analysis.observations:
        notes.append("Model yanıtı şemaya uygun alan içermiyordu.")
    return analysis, notes
