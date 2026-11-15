"""Bilimsel sonuçlarla AI gözlemlerini birleştiren katman.

Sıra: bölge seç → bilimsel ölçümleri **mevcut çıktılardan oku** → görüntüyü
hazırla → modele sor → yanıtı doğrula → birleştir.

Yetki kuralı: ölçümün tek kaynağı bilimsel modüllerdir. Model bir sayı
söylese bile `ScientificAnalysis` değişmez; çelişki varsa bilimsel değer
korunur ve fark `conflicts` içinde görünür kılınır (spec bölüm 6).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from luna_sight.ai.client import NimClient, NimError
from luna_sight.ai.imaging import PreparedImage
from luna_sight.ai.schema import (
    AiAnalysis,
    AnalysisMetadata,
    RegionAnalysis,
    RegionRef,
    ScientificAnalysis,
    normalize_ai_payload,
    utc_now,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
K2_DIR = REPO_ROOT / "outputs" / "k2"
K3_DIR = REPO_ROOT / "outputs" / "k3"

SYSTEM_PROMPT = (
    "You analyse lunar surface imagery for a mission-planning tool. "
    "Report only what is visually evident in the supplied image. "
    "You must NOT state crater diameters, elevations, slope angles, "
    "coordinates, mineral composition, geological ages, hazard "
    "probabilities or any other numeric measurement: those come from "
    "validated instruments and are supplied separately. "
    "Respond with a single JSON object and nothing else, using this shape: "
    '{"summary": str, "observations": [{"feature": str, "description": str, '
    '"evidence": str, "certainty": "observed|inferred|uncertain", '
    '"locationInImage": str, "box": [xmin, ymin, xmax, ymax] or null, '
    '"point": [x, y] or null}], "terrainInterpretation": str, '
    '"potentialHazards": [str], "limitations": [str]}. '
    "Allowed feature values: impact_crater, crater_rim, boulder, "
    "boulder_field, ridge, texture_variation, discontinuity, "
    "shadowed_region, roughness, other. "
    "Write all human-readable values in Turkish; keep JSON keys and enums unchanged. "
    "Boxes and points are optional approximate image positions normalized from 0 to 1, "
    "origin top-left. Only provide them for clearly localized visible features. "
    "Return null when localization is not supported. Never identify a safe landing site."
)

#: Modelin metninde geçen sayı+birim kalıpları. Ölçüm iddiası tespitinde
#: kullanılır; bulunursa gözlem silinmez ama çelişki olarak işaretlenir.
_MEASUREMENT_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:m\b|km\b|metre|meters?|derece|deg\b|degrees?|°)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RegionContext:
    """Bir aday bölgenin kimliği ve bilimsel özeti."""

    site_id: str
    site_name: str
    latitude_deg: float | None
    longitude_deg_east: float | None
    scientific: ScientificAnalysis


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return payload if isinstance(payload, dict) else None
    except ValueError:
        return None


def load_region_context(site_id: str, radius_m: float = 4000.0) -> RegionContext:
    """Bölgenin bilimsel ölçümlerini mevcut K2/K3 çıktılarından topla.

    Bulunamayan değer `None` kalır; tahmin üretilmez (spec bölüm 6).
    """
    k2 = _read_json(K2_DIR / f"{site_id}_summary.json") or {}
    k3 = _read_json(K3_DIR / f"{site_id}_summary.json") or {}

    coordinate = k2.get("coordinate") or k3.get("coordinate") or {}
    latitude = coordinate.get("lat_deg", coordinate.get("latitude_deg"))
    longitude = coordinate.get("lon_deg_east", coordinate.get("longitude_deg_east"))

    horizon_mean = horizon_max = None
    for profile in k2.get("profiles", []) or []:
        if not isinstance(profile, dict):
            continue
        parameters = profile.get("parameters", {}) or {}
        if parameters.get("max_radius_m") == radius_m:
            horizon_mean = profile.get("horizon_mean_deg", horizon_mean)
            horizon_max = profile.get("horizon_max_deg", horizon_max)
            if parameters.get("max_radius_m") == radius_m:
                break

    joint = (k3.get("bodies") or {}).get("joint") or {}
    sources: list[str] = []
    if k2:
        sources.append(f"outputs/k2/{site_id}_summary.json (K2 · LOLA ufuk profili)")
    if k3:
        sources.append(f"outputs/k3/{site_id}_summary.json (K3 · görünürlük motoru)")

    scientific = ScientificAnalysis(
        elevation_m=None,  # Nokta yüksekliği ayrı bir üründe; burada yok.
        slope_deg=None,  # Eğim analizi bu sürümde üretilmiyor.
        horizon_mean_deg=horizon_mean,
        horizon_max_deg=horizon_max,
        joint_visible_fraction=joint.get("visible_fraction"),
        longest_joint_window_hours=joint.get("longest_visible_hours"),
        crater_metrics=(),  # Krater ölçümü modülü yok; boş bırakılır.
        additional={
            "dem_product": (k2.get("dem") or {}).get("product"),
            "dem_pixel_size_m": (k2.get("dem") or {}).get("pixel_size_m"),
            "joint_window_count": joint.get("window_count"),
            "analysis_radius_m": radius_m,
        },
        sources=tuple(sources),
    )
    return RegionContext(
        site_id=site_id,
        site_name=k2.get("site_name") or site_id,
        latitude_deg=latitude,
        longitude_deg_east=longitude,
        scientific=scientific,
    )


def _format_scientific_brief(context: RegionContext) -> str:
    """Modele verilecek bağlam. Ölçümler burada **bilgi** olarak geçer."""
    science = context.scientific
    lines = [
        f"Region id: {context.site_id} ({context.site_name}).",
        "Validated measurements supplied by the mission's own pipeline "
        "(do not restate them as your own observations):",
    ]
    if science.horizon_mean_deg is not None:
        lines.append(f"- mean terrain horizon: {science.horizon_mean_deg:.3f} deg")
    if science.horizon_max_deg is not None:
        lines.append(f"- highest terrain horizon: {science.horizon_max_deg:.3f} deg")
    if science.joint_visible_fraction is not None:
        lines.append(f"- joint Sun+Earth visibility: {science.joint_visible_fraction * 100:.2f}%")
    if len(lines) == 2:
        lines.append("- none available for this region")
    if science.additional.get("selected_scene"):
        lines.append(
            "Selected scene context from the application data (separate from region summary):"
        )
        lines.append(json.dumps(science.additional["selected_scene"], ensure_ascii=False))
    lines.append(
        "Describe only what the image shows. If the image cannot support a "
        "claim, say so in limitations."
    )
    return "\n".join(lines)


def build_messages(context: RegionContext, image: PreparedImage) -> list[dict[str, object]]:
    """NIM sohbet mesajlarını kur (OpenAI uyumlu içerik parçaları)."""
    user_text = _format_scientific_brief(context) + _image_brief(image)
    if image.is_rendered:
        user_text += (
            "\nIMPORTANT: this image is a rendered 3D visualisation, not an "
            "observation. Lighting and shading are synthetic; do not treat "
            "them as surface properties."
        )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": image.data_url}},
            ],
        },
    ]


def _image_brief(image: PreparedImage) -> str:
    return (
        f"\nImage source: {image.source_label}. Image size: {image.width}x{image.height}. "
        f"Provenance and limitations: {image.provenance_note}\n"
        "Respect the image resolution. Do not identify individual boulders or surface "
        "texture without supporting optical detail. In a DEM hillshade, shading is "
        "synthetic topographic relief, not actual solar shadows or albedo."
    )


def detect_conflicts(analysis: AiAnalysis, science: ScientificAnalysis) -> list[str]:
    """Modelin ölçüm iddiasına girdiği yerleri işaretle.

    Gözlem silinmez; kullanıcı neyin ölçüm neyin yorum olduğunu görmeli.
    """
    conflicts: list[str] = []
    for observation in analysis.observations:
        if _MEASUREMENT_PATTERN.search(
            " ".join(
                (
                    observation.description,
                    observation.evidence,
                    observation.location_in_image or "",
                )
            )
        ):
            conflicts.append(
                f"Model '{observation.feature}' gözleminde sayısal ifade kullandı; "
                "ölçüm olarak alınmadı. Geçerli sayılar yalnızca bilimsel "
                "bölümdedir."
            )
    for hazard in analysis.potential_hazards:
        if _MEASUREMENT_PATTERN.search(hazard):
            conflicts.append(
                "Model tehlike ifadesinde sayı kullandı; nicel iniş güvenliği "
                "değerlendirmesi bu araçta yapılmaz."
            )
    if any(
        _MEASUREMENT_PATTERN.search(text)
        for text in (
            analysis.summary,
            analysis.terrain_interpretation,
        )
    ):
        conflicts.append(
            "Model yorumunda sayısal ölçüm iddiası var; bilimsel ölçüm olarak alınmadı."
        )
    if science.joint_visible_fraction == 0 and any(
        "visib" in item.description.lower() for item in analysis.observations
    ):
        conflicts.append(
            "Bilimsel sonuç bu pencerede ortak görünürlüğün sıfır olduğunu "
            "söylüyor; modelin görünürlük yorumu bunun yerine geçmez."
        )
    # Aynı metni tekrar tekrar göstermeye gerek yok.
    return list(dict.fromkeys(conflicts))


def analyze_region(
    context: RegionContext,
    image: PreparedImage,
    client: NimClient,
    max_tokens: int = 2048,
    focus: str = "",
) -> RegionAnalysis:
    """Tek bölge için uçtan uca analiz üret.

    Model çağrısı başarısız olursa bilimsel ölçümler yine döner; arayüz
    AI olmadan da çalışmaya devam eder (spec bölüm 12).
    """
    region = RegionRef(
        id=context.site_id,
        latitude=context.latitude_deg,
        longitude=context.longitude_deg_east,
        image_source=image.source_label,
    )
    notes: list[str] = [image.provenance_note]
    if image.is_rendered:
        notes.append("Görüntü çizimdir; aydınlatma ve gölge ölçüm değildir.")

    try:
        messages = build_messages(context, image)
        if focus:
            messages.append(
                {"role": "user", "content": f"Focus of visual inspection: {focus[:500]}"}
            )
        raw = client.chat(messages, max_tokens=max_tokens)
    except NimError as exc:
        return RegionAnalysis(
            region=region,
            ai_analysis=AiAnalysis(
                summary="",
                limitations=("Model çağrısı tamamlanamadı; görsel yorum yok.",),
            ),
            scientific_analysis=context.scientific,
            metadata=AnalysisMetadata(
                model=client.config.model,
                timestamp=utc_now(),
                status="failed",
                endpoint=client.config.endpoint,
                inference_executed=False,
                notes=tuple([*notes, str(exc)]),
            ),
        )

    analysis, parse_notes = normalize_ai_payload(raw)
    conflicts = detect_conflicts(analysis, context.scientific)
    status = (
        "completed"
        if (analysis.summary or analysis.observations) and not parse_notes
        else "partial"
    )

    return RegionAnalysis(
        region=region,
        ai_analysis=analysis,
        scientific_analysis=context.scientific,
        metadata=AnalysisMetadata(
            model=client.config.model,
            timestamp=utc_now(),
            status=status,
            endpoint=client.config.endpoint,
            inference_executed=True,
            notes=tuple([*notes, *parse_notes]),
        ),
        conflicts=tuple(conflicts),
    )


def ask_followup(
    context: RegionContext,
    image: PreparedImage,
    client: NimClient,
    question: str,
    history: list[dict[str, str]] | None = None,
    max_tokens: int = 512,
) -> str:
    """Seçili bölge hakkında serbest soru sor.

    Sohbet geçmişi bağlam sınırını aşmasın diye son birkaç tur taşınır.
    """
    messages: list[dict[str, object]] = [
        {
            "role": "system",
            "content": (
                SYSTEM_PROMPT.split("Respond with a single JSON object")[0]
                + "Answer in the user's language, in prose. Separate what you "
                "see in the image from the supplied measurements, and say "
                "plainly when something cannot be determined from the image."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _format_scientific_brief(context) + _image_brief(image)},
                {"type": "image_url", "image_url": {"url": image.data_url}},
            ],
        },
    ]
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})
    return client.chat(messages, max_tokens=max_tokens)


def observation_rows(analysis: RegionAnalysis) -> list[dict[str, str]]:
    """Gözlemleri tabloya uygun satırlara çevir."""
    return [
        {
            "Özellik": item.feature,
            "Gözlem": item.description,
            "Dayanak": item.evidence or "—",
            "Kesinlik": item.certainty,
            "Konum": item.location_in_image or "—",
        }
        for item in analysis.ai_analysis.observations
    ]
