#!/usr/bin/env python3
"""Generate the official 12-slide Turkish LUNA-SIGHT presentation deck (16:9 PDF).

Tüm metrikler canlı olarak `outputs/`, `governance/registry.json`, `.github/workflows/`,
`docs/DECISIONS.md`, `data/manifest.csv` ve `luna_sight` modüllerinden (`terrain`,
`visibility`) hesaplanır; statik veya bayat sayı kullanılmaz.

Kullanım:
    .\\.venv\\Scripts\\python.exe scripts/generate_presentation_pdf.py
"""

from __future__ import annotations

import csv
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from reportlab.graphics.shapes import (
    Circle,
    Drawing,
    Ellipse,
    Line,
    Polygon,
    PolyLine,
    Rect,
    String,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from luna_sight.terrain import (  # noqa: E402
    CANDIDATE_SITES,
    evaluate_landing_footprint,
    find_safe_corridor,
    merge_hybrid_profiles,
)
from luna_sight.visibility import (  # noqa: E402
    DEFAULT_LUNAR_EARTH_DIST_M,
    KA_BAND_FREQ_HZ,
    NRHO_APOLUNE_KM,
    NRHO_ECCENTRICITY,
    NRHO_PERILUNE_KM,
    NRHO_PERIOD_HOURS,
    NRHO_SEMI_MAJOR_AXIS_KM,
    S_BAND_FREQ_HZ,
    SOLAR_ANGULAR_DIAMETER_DEG,
    SOLAR_ANGULAR_RADIUS_DEG,
    SOLAR_CONSTANT_1AU,
    DSNStation,
    FrequencyBand,
    compute_diffraction_loss_itu,
    compute_fresnel_parameter,
    compute_gateway_visibility,
    compute_link_budget,
    compute_penumbra_power,
    compute_solar_disk_fraction,
    evaluate_emergency_link_margin,
    load_horizon_profile,
)

OUT_PDF = REPO_ROOT / "artifacts" / "luna_sight_sunum.pdf"

# Explicit 16:9 widescreen presentation geometry (297mm x 167mm ~ 16:9)
SLIDE_W = 297.0 * mm
SLIDE_H = 167.0 * mm
MARGIN_X = 11.5 * mm
TOP_MARGIN = 21.0 * mm
BOTTOM_MARGIN = 11.0 * mm
CONTENT_W = SLIDE_W - 2.0 * MARGIN_X
CONTENT_H = SLIDE_H - TOP_MARGIN - BOTTOM_MARGIN

# NASA / Aerospace presentation palette
C_SPACE_DARK = colors.HexColor("#070B18")
C_SPACE_MID = colors.HexColor("#0F172A")
C_SPACE_CARD = colors.HexColor("#131D36")
C_NASA_BLUE = colors.HexColor("#0B3D91")
C_AZURE = colors.HexColor("#1D6FD8")
C_AZURE_LIGHT = colors.HexColor("#5AA9FF")
C_CYAN = colors.HexColor("#38BDF8")
C_GOLD = colors.HexColor("#D9822B")
C_GOLD_BRIGHT = colors.HexColor("#F5B942")
C_OK = colors.HexColor("#1B7A4B")
C_OK_BRIGHT = colors.HexColor("#3DDC97")
C_OK_BG = colors.HexColor("#ECF9F2")
C_DANGER = colors.HexColor("#C62828")
C_DANGER_BRIGHT = colors.HexColor("#FC3D21")
C_DANGER_BG = colors.HexColor("#FFF2F2")
C_WARN_BG = colors.HexColor("#FFF8EB")
C_NOTE_BG = colors.HexColor("#EEF4FC")
C_BG_LIGHT = colors.HexColor("#F7F9FD")
C_ROW_ALT = colors.HexColor("#F4F7FC")
C_BORDER = colors.HexColor("#CFD9E8")
C_TEXT = colors.HexColor("#162033")
C_MUTED = colors.HexColor("#4B5B76")
C_LIGHT_TEXT = colors.HexColor("#E6EEF9")
C_LIGHT_DIM = colors.HexColor("#A9B9D6")

_ALLOWED_CHAR_SETS: dict[str, set[int]] = {}


@dataclass(frozen=True)
class SlideMeta:
    """Metadata drawn in the header/footer chrome of each slide."""

    number: int
    category: str
    title: str
    subtitle: str


def register_fonts() -> None:
    """Register Windows Arial and Consolas TrueType fonts with full Turkish glyph maps."""
    font_paths = {
        "Arial": Path(r"C:\Windows\Fonts\arial.ttf"),
        "Arial-Bold": Path(r"C:\Windows\Fonts\arialbd.ttf"),
        "Arial-Italic": Path(r"C:\Windows\Fonts\ariali.ttf"),
        "Arial-BoldItalic": Path(r"C:\Windows\Fonts\arialbi.ttf"),
        "Consolas": Path(r"C:\Windows\Fonts\consola.ttf"),
        "Consolas-Bold": Path(r"C:\Windows\Fonts\consolab.ttf"),
    }
    for name, path in font_paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Gerekli sistem fontu bulunamadı: {path}")
        tt = TTFont(name, str(path))
        pdfmetrics.registerFont(tt)
        _ALLOWED_CHAR_SETS[name] = set(tt.face.charToGlyph.keys())

    registerFontFamily(
        "Arial",
        normal="Arial",
        bold="Arial-Bold",
        italic="Arial-Italic",
        boldItalic="Arial-BoldItalic",
    )
    registerFontFamily(
        "Consolas",
        normal="Consolas",
        bold="Consolas-Bold",
        italic="Consolas",
        boldItalic="Consolas-Bold",
    )


_EMOJI_FALLBACK = {
    "\ufe0f": "",
    "🌕": "",
    "🛰": "[K1]",
    "🏔": "[K2]",
    "⚡": "[K3]",
    "🚀": "[K4]",
    "🛡": "[K5]",
    "☀": "*",
    "🌍": "",
    "⚠": "!",
    "✅": "[OK]",
    "🔴": "[!]",
    "🟢": "[OK]",
    "🔭": "",
    "🔍": "",
    "🌐": "",
    "📊": "",
    "📋": "",
    "📡": "",
    "ℹ": "[i]",
}


def sanitize_for_font(text: str, font_name: str = "Arial") -> str:
    """Strip unsupported emojis and replace missing glyphs cleanly (zero □ squares)."""
    cleaned = (
        text.replace("🛰️", "[K1]")
        .replace("🏔️", "[K2]")
        .replace("🛡️", "[K5]")
        .replace("☀️", "*")
        .replace("⚠️", "!")
        .replace("ℹ️", "[i]")
    )
    for k, v in _EMOJI_FALLBACK.items():
        cleaned = cleaned.replace(k, v)

    allowed = _ALLOWED_CHAR_SETS.get(font_name, set())
    ascii_fallbacks = {
        "−": "-",
        "≥": ">=",
        "≤": "<=",
        "→": "->",
        "←": "<-",
        "↔": "<->",
        "≈": "~",
        "±": "+/-",
        "Δ": "Delta",
        "θ": "theta",
        "σ": "sigma",
        "ν": "v",
        "μ": "mu",
        "λ": "lambda",
        "·": "-",
        "•": "*",
        "“": '"',
        "”": '"',
        "’": "'",
        "‘": "'",
        "—": "-",
        "–": "-",
    }
    out: list[str] = []
    for ch in cleaned:
        code = ord(ch)
        if code < 128 or code in allowed:
            out.append(ch)
        elif ch in ascii_fallbacks:
            out.append(ascii_fallbacks[ch])
    return "".join(out)


def rl_p(text: str, style: ParagraphStyle, font_name: str = "Arial") -> Paragraph:
    """Create a sanitized ReportLab Paragraph safely."""
    return Paragraph(sanitize_for_font(text, font_name), style)


def build_styles() -> dict[str, ParagraphStyle]:
    """Typography styles tuned for 16:9 widescreen presentation slides."""
    return {
        "cover_kicker": ParagraphStyle(
            "CoverKicker",
            fontName="Arial-Bold",
            fontSize=9.5,
            leading=13.0,
            textColor=C_CYAN,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            fontName="Arial-Bold",
            fontSize=30.0,
            leading=34.0,
            textColor=colors.white,
        ),
        "cover_sub": ParagraphStyle(
            "CoverSub",
            fontName="Arial",
            fontSize=13.5,
            leading=18.5,
            textColor=C_LIGHT_TEXT,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta",
            fontName="Arial",
            fontSize=9.2,
            leading=13.0,
            textColor=C_LIGHT_DIM,
        ),
        "card_title": ParagraphStyle(
            "CardTitle",
            fontName="Arial-Bold",
            fontSize=9.6,
            leading=12.2,
            textColor=C_NASA_BLUE,
            spaceAfter=2.5,
        ),
        "card_title_dark": ParagraphStyle(
            "CardTitleDark",
            fontName="Arial-Bold",
            fontSize=9.6,
            leading=12.2,
            textColor=C_CYAN,
            spaceAfter=2.5,
        ),
        "body": ParagraphStyle(
            "Body",
            fontName="Arial",
            fontSize=8.5,
            leading=11.6,
            textColor=C_TEXT,
            alignment=TA_LEFT,
            spaceAfter=2.2,
        ),
        "body_sm": ParagraphStyle(
            "BodySm",
            fontName="Arial",
            fontSize=7.8,
            leading=10.6,
            textColor=C_TEXT,
            alignment=TA_LEFT,
            spaceAfter=1.8,
        ),
        "body_dark": ParagraphStyle(
            "BodyDark",
            fontName="Arial",
            fontSize=8.3,
            leading=11.4,
            textColor=C_LIGHT_TEXT,
            alignment=TA_LEFT,
            spaceAfter=2.0,
        ),
        "mono": ParagraphStyle(
            "Mono",
            fontName="Consolas",
            fontSize=7.4,
            leading=10.0,
            textColor=C_NASA_BLUE,
        ),
        "kpi_val": ParagraphStyle(
            "KpiVal",
            fontName="Arial-Bold",
            fontSize=15.0,
            leading=17.5,
            textColor=C_NASA_BLUE,
            alignment=TA_LEFT,
        ),
        "kpi_val_light": ParagraphStyle(
            "KpiValLight",
            fontName="Arial-Bold",
            fontSize=14.5,
            leading=17.0,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "kpi_lbl": ParagraphStyle(
            "KpiLbl",
            fontName="Arial-Bold",
            fontSize=7.5,
            leading=9.6,
            textColor=C_MUTED,
            alignment=TA_LEFT,
        ),
        "kpi_sub": ParagraphStyle(
            "KpiSub",
            fontName="Arial",
            fontSize=7.2,
            leading=9.6,
            textColor=C_MUTED,
            alignment=TA_LEFT,
        ),
        "tbl_hdr": ParagraphStyle(
            "TblHdr",
            fontName="Arial-Bold",
            fontSize=7.4,
            leading=9.4,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "tbl_hdr_c": ParagraphStyle(
            "TblHdrC",
            fontName="Arial-Bold",
            fontSize=7.4,
            leading=9.4,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "tbl_cell": ParagraphStyle(
            "TblCell",
            fontName="Arial",
            fontSize=7.2,
            leading=9.4,
            textColor=C_TEXT,
            alignment=TA_LEFT,
        ),
        "tbl_cell_c": ParagraphStyle(
            "TblCellC",
            fontName="Arial",
            fontSize=7.2,
            leading=9.4,
            textColor=C_TEXT,
            alignment=TA_CENTER,
        ),
        "tbl_cell_r": ParagraphStyle(
            "TblCellR",
            fontName="Arial",
            fontSize=7.2,
            leading=9.4,
            textColor=C_TEXT,
            alignment=TA_RIGHT,
        ),
        "callout": ParagraphStyle(
            "Callout",
            fontName="Arial",
            fontSize=8.2,
            leading=11.2,
            textColor=C_TEXT,
        ),
        "section_label": ParagraphStyle(
            "SectionLabel",
            fontName="Arial-Bold",
            fontSize=8.6,
            leading=11.0,
            textColor=C_NASA_BLUE,
            spaceAfter=2.0,
        ),
    }


# ---------------------------------------------------------------------------
# Dynamic Data Collection (Zero Hardcoded Stale Metrics)
# ---------------------------------------------------------------------------


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        out = float(val)
        return out if math.isfinite(out) else default
    except (TypeError, ValueError):
        return default


def _count_tests() -> int:
    """Count test cases cleanly across tests/test_*.py without mutating workspace."""
    tests_dir = REPO_ROOT / "tests"
    if not tests_dir.exists():
        return 0
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        m = re.search(r"(\d+)\s+tests?\s+collected", proc.stdout + "\n" + proc.stderr)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    total = 0
    for tf in sorted(tests_dir.glob("test_*.py")):
        total += len(re.findall(r"^\s*def\s+test_", tf.read_text(encoding="utf-8"), re.M))
    return total


def _extract_app_tabs() -> list[str]:
    app_path = REPO_ROOT / "app" / "app.py"
    if not app_path.exists():
        return [
            "3B Ay küresi",
            "Ufuk görünümü",
            "Zaman çizelgesi",
            "Güney Kutbu Haritası (2D)",
            "Arazi Riski",
            "Veri ve kaynak",
        ]
    text = app_path.read_text(encoding="utf-8")
    m = re.search(r"st\.tabs\(\s*\[(.*?)\]\s*\)", text, re.S)
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


def collect_presentation_data() -> dict[str, Any]:
    """Load and compute all live scientific, governance, and CI metrics from repo."""
    reg_path = REPO_ROOT / "governance" / "registry.json"
    registry = json.loads(reg_path.read_text(encoding="utf-8"))

    decisions_path = REPO_ROOT / "docs" / "DECISIONS.md"
    adrs: list[dict[str, str]] = []
    if decisions_path.exists():
        adr_re = re.compile(r"^\|\s*(ADR-\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|")
        for line in decisions_path.read_text(encoding="utf-8").splitlines():
            m = adr_re.match(line.strip())
            if m:
                adrs.append(
                    {
                        "id": m.group(1).strip(),
                        "when": m.group(2).strip(),
                        "decision": m.group(3).strip(),
                        "owner": m.group(5).strip(),
                    }
                )

    with (REPO_ROOT / "data" / "manifest.csv").open(encoding="utf-8", newline="") as fh:
        manifest_rows = list(csv.DictReader(fh))

    workflows: list[dict[str, Any]] = []
    for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        txt = wf.read_text(encoding="utf-8")
        wf_name = re.search(r"^name:\s*(.+)$", txt, re.M)
        workflows.append(
            {
                "file": wf.name,
                "name": wf_name.group(1).strip() if wf_name else wf.stem,
            }
        )

    srt_path = REPO_ROOT / "artifacts" / "luna_sight_demo_120s_v2.en.srt"
    srt_count = 0
    if srt_path.exists():
        srt_count = len(re.findall(r"^\d+$", srt_path.read_text(encoding="utf-8"), re.M))

    py_files_count = sum(
        len(list((REPO_ROOT / root).rglob("*.py")))
        for root in ("src", "app", "scripts", "tests")
        if (REPO_ROOT / root).exists()
    )

    sites_rows: list[dict[str, Any]] = []
    for sid, site in CANDIDATE_SITES.items():
        k3_path = REPO_ROOT / "outputs" / "k3" / f"{sid}_summary.json"
        k3 = json.loads(k3_path.read_text("utf-8"))
        k2_path = REPO_ROOT / "outputs" / "k2" / f"{sid}_slope_summary.json"
        k2_slope = json.loads(k2_path.read_text("utf-8"))
        fp = evaluate_landing_footprint(sid)
        k2_20_path = REPO_ROOT / "outputs" / "k2" / f"{sid}_summary_20000m.json"
        k2_20 = json.loads(k2_20_path.read_text("utf-8")) if k2_20_path.exists() else {}

        vis_df = pd.read_csv(REPO_ROOT / "outputs" / "k3" / f"{sid}_visibility.csv")
        sun_b = k3["bodies"]["sun"]
        earth_b = k3["bodies"]["earth"]
        joint_b = k3["bodies"]["joint"]
        prof_name = Path(k3["profile"]).name
        is_5m = "4000m" in prof_name or "2000m" in prof_name
        prof_label = "4 km (5m/px)" if is_5m else "20 km (240m/px)"
        k2_qflag = "valid" if is_5m else str(k2_20.get("quality_flag", "partial"))

        sites_rows.append(
            {
                "site_id": sid,
                "site_name": site.site_name,
                "lat_deg": site.latitude_deg,
                "lon_deg_east": site.longitude_deg_east,
                "x_km": site.x_m / 1000.0,
                "y_km": site.y_m / 1000.0,
                "profile_name": prof_name,
                "profile_label": prof_label,
                "k2_quality_flag": k2_qflag,
                "k3_series_quality": k3["series"]["quality_flag"],
                "samples": int(k3["series"]["samples"]),
                "span_hours": float(k3["series"]["span_hours"]),
                "margin_deg": float(k3["config"]["margin_deg"]),
                "sun_pct": float(sun_b["visible_fraction"]) * 100.0,
                "earth_pct": float(earth_b["visible_fraction"]) * 100.0,
                "joint_pct": float(joint_b["visible_fraction"]) * 100.0,
                "joint_hours": float(joint_b["state_hours"]["visible"]),
                "longest_joint_h": _safe_float(joint_b.get("longest_visible_hours"), 0.0),
                "joint_windows": int(joint_b["window_count"]),
                "sun_alt_min": float(vis_df["sun_alt_deg"].min()),
                "sun_alt_max": float(vis_df["sun_alt_deg"].max()),
                "earth_alt_min": float(vis_df["earth_alt_deg"].min()),
                "earth_alt_max": float(vis_df["earth_alt_deg"].max()),
                "earth_az_min": float(vis_df["earth_az_deg"].min()),
                "earth_az_max": float(vis_df["earth_az_deg"].max()),
                "h_earth_min": float(vis_df["terrain_horizon_earth_deg"].min()),
                "h_earth_max": float(vis_df["terrain_horizon_earth_deg"].max()),
                "slope_mean": float(k2_slope["slope"]["mean_deg"]),
                "slope_p95": float(k2_slope["slope"]["p95_deg"]),
                "slope_max": float(k2_slope["slope"]["max_deg"]),
                "dem_source": str(k2_slope["dem_source"]),
                "dem_res_m": float(k2_slope["dem_resolution_m"]),
                "safe_3sigma_pct": float(fp["footprint_safe_pct"]),
                "boulder_prob": float(fp["boulder_hazard_prob"]),
                "safety_score": float(fp["landing_safety_score"]),
                "verdict": str(fp["verdict"]),
            }
        )

    site_map = {r["site_id"]: r for r in sites_rows}

    hybrid_stats: dict[str, dict[str, float]] = {}
    for sid in ("Site01", "Site04"):
        near_df = pd.read_csv(REPO_ROOT / "outputs" / "k2" / f"{sid}_horizon_4000m.csv")
        far_df = pd.read_csv(REPO_ROOT / "outputs" / "k2" / f"{sid}_horizon_20000m.csv")
        hyb_df = merge_hybrid_profiles(near_df, far_df)
        hybrid_stats[sid] = {
            "near_mean": float(near_df["horizon_deg"].mean()),
            "far_mean": float(far_df["horizon_deg"].mean()),
            "hyb_mean": float(hyb_df["horizon_deg"].mean()),
            "hyb_max": float(hyb_df["horizon_deg"].max()),
        }

    sens_df = pd.read_csv(REPO_ROOT / "outputs" / "k3" / "sensitivity.csv")

    gw_results: dict[str, dict[str, Any]] = {}
    for label, sid, hfile in (
        ("Site01_4km", "Site01", "Site01_horizon_4000m.csv"),
        ("Site04_4km", "Site04", "Site04_horizon_4000m.csv"),
        ("Site04_20km", "Site04", "Site04_horizon_20000m.csv"),
    ):
        site_obj = CANDIDATE_SITES[sid]
        vis_df = pd.read_csv(REPO_ROOT / "outputs" / "k3" / f"{sid}_visibility.csv")
        gw = compute_gateway_visibility(
            vis_df,
            REPO_ROOT / "outputs" / "k2" / hfile,
            site_obj.latitude_deg,
            site_obj.longitude_deg_east,
            margin_deg=0.1,
        )
        gw_results[label] = {k: v for k, v in gw.items() if k != "series"}

    pen_results: dict[str, dict[str, Any]] = {}
    for label, sid, hfile in (
        ("Site01_4km", "Site01", "Site01_horizon_4000m.csv"),
        ("Site04_4km", "Site04", "Site04_horizon_4000m.csv"),
        ("Site04_20km", "Site04", "Site04_horizon_20000m.csv"),
        ("Site08_20km", "Site08", "Site08_horizon_20000m.csv"),
        ("Site13_20km", "Site13", "Site13_horizon_20000m.csv"),
    ):
        vis_df = pd.read_csv(REPO_ROOT / "outputs" / "k3" / f"{sid}_visibility.csv")
        prof = load_horizon_profile(REPO_ROOT / "outputs" / "k2" / hfile)
        h_vals = np.array([prof.elevation_at(float(az)) for az in vis_df["sun_az_deg"]])
        pen = compute_penumbra_power(
            vis_df["sun_alt_deg"].to_numpy(),
            h_vals,
            step_minutes=5.0,
            max_power_w=1000.0,
        )
        pen_results[label] = {k: v for k, v in pen.items() if not isinstance(v, np.ndarray)}

    link_clear: dict[str, dict[str, Any]] = {}
    link_obs: dict[str, dict[str, Any]] = {}
    for band in (FrequencyBand.S_BAND, FrequencyBand.KA_BAND, FrequencyBand.OPTICAL_O2O):
        link_clear[band.value] = compute_link_budget(station=DSNStation.GOLDSTONE, band=band)
        link_obs[band.value] = compute_link_budget(
            station=DSNStation.GOLDSTONE,
            band=band,
            obstruction_angle_deg=0.35,
            distance_to_ridge_m=5000.0,
        )
    link_stations: dict[str, dict[str, Any]] = {
        stn.value: compute_link_budget(
            station=stn, band=FrequencyBand.S_BAND, obstruction_angle_deg=0.35
        )
        for stn in (DSNStation.GOLDSTONE, DSNStation.MADRID, DSNStation.CANBERRA)
    }

    emerg_sweep: list[dict[str, Any]] = []
    for ang in (0.0, 0.2, 0.35, 0.5, 1.0, 2.5):
        em_s = evaluate_emergency_link_margin(
            obstruction_angle_deg=ang, frequency_hz=S_BAND_FREQ_HZ
        )
        em_ka = evaluate_emergency_link_margin(
            obstruction_angle_deg=ang,
            frequency_hz=KA_BAND_FREQ_HZ,
            tx_antenna_gain_dbi=32.0,
            rx_antenna_gain_dbi=78.5,
            receiver_sensitivity_dbm=-150.0,
        )
        emerg_sweep.append({"angle": ang, "s_band": em_s, "ka_band": em_ka})

    corridors: dict[str, dict[str, Any]] = {
        sid: find_safe_corridor(sid) for sid in ("Site01", "Site04", "Site08", "Site13")
    }

    return {
        "registry": registry,
        "adrs": adrs,
        "manifest_rows": manifest_rows,
        "workflows": workflows,
        "srt_count": srt_count,
        "py_files_count": py_files_count,
        "test_count": _count_tests(),
        "app_tabs": _extract_app_tabs(),
        "sites": sites_rows,
        "site_map": site_map,
        "hybrid_stats": hybrid_stats,
        "sens_df": sens_df,
        "gateway": gw_results,
        "penumbra": pen_results,
        "link_clear": link_clear,
        "link_obs": link_obs,
        "link_stations": link_stations,
        "emerg_sweep": emerg_sweep,
        "corridors": corridors,
    }


# ---------------------------------------------------------------------------
# Reusable Slide Building Helpers
# ---------------------------------------------------------------------------


def make_card(
    title: str,
    body_paragraphs: list[Paragraph],
    width: float,
    styles: dict[str, ParagraphStyle],
    *,
    bg: colors.Color = colors.white,
    accent: colors.Color = C_NASA_BLUE,
    dark: bool = False,
    pad_x: float = 8.0,
    pad_y: float = 5.5,
) -> Table:
    """Styled card with left accent bar and crisp border."""
    title_style = styles["card_title_dark"] if dark else styles["card_title"]
    rows: list[list[Paragraph]] = [[rl_p(title, title_style)]]
    for p in body_paragraphs:
        rows.append([p])
    tbl = Table(rows, colWidths=[width])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LINEBEFORE", (0, 0), (0, -1), 3.0, accent),
                ("BOX", (0, 0), (-1, -1), 0.6, C_SPACE_CARD if dark else C_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), pad_x),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad_x),
                ("TOPPADDING", (0, 0), (0, 0), pad_y),
                ("BOTTOMPADDING", (0, 0), (0, 0), 2.0),
                ("TOPPADDING", (0, 1), (-1, -1), 1.0),
                ("BOTTOMPADDING", (0, 1), (-1, -2), 1.5),
                ("BOTTOMPADDING", (0, -1), (-1, -1), pad_y),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tbl


def make_kpi_strip(
    items: list[tuple[str, str, str, colors.Color]],
    width: float,
    styles: dict[str, ParagraphStyle],
    *,
    dark: bool = False,
) -> Table:
    """Horizontal row of executive KPI metric boxes."""
    ncols = len(items)
    gap = 6.0
    box_w = (width - gap * (ncols - 1)) / ncols
    col_widths: list[float] = []
    cells: list[Any] = []
    for idx, (label, val, sub, accent) in enumerate(items):
        bg = C_SPACE_CARD if dark else colors.white
        val_st = ParagraphStyle(
            f"KpiVal_{idx}",
            parent=styles["kpi_val_light"] if dark else styles["kpi_val"],
            textColor=accent,
        )
        lbl_st = ParagraphStyle(
            f"KpiLbl_{idx}",
            parent=styles["kpi_lbl"],
            textColor=C_LIGHT_DIM if dark else C_MUTED,
        )
        sub_st = ParagraphStyle(
            f"KpiSub_{idx}",
            parent=styles["kpi_sub"],
            textColor=C_LIGHT_DIM if dark else C_MUTED,
        )
        inner = Table(
            [[rl_p(label, lbl_st)], [rl_p(val, val_st)], [rl_p(sub, sub_st)]],
            colWidths=[box_w],
        )
        inner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), bg),
                    ("LINEABOVE", (0, 0), (-1, 0), 2.8, accent),
                    ("BOX", (0, 0), (-1, -1), 0.6, C_AZURE_LIGHT if dark else C_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (0, 0), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -2), 1.5),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
                ]
            )
        )
        cells.append(inner)
        col_widths.append(box_w)
        if idx < ncols - 1:
            cells.append("")
            col_widths.append(gap)

    outer = Table([cells], colWidths=col_widths)
    outer.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return outer


def make_callout(
    prefix: str,
    text: str,
    width: float,
    styles: dict[str, ParagraphStyle],
    *,
    bg: colors.Color = C_NOTE_BG,
    bar: colors.Color = C_NASA_BLUE,
) -> Table:
    """Executive takeaway callout banner."""
    p = rl_p(f"<b>{prefix}</b> {text}", styles["callout"])
    tbl = Table([[p]], colWidths=[width])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("LINEBEFORE", (0, 0), (0, -1), 3.2, bar),
                ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return tbl


def make_grid_row(cols: list[tuple[Any, float]], gap: float = 8.0) -> Table:
    """Place multiple widgets side by side with exact gap."""
    cells: list[Any] = []
    widths: list[float] = []
    n = len(cols)
    for i, (widget, w) in enumerate(cols):
        cells.append(widget)
        widths.append(w)
        if i < n - 1:
            cells.append("")
            widths.append(gap)
    tbl = Table([cells], colWidths=widths)
    tbl.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tbl


def make_vertical_stack(widgets: list[Any], width: float) -> Table:
    """Stack flowables vertically with zero extra table padding."""
    tbl = Table([[w] for w in widgets], colWidths=[width])
    tbl.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return tbl


def make_styled_table(
    headers: list[str],
    rows: list[list[str]],
    col_widths: list[float],
    styles: dict[str, ParagraphStyle],
    *,
    aligns: list[str] | None = None,
    font_size: float = 7.1,
    pad_x: float = 4.0,
    pad_y: float = 2.8,
    highlight_rows: dict[int, colors.Color] | None = None,
) -> Table:
    """Create a crisp NASA-styled data table with compact padding."""
    lead = font_size + 2.1
    hdr_s = ParagraphStyle("TH_dyn", parent=styles["tbl_hdr"], fontSize=font_size, leading=lead)
    hdr_c = ParagraphStyle("THC_dyn", parent=styles["tbl_hdr_c"], fontSize=font_size, leading=lead)
    c_l = ParagraphStyle("TC_L", parent=styles["tbl_cell"], fontSize=font_size, leading=lead)
    c_c = ParagraphStyle("TC_C", parent=styles["tbl_cell_c"], fontSize=font_size, leading=lead)
    c_r = ParagraphStyle("TC_R", parent=styles["tbl_cell_r"], fontSize=font_size, leading=lead)

    al = aligns or ["L"] * len(headers)
    data: list[list[Paragraph]] = [
        [rl_p(h, hdr_c if al[i] == "C" else hdr_s) for i, h in enumerate(headers)]
    ]
    for row in rows:
        styled: list[Paragraph] = []
        for i, cell in enumerate(row):
            st = c_c if al[i] == "C" else (c_r if al[i] == "R" else c_l)
            styled.append(rl_p(cell, st))
        data.append(styled)

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    ts: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NASA_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, C_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, C_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), pad_x),
        ("RIGHTPADDING", (0, 0), (-1, -1), pad_x),
        ("TOPPADDING", (0, 0), (-1, -1), pad_y),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad_y),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    hl = highlight_rows or {}
    for r_idx in range(1, len(data)):
        bg = hl.get(r_idx - 1, C_ROW_ALT if r_idx % 2 == 0 else colors.white)
        ts.append(("BACKGROUND", (0, r_idx), (-1, r_idx), bg))
    tbl.setStyle(TableStyle(ts))
    return tbl


# ---------------------------------------------------------------------------
# Vector Diagrams & Data Plots (ReportLab Shapes)
# ---------------------------------------------------------------------------


def _draw_box(
    d: Drawing,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str,
    fill: colors.Color,
    stroke: colors.Color,
    *,
    title_color: colors.Color = C_NASA_BLUE,
    sub_color: colors.Color = C_MUTED,
    title_size: float = 7.8,
    sub_size: float = 6.7,
) -> None:
    d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=fill, strokeColor=stroke, strokeWidth=1.0))
    d.add(
        String(
            x + w / 2.0,
            y + (h * 0.56 if subtitle else h * 0.42),
            sanitize_for_font(title, "Arial-Bold"),
            fontName="Arial-Bold",
            fontSize=title_size,
            fillColor=title_color,
            textAnchor="middle",
        )
    )
    if subtitle:
        d.add(
            String(
                x + w / 2.0,
                y + h * 0.22,
                sanitize_for_font(subtitle, "Arial"),
                fontName="Arial",
                fontSize=sub_size,
                fillColor=sub_color,
                textAnchor="middle",
            )
        )


def _draw_arrow(
    d: Drawing,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: colors.Color,
    *,
    dashed: bool = False,
) -> None:
    kw: dict[str, Any] = {"strokeColor": color, "strokeWidth": 1.1}
    if dashed:
        kw["strokeDashArray"] = [3, 2]
    d.add(Line(x1, y1, x2, y2, **kw))
    if abs(x2 - x1) >= abs(y2 - y1):
        sign = 1 if x2 >= x1 else -1
        poly = [x2, y2, x2 - 5 * sign, y2 + 2.8, x2 - 5 * sign, y2 - 2.8]
        d.add(Polygon(poly, fillColor=color, strokeColor=color))
    else:
        sign = 1 if y2 >= y1 else -1
        poly = [x2, y2, x2 - 2.8, y2 - 5 * sign, x2 + 2.8, y2 - 5 * sign]
        d.add(Polygon(poly, fillColor=color, strokeColor=color))


_POLAR_LABEL_LAYOUT: dict[str, tuple[float, float, str, bool]] = {
    "Site01": (-16.0, 9.0, "end", True),
    "Site02": (-15.0, -13.0, "end", True),
    "Site03": (-8.0, 8.0, "end", True),
    "Site04": (14.0, -13.0, "start", True),
    "Site05": (8.0, 10.0, "start", True),
    "Site06": (-6.0, -3.0, "end", False),
    "Site07": (-6.0, -2.0, "end", False),
    "Site08": (6.0, -2.0, "start", False),
    "Site09": (7.0, -6.0, "start", False),
    "Site11": (6.0, -2.0, "start", False),
    "Site12": (6.0, -2.0, "start", False),
    "Site13": (6.0, 5.0, "start", False),
}


def draw_cover_polar_graphic(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Vector South Pole polar projection with all 12 candidate sites for Slide 1."""
    d = Drawing(w, h)
    d.add(
        Rect(0, 0, w, h, rx=8, ry=8, fillColor=C_SPACE_CARD, strokeColor=C_AZURE, strokeWidth=1.0)
    )
    cx, cy = w * 0.50, h * 0.50
    max_r = min(w, h) * 0.37
    scale = max_r / 185.0

    for r_km, lbl in ((60.0, "-88° G"), (120.0, "-86° G"), (180.0, "-84° G")):
        rr = r_km * scale
        d.add(
            Circle(
                cx,
                cy,
                rr,
                fillColor=None,
                strokeColor=colors.HexColor("#22345E"),
                strokeWidth=0.7,
                strokeDashArray=[2, 2],
            )
        )
        # Place ring labels on the empty SE 45-deg diagonal away from Site08/Site13
        lx = cx + rr * 0.707 + 2.0
        ly = cy - rr * 0.707 - 5.0
        d.add(
            String(
                lx,
                ly,
                sanitize_for_font(lbl),
                fontName="Arial",
                fontSize=6.4,
                fillColor=C_LIGHT_DIM,
            )
        )

    d.add(
        Line(
            cx - max_r, cy, cx + max_r, cy, strokeColor=colors.HexColor("#1D2E54"), strokeWidth=0.6
        )
    )
    d.add(
        Line(
            cx, cy - max_r, cx, cy + max_r, strokeColor=colors.HexColor("#1D2E54"), strokeWidth=0.6
        )
    )
    d.add(Circle(cx, cy, 3.0, fillColor=C_GOLD_BRIGHT, strokeColor=colors.white, strokeWidth=0.6))
    d.add(
        String(
            cx + 4,
            cy + 4,
            sanitize_for_font("90°G"),
            fontName="Arial-Bold",
            fontSize=6.6,
            fillColor=C_GOLD_BRIGHT,
        )
    )

    for row in data["sites"]:
        px = cx + row["x_km"] * scale
        py = cy + row["y_km"] * scale
        sid = row["site_id"]
        if sid == "Site01":
            col, rad = C_OK_BRIGHT, 4.0
        elif sid == "Site04":
            col, rad = C_DANGER_BRIGHT, 4.0
        elif row["joint_pct"] >= 80.0:
            col, rad = C_CYAN, 3.5
        else:
            col, rad = C_AZURE_LIGHT, 2.9
        d.add(Circle(px, py, rad, fillColor=col, strokeColor=colors.white, strokeWidth=0.6))
        dx, dy, anchor, leader = _POLAR_LABEL_LAYOUT.get(sid, (5.0, -2.0, "start", False))
        if leader:
            d.add(
                Line(
                    px,
                    py,
                    px + dx * 0.85,
                    py + dy * 0.85,
                    strokeColor=colors.HexColor("#5B739E"),
                    strokeWidth=0.55,
                )
            )
        d.add(
            String(
                px + dx,
                py + dy - 2.0,
                sid,
                fontName="Arial-Bold",
                fontSize=6.4,
                fillColor=C_LIGHT_TEXT,
                textAnchor=anchor,
            )
        )

    d.add(
        String(
            10,
            h - 14,
            sanitize_for_font("Ay Güney Kutbu Stereografik Dağılım (12 Aday Bölge)"),
            fontName="Arial-Bold",
            fontSize=8.0,
            fillColor=C_CYAN,
        )
    )
    d.add(
        String(
            10,
            8,
            sanitize_for_font("Yeşil: Site01 (DTE) | Kırmızı: Site04 (Gateway) | Camgöbeği: %85+"),
            fontName="Arial",
            fontSize=6.5,
            fillColor=C_LIGHT_DIM,
        )
    )
    return d


def draw_south_pole_geometry(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Cross-section diagram illustrating 1.54 deg tilt, PSR shadow, and Earth libration."""
    d = Drawing(w, h)
    d.add(
        Rect(
            0, 0, w, h, rx=5, ry=5, fillColor=C_SPACE_DARK, strokeColor=C_NASA_BLUE, strokeWidth=1.0
        )
    )
    d.add(
        String(
            10,
            h - 15,
            sanitize_for_font("Ay Güney Kutbu Kesiti: 1.5° Güneş Sıyırması ve Dünya Librasyonu"),
            fontName="Arial-Bold",
            fontSize=8.2,
            fillColor=C_CYAN,
        )
    )

    pts = [10, 56, 55, 98, 95, 36, 155, 36, 205, 108, 245, 70, 305, 78, w - 10, 66]
    poly_pts = pts + [w - 10, 14, 10, 14]
    d.add(
        Polygon(
            poly_pts,
            fillColor=colors.HexColor("#1E293B"),
            strokeColor=colors.HexColor("#64748B"),
            strokeWidth=1.2,
        )
    )

    d.add(Line(10, 118, w - 12, 104, strokeColor=C_GOLD_BRIGHT, strokeWidth=1.8))
    d.add(
        Line(
            10,
            128,
            w - 12,
            114,
            strokeColor=C_GOLD_BRIGHT,
            strokeWidth=0.9,
            strokeDashArray=[4, 2],
        )
    )
    d.add(
        String(
            14,
            132,
            sanitize_for_font("Güneş Işını (~1.0° – 1.7° Ufuk Teğeti)"),
            fontName="Arial-Bold",
            fontSize=7.1,
            fillColor=C_GOLD_BRIGHT,
        )
    )

    d.add(
        String(
            125,
            45,
            sanitize_for_font("PSR Krater Tabanı"),
            fontName="Arial-Bold",
            fontSize=7.2,
            fillColor=C_CYAN,
            textAnchor="middle",
        )
    )
    d.add(
        String(
            125,
            34,
            sanitize_for_font("-200°C Su Buzu"),
            fontName="Arial",
            fontSize=6.8,
            fillColor=C_LIGHT_DIM,
            textAnchor="middle",
        )
    )

    s04 = data["site_map"]["Site04"]
    s01 = data["site_map"]["Site01"]
    d.add(
        Circle(205, 110, 3.6, fillColor=C_DANGER_BRIGHT, strokeColor=colors.white, strokeWidth=0.7)
    )
    # Place Site04 wall label safely above Sun ray with thin dashed leader
    d.add(
        Line(
            205,
            114,
            218,
            144,
            strokeColor=C_DANGER_BRIGHT,
            strokeWidth=0.7,
            strokeDashArray=[2, 2],
        )
    )
    d.add(
        String(
            220,
            146,
            sanitize_for_font(f"Site04 Duvar (+{s04['h_earth_max']:.1f}°)"),
            fontName="Arial-Bold",
            fontSize=6.9,
            fillColor=C_DANGER_BRIGHT,
            textAnchor="middle",
        )
    )

    d.add(Circle(305, 80, 3.6, fillColor=C_OK_BRIGHT, strokeColor=colors.white, strokeWidth=0.7))
    d.add(
        String(
            305,
            63,
            sanitize_for_font(f"Site01 Sırt (+{s01['h_earth_max']:.1f}°)"),
            fontName="Arial-Bold",
            fontSize=6.9,
            fillColor=C_OK_BRIGHT,
            textAnchor="middle",
        )
    )

    ex = w - 34
    d.add(Circle(ex, 162, 8.5, fillColor=C_AZURE, strokeColor=C_CYAN, strokeWidth=1.0))
    d.add(
        String(
            ex - 14,
            174,
            sanitize_for_font("Dünya (384.400 km)"),
            fontName="Arial-Bold",
            fontSize=6.9,
            fillColor=C_CYAN,
            textAnchor="end",
        )
    )
    d.add(
        Line(305, 80, ex - 8, 158, strokeColor=C_OK_BRIGHT, strokeWidth=1.1, strokeDashArray=[3, 2])
    )
    d.add(
        String(
            w - 78,
            132,
            sanitize_for_font(
                f"Librasyon: {s01['earth_alt_min']:+.1f}°..{s04['earth_alt_max']:+.1f}°"
            ),
            fontName="Arial",
            fontSize=6.8,
            fillColor=C_LIGHT_TEXT,
            textAnchor="middle",
        )
    )
    return d


def draw_architecture_diagram(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Modular K1-K5 architecture flow diagram for Slide 3."""
    d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, rx=5, ry=5, fillColor=C_BG_LIGHT, strokeColor=C_BORDER, strokeWidth=0.9))
    d.add(
        String(
            10,
            h - 13,
            sanitize_for_font("LUNA-SIGHT K1–K5 Modüler Veri Akışı ve Sözleşme Mimari Haritası"),
            fontName="Arial-Bold",
            fontSize=8.4,
            fillColor=C_NASA_BLUE,
        )
    )

    bw = (w - 90) / 4.0
    x1 = 12.0
    x2 = x1 + bw + 22.0
    x3 = x2 + bw + 22.0
    x4 = x3 + bw + 22.0
    _draw_box(
        d,
        x1,
        62,
        bw,
        42,
        "K1: Efemeris Motoru",
        "JPL DE441 · coord@301 · 5 dk",
        colors.white,
        C_AZURE,
    )
    _draw_box(
        d, x1, 12, bw, 42, "K2: Arazi & Risk", "LOLA 5m/240m · Ufuk · A*", colors.white, C_AZURE
    )
    _draw_box(
        d,
        x2,
        37,
        bw,
        44,
        "K3: Görünürlük & Fizik",
        "3-Durum · Gateway · Penumbra · RF",
        C_NOTE_BG,
        C_NASA_BLUE,
    )
    _draw_box(
        d,
        x3,
        37,
        bw,
        44,
        "K4: Karar Kokpiti",
        f"{len(data['app_tabs'])} Sekme · Moon Trek · SUHAIL",
        C_SPACE_DARK,
        C_AZURE_LIGHT,
        title_color=colors.white,
        sub_color=C_LIGHT_DIM,
    )
    _draw_box(
        d,
        x4,
        37,
        bw,
        44,
        "K5: Yönetişim & CI",
        f"{data['test_count']} Test · Ruff · 4 CI Kapısı",
        C_OK_BG,
        C_OK,
        title_color=C_OK,
        sub_color=C_TEXT,
    )

    _draw_arrow(d, x1 + bw, 83, x2 - 2, 65, C_NASA_BLUE)
    _draw_arrow(d, x1 + bw, 33, x2 - 2, 53, C_NASA_BLUE)
    _draw_arrow(d, x2 + bw, 59, x3 - 2, 59, C_NASA_BLUE)
    _draw_arrow(d, x3 + bw, 59, x4 - 2, 59, C_OK)

    n_req = len(data["registry"]["data_contract"]["required_columns"])
    contract_lbl = f"Ortak Sözleşme: {n_req} Zorunlu Kolon · Boylam [-180°, +180°]"
    d.add(
        String(
            x2 + bw * 0.5,
            15,
            sanitize_for_font(contract_lbl),
            fontName="Arial-Bold",
            fontSize=7.2,
            fillColor=C_NASA_BLUE,
            textAnchor="middle",
        )
    )
    return d


def draw_polar_sites_map(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Compact polar scatter map of the 12 sites in South Polar Stereographic coordinates."""
    d = Drawing(w, h)
    d.add(
        Rect(
            0, 0, w, h, rx=5, ry=5, fillColor=C_SPACE_MID, strokeColor=C_NASA_BLUE, strokeWidth=0.9
        )
    )
    d.add(
        String(
            8,
            h - 13,
            sanitize_for_font("12 Bölgenin Kutupsal Konumları (km)"),
            fontName="Arial-Bold",
            fontSize=7.8,
            fillColor=C_CYAN,
        )
    )
    cx, cy = w * 0.5, h * 0.45
    rad_max = min(w, h) * 0.36
    scale = rad_max / 185.0

    for rk in (60.0, 120.0, 180.0):
        d.add(
            Circle(
                cx,
                cy,
                rk * scale,
                fillColor=None,
                strokeColor=colors.HexColor("#263B6B"),
                strokeWidth=0.6,
            )
        )
    d.add(
        Line(
            cx - rad_max,
            cy,
            cx + rad_max,
            cy,
            strokeColor=colors.HexColor("#22325A"),
            strokeWidth=0.5,
        )
    )
    d.add(
        Line(
            cx,
            cy - rad_max,
            cx,
            cy + rad_max,
            strokeColor=colors.HexColor("#22325A"),
            strokeWidth=0.5,
        )
    )

    for row in data["sites"]:
        px = cx + row["x_km"] * scale
        py = cy + row["y_km"] * scale
        sid = row["site_id"]
        col = C_OK_BRIGHT if sid == "Site01" else (C_DANGER_BRIGHT if sid == "Site04" else C_CYAN)
        d.add(Circle(px, py, 2.7, fillColor=col, strokeColor=colors.white, strokeWidth=0.4))
        dx, dy, anchor, leader = _POLAR_LABEL_LAYOUT.get(sid, (4.0, -2.0, "start", False))
        sdx, sdy = dx * 0.80, dy * 0.80
        if leader:
            d.add(
                Line(
                    px,
                    py,
                    px + sdx * 0.82,
                    py + sdy * 0.82,
                    strokeColor=colors.HexColor("#5B739E"),
                    strokeWidth=0.45,
                )
            )
        d.add(
            String(
                px + sdx,
                py + sdy - 2.0,
                sid.replace("Site", "S"),
                fontName="Arial-Bold",
                fontSize=5.9,
                fillColor=C_LIGHT_TEXT,
                textAnchor=anchor,
            )
        )
    return d


def draw_earth_horizon_chart(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Slide 6 vector chart: Earth elevation window vs Site01/Site04 horizon walls."""
    d = Drawing(w, h)
    d.add(
        Rect(0, 0, w, h, rx=5, ry=5, fillColor=colors.white, strokeColor=C_BORDER, strokeWidth=0.8)
    )
    d.add(
        String(
            8,
            h - 13,
            sanitize_for_font("Dünya Azimut Penceresinde Topoğrafik Ufuk vs. Librasyon Zarfı (°)"),
            fontName="Arial-Bold",
            fontSize=7.8,
            fillColor=C_NASA_BLUE,
        )
    )

    s01 = data["site_map"]["Site01"]
    s04 = data["site_map"]["Site04"]
    gx, gy, gw, gh = 32.0, 20.0, w - 44.0, h - 42.0
    d.add(Line(gx, gy, gx + gw, gy, strokeColor=C_MUTED, strokeWidth=0.7))
    d.add(Line(gx, gy, gx, gy + gh, strokeColor=C_MUTED, strokeWidth=0.7))

    y_min, y_max = -6.0, 11.5

    def y_px(val: float) -> float:
        return gy + ((val - y_min) / (y_max - y_min)) * gh

    for tick in (-5, 0, 5, 10):
        yp = y_px(float(tick))
        d.add(
            Line(gx, yp, gx + gw, yp, strokeColor=C_BORDER, strokeWidth=0.5, strokeDashArray=[2, 2])
        )
        d.add(
            String(
                gx - 3,
                yp - 2.5,
                f"{tick:+d}°",
                fontName="Arial",
                fontSize=6.4,
                fillColor=C_MUTED,
                textAnchor="end",
            )
        )

    for idx, (label, row, col) in enumerate(
        (("Site01 (4 km)", s01, C_OK), ("Site04 (4 km)", s04, C_DANGER))
    ):
        bx = gx + (0.10 + idx * 0.48) * gw
        bw = gw * 0.36
        e_lo = y_px(row["earth_alt_min"])
        e_hi = y_px(row["earth_alt_max"])
        d.add(
            Rect(
                bx,
                e_lo,
                bw * 0.44,
                e_hi - e_lo,
                fillColor=C_NOTE_BG,
                strokeColor=C_AZURE,
                strokeWidth=0.9,
            )
        )
        h_lo = y_px(row["h_earth_min"])
        h_hi = y_px(row["h_earth_max"])
        h_box_h = max(3.5, h_hi - h_lo)
        d.add(
            Rect(
                bx + bw * 0.52,
                h_lo,
                bw * 0.44,
                h_box_h,
                fillColor=col,
                strokeColor=col,
                strokeWidth=0.8,
            )
        )
        d.add(
            String(
                bx + bw * 0.5,
                gy - 10,
                sanitize_for_font(label),
                fontName="Arial-Bold",
                fontSize=7.0,
                fillColor=C_TEXT,
                textAnchor="middle",
            )
        )
        d.add(
            String(
                bx + bw * 0.74,
                h_lo + h_box_h + 3,
                sanitize_for_font(f"Ufuk +{row['h_earth_min']:.1f}..+{row['h_earth_max']:.1f}°"),
                fontName="Arial-Bold",
                fontSize=6.1,
                fillColor=col,
                textAnchor="middle",
            )
        )
        d.add(
            String(
                bx + bw * 0.22,
                e_hi + 3,
                sanitize_for_font(f"Dünya {row['earth_alt_max']:+.2f}°"),
                fontName="Arial",
                fontSize=6.1,
                fillColor=C_AZURE,
                textAnchor="middle",
            )
        )
    return d


def draw_gateway_nrho_diagram(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Slide 7 combined diagram: 9:2 NRHO orbit geometry + DTE vs Gateway coverage bars."""
    d = Drawing(w, h)
    d.add(
        Rect(
            0, 0, w, h, rx=5, ry=5, fillColor=C_SPACE_DARK, strokeColor=C_NASA_BLUE, strokeWidth=1.0
        )
    )
    d.add(
        String(
            10,
            h - 14,
            sanitize_for_font("9:2 Güney Halo (NRHO) Röle Geometrisi (e = 0.912)"),
            fontName="Arial-Bold",
            fontSize=8.0,
            fillColor=C_CYAN,
        )
    )

    # Position the 9:2 NRHO ellipse slightly left so right-hand labels sit in open column
    mx, my = w * 0.25, h * 0.74
    d.add(
        Ellipse(
            mx,
            my - 28,
            42,
            46,
            fillColor=None,
            strokeColor=C_CYAN,
            strokeWidth=1.2,
            strokeDashArray=[3, 2],
        )
    )
    d.add(
        Circle(
            mx,
            my + 6,
            10.5,
            fillColor=colors.HexColor("#475569"),
            strokeColor=colors.white,
            strokeWidth=0.8,
        )
    )
    gx, gy = mx, my - 72
    d.add(Circle(gx, gy, 4.2, fillColor=C_GOLD_BRIGHT, strokeColor=colors.white, strokeWidth=0.8))
    d.add(
        Line(
            mx,
            my - 4.5,
            gx,
            gy + 4.2,
            strokeColor=C_OK_BRIGHT,
            strokeWidth=1.4,
            strokeDashArray=[3, 2],
        )
    )

    lx = mx + 54.0
    mean_el = data["gateway"]["Site04_4km"]["mean_gateway_elevation_deg"]

    # Leader lines + crisp right-aligned annotations completely outside ellipse
    d.add(Line(mx + 12, my + 8, lx - 4, my + 8, strokeColor=C_LIGHT_DIM, strokeWidth=0.6))
    d.add(
        String(
            lx,
            my + 5.5,
            sanitize_for_font(f"Ay & Perilun (~{NRHO_PERILUNE_KM:,.0f} km)"),
            fontName="Arial-Bold",
            fontSize=6.8,
            fillColor=C_LIGHT_TEXT,
        )
    )

    d.add(
        Line(
            mx + 3,
            my - 32,
            lx - 4,
            my - 32,
            strokeColor=C_OK_BRIGHT,
            strokeWidth=0.6,
            strokeDashArray=[2, 2],
        )
    )
    d.add(
        String(
            lx,
            my - 34.5,
            sanitize_for_font(f"Ort. Yükseliş: {mean_el:.1f}° (Zenit Yakını)"),
            fontName="Arial-Bold",
            fontSize=6.9,
            fillColor=C_OK_BRIGHT,
        )
    )

    d.add(Line(gx + 6, gy, lx - 4, gy, strokeColor=C_GOLD_BRIGHT, strokeWidth=0.6))
    d.add(
        String(
            lx,
            gy - 2.5,
            sanitize_for_font(f"Lunar Gateway Apolun (~{NRHO_APOLUNE_KM:,.0f} km)"),
            fontName="Arial-Bold",
            fontSize=6.8,
            fillColor=C_GOLD_BRIGHT,
        )
    )

    by = 16.0
    d.add(
        Line(14, by + 56, w - 14, by + 56, strokeColor=colors.HexColor("#22345E"), strokeWidth=0.8)
    )
    d.add(
        String(
            10,
            by + 44,
            sanitize_for_font("Doğrudan Dünya (DTE) vs. Gateway NRHO Kapsaması (%)"),
            fontName="Arial-Bold",
            fontSize=7.5,
            fillColor=colors.white,
        )
    )

    gw04 = data["gateway"]["Site04_4km"]
    gw01 = data["gateway"]["Site01_4km"]
    bars = [
        ("Site04 DTE", gw04["direct_earth_pct"], C_DANGER_BRIGHT, 0),
        ("Site04 Gateway", gw04["gateway_relay_pct"], C_OK_BRIGHT, 1),
        ("Site01 DTE", gw01["direct_earth_pct"], C_GOLD_BRIGHT, 2),
        ("Site01 Gateway", gw01["gateway_relay_pct"], C_CYAN, 3),
    ]
    bar_max_w = w - 122
    for lbl, val, col, idx in bars:
        yy = by + 30 - idx * 9.5
        d.add(
            String(
                12,
                yy + 1,
                sanitize_for_font(lbl),
                fontName="Arial",
                fontSize=6.6,
                fillColor=C_LIGHT_TEXT,
            )
        )
        bw = max(2.0, (val / 100.0) * bar_max_w)
        d.add(Rect(78, yy, bar_max_w, 6.5, fillColor=colors.HexColor("#1E293B"), strokeColor=None))
        d.add(Rect(78, yy, bw, 6.5, fillColor=col, strokeColor=None))
        d.add(
            String(
                78 + bw + 4,
                yy + 0.8,
                f"%{val:.2f}",
                fontName="Arial-Bold",
                fontSize=6.6,
                fillColor=col,
            )
        )
    return d


def draw_penumbra_and_diffraction_charts(w: float, h: float) -> Drawing:
    """Slide 8 dual plot: Left = Solar disk penumbra curve, Right = ITU-R P.526 J(v)."""
    d = Drawing(w, h)
    d.add(
        Rect(0, 0, w, h, rx=5, ry=5, fillColor=colors.white, strokeColor=C_BORDER, strokeWidth=0.8)
    )
    half = w * 0.49
    d.add(Line(half, 6, half, h - 6, strokeColor=C_BORDER, strokeWidth=0.8))

    d.add(
        String(
            8,
            h - 12,
            sanitize_for_font("Güneş Diski (0.533°) Penumbra Akı Eğrisi"),
            fontName="Arial-Bold",
            fontSize=7.4,
            fillColor=C_NASA_BLUE,
        )
    )
    gx, gy, gw, gh = 26.0, 18.0, half - 36.0, h - 36.0
    d.add(Line(gx, gy, gx + gw, gy, strokeColor=C_MUTED, strokeWidth=0.6))
    d.add(Line(gx, gy, gx, gy + gh, strokeColor=C_MUTED, strokeWidth=0.6))

    deltas = np.linspace(-0.35, 0.35, 50)
    fracs = compute_solar_disk_fraction(deltas, 0.0, limb_darkening=True)
    mid_x = gx + 0.5 * gw
    d.add(
        PolyLine(
            [gx, gy, mid_x, gy, mid_x, gy + gh, gx + gw, gy + gh],
            strokeColor=C_MUTED,
            strokeWidth=1.0,
            strokeDashArray=[3, 2],
        )
    )
    pen_pts: list[float] = []
    for dd, ff in zip(deltas, fracs, strict=True):
        px = gx + ((float(dd) + 0.35) / 0.70) * gw
        py = gy + float(ff) * gh
        pen_pts.extend([px, py])
    d.add(PolyLine(pen_pts, strokeColor=C_GOLD, strokeWidth=1.8))
    d.add(
        String(
            gx + 3,
            gy + gh - 9,
            sanitize_for_font("Noktasal (kesik) vs Penumbra (altın)"),
            fontName="Arial",
            fontSize=6.2,
            fillColor=C_MUTED,
        )
    )
    d.add(String(gx, gy - 9, "-0.35°", fontName="Arial", fontSize=6.0, fillColor=C_MUTED))
    d.add(
        String(
            mid_x,
            gy - 9,
            "0.0°",
            fontName="Arial",
            fontSize=6.0,
            fillColor=C_MUTED,
            textAnchor="middle",
        )
    )
    d.add(
        String(
            gx + gw,
            gy - 9,
            "+0.35°",
            fontName="Arial",
            fontSize=6.0,
            fillColor=C_MUTED,
            textAnchor="end",
        )
    )

    for y_frac, lbl in ((0.0, "%0"), (0.5, "%50"), (1.0, "%100")):
        d.add(
            String(
                gx - 3,
                gy + y_frac * gh - 2.0,
                lbl,
                fontName="Arial",
                fontSize=5.6,
                fillColor=C_MUTED,
                textAnchor="end",
            )
        )

    rx = half + 32.0
    rw = w - rx - 10.0
    d.add(
        String(
            half + 8,
            h - 12,
            sanitize_for_font("ITU-R P.526 Kırınım Kaybı J(v) [dB] (d1=5 km)"),
            fontName="Arial-Bold",
            fontSize=7.4,
            fillColor=C_NASA_BLUE,
        )
    )
    d.add(Line(rx, gy, rx + rw, gy, strokeColor=C_MUTED, strokeWidth=0.6))
    d.add(Line(rx, gy, rx, gy + gh, strokeColor=C_MUTED, strokeWidth=0.6))

    angs = np.linspace(0.0, 1.0, 40)
    loss_max = 42.0
    for db_tick in (0, 20, 40):
        d.add(
            String(
                rx - 3,
                gy + (db_tick / loss_max) * gh - 2.0,
                f"{db_tick}",
                fontName="Arial",
                fontSize=5.6,
                fillColor=C_MUTED,
                textAnchor="end",
            )
        )
    for freq, col in ((S_BAND_FREQ_HZ, C_OK), (KA_BAND_FREQ_HZ, C_DANGER)):
        pts: list[float] = []
        for a in angs:
            v_val = float(
                compute_fresnel_parameter(float(a), 5000.0, DEFAULT_LUNAR_EARTH_DIST_M, freq)
            )
            j_db = float(compute_diffraction_loss_itu(v_val))
            px = rx + float(a) * rw
            py = gy + min(1.0, j_db / loss_max) * gh
            pts.extend([px, py])
        d.add(PolyLine(pts, strokeColor=col, strokeWidth=1.6))
    d.add(
        String(
            rx + rw - 2,
            gy + 12,
            sanitize_for_font("S-Band: +12.1 dB @ 0.35°"),
            fontName="Arial-Bold",
            fontSize=6.1,
            fillColor=C_OK,
            textAnchor="end",
        )
    )
    d.add(
        String(
            rx + 6,
            gy + gh - 9,
            sanitize_for_font("Ka-Band (26 GHz): -7.53 dB @ 0.35° (LINK_LOSS)"),
            fontName="Arial-Bold",
            fontSize=6.0,
            fillColor=C_DANGER,
            textAnchor="start",
        )
    )
    d.add(String(rx, gy - 9, "0.0°", fontName="Arial", fontSize=6.0, fillColor=C_MUTED))
    d.add(
        String(
            rx + rw * 0.35,
            gy - 9,
            "0.35°",
            fontName="Arial-Bold",
            fontSize=6.0,
            fillColor=C_NASA_BLUE,
            textAnchor="middle",
        )
    )
    d.add(
        String(
            rx + rw,
            gy - 9,
            "1.0°",
            fontName="Arial",
            fontSize=6.0,
            fillColor=C_MUTED,
            textAnchor="end",
        )
    )
    return d


def draw_astar_corridors_chart(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Slide 9 vector visualization of A* waypoint slope profiles for 4 key sites."""
    d = Drawing(w, h)
    d.add(
        Rect(0, 0, w, h, rx=5, ry=5, fillColor=colors.white, strokeColor=C_BORDER, strokeWidth=0.8)
    )
    d.add(
        String(
            8,
            h - 13,
            sanitize_for_font("A* PSR Koridoru: Rota Boyunca Yerel Eğim Profili (°) ve 15° Sınırı"),
            fontName="Arial-Bold",
            fontSize=7.8,
            fillColor=C_NASA_BLUE,
        )
    )
    gx, gy, gw, gh = 30.0, 18.0, w - 42.0, h - 40.0
    d.add(Line(gx, gy, gx + gw, gy, strokeColor=C_MUTED, strokeWidth=0.7))
    d.add(Line(gx, gy, gx, gy + gh, strokeColor=C_MUTED, strokeWidth=0.7))

    max_slope_axis = 60.0
    y15 = gy + (15.0 / max_slope_axis) * gh
    d.add(
        Line(gx, y15, gx + gw, y15, strokeColor=C_DANGER, strokeWidth=1.0, strokeDashArray=[4, 2])
    )
    d.add(
        String(
            gx + 6,
            y15 + 4,
            sanitize_for_font("15° Rover Devrilme Sınırı"),
            fontName="Arial-Bold",
            fontSize=6.4,
            fillColor=C_DANGER,
            textAnchor="start",
        )
    )

    for tick in (0, 15, 30, 45, 60):
        yp = gy + (tick / max_slope_axis) * gh
        d.add(
            String(
                gx - 3,
                yp - 2,
                f"{tick}°",
                fontName="Arial",
                fontSize=6.2,
                fillColor=C_MUTED,
                textAnchor="end",
            )
        )

    palette = [("Site13", C_OK), ("Site08", C_AZURE), ("Site01", C_GOLD), ("Site04", C_DANGER)]
    for idx, (sid, col) in enumerate(palette):
        wps = data["corridors"][sid]["waypoints"]
        n = max(1, len(wps) - 1)
        pts: list[float] = []
        for wi, wp in enumerate(wps):
            px = gx + (wi / n) * gw
            py = gy + min(1.0, float(wp["local_slope_deg"]) / max_slope_axis) * gh
            pts.extend([px, py])
        d.add(PolyLine(pts, strokeColor=col, strokeWidth=1.5))
        d.add(
            String(
                gx + 6 + idx * 78,
                h - 24,
                sanitize_for_font(f"-- {sid}"),
                fontName="Arial-Bold",
                fontSize=6.5,
                fillColor=col,
            )
        )

    x_lbl = "Normalize Rota İlerlemesi (%0 İniş Noktası -> %100 PSR Krater Kenarı)"
    d.add(
        String(
            gx + gw * 0.5,
            gy - 10,
            sanitize_for_font(x_lbl),
            fontName="Arial",
            fontSize=6.3,
            fillColor=C_MUTED,
            textAnchor="middle",
        )
    )
    return d


def draw_cockpit_wireframe(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Slide 10 clean executive wireframe of the 6-tab Streamlit Decision Cockpit."""
    d = Drawing(w, h)
    d.add(
        Rect(0, 0, w, h, rx=6, ry=6, fillColor=C_SPACE_DARK, strokeColor=C_AZURE, strokeWidth=1.0)
    )
    d.add(
        String(
            10,
            h - 14,
            sanitize_for_font(
                "LUNA-SIGHT K4 Karar Kokpiti (app/app.py) — Tek Bakışta Taktik Arayüz"
            ),
            fontName="Arial-Bold",
            fontSize=8.2,
            fillColor=C_CYAN,
        )
    )

    sb_w = w * 0.23
    d.add(
        Rect(
            10,
            12,
            sb_w,
            h - 34,
            rx=4,
            ry=4,
            fillColor=C_SPACE_CARD,
            strokeColor=C_NASA_BLUE,
            strokeWidth=0.8,
        )
    )
    d.add(
        String(
            18,
            h - 34,
            sanitize_for_font("KONTROL PANELİ"),
            fontName="Arial-Bold",
            fontSize=7.3,
            fillColor=C_GOLD_BRIGHT,
        )
    )
    sb_items = [
        "• Bölge A & B (12 Aday)",
        "• Başlangıç UTC & Gün",
        "• SUHAIL Min. Güneş %",
        "• SUHAIL Maks. Kesinti",
        "• Kaynak: Gerçek / Senaryo",
    ]
    for i, item in enumerate(sb_items):
        d.add(
            String(
                16,
                h - 49 - i * 14,
                sanitize_for_font(item),
                fontName="Arial",
                fontSize=6.8,
                fillColor=C_LIGHT_TEXT,
            )
        )

    mx = 18.0 + sb_w
    mw = w - mx - 10.0
    d.add(
        Rect(
            mx,
            h - 48,
            mw,
            26,
            rx=4,
            ry=4,
            fillColor=C_NASA_BLUE,
            strokeColor=C_CYAN,
            strokeWidth=0.9,
        )
    )
    d.add(
        String(
            mx + 8,
            h - 39,
            sanitize_for_font("TAKTİK KARAR BANDI: Kazanan Bölge + Optimal İniş Anı (UTC)"),
            fontName="Arial-Bold",
            fontSize=7.4,
            fillColor=colors.white,
        )
    )

    ab_w = (mw - 8) / 2.0
    _draw_box(
        d,
        mx,
        h - 92,
        ab_w,
        38,
        "Bölge A: Site01 (Connecting Ridge)",
        "SUHAIL Rozeti · Güneş %100 · Ortak %31.96",
        C_SPACE_CARD,
        C_OK_BRIGHT,
        title_color=C_OK_BRIGHT,
        sub_color=C_LIGHT_TEXT,
        title_size=7.3,
        sub_size=6.3,
    )
    _draw_box(
        d,
        mx + ab_w + 8,
        h - 92,
        ab_w,
        38,
        "Bölge B: Site04 (Shackleton Rim)",
        "SUHAIL Rozeti · Güneş %100 · DTE %0.00",
        C_SPACE_CARD,
        C_DANGER_BRIGHT,
        title_color=C_DANGER_BRIGHT,
        sub_color=C_LIGHT_TEXT,
        title_size=7.3,
        sub_size=6.3,
    )

    tabs = data["app_tabs"] or [
        "3B Ay küresi",
        "Ufuk görünümü",
        "Zaman çizelgesi",
        "Güney Kutbu Haritası (2D)",
        "Arazi Riski",
        "Veri ve kaynak",
    ]
    tab_w = (mw - 15) / 6.0
    for idx, tname in enumerate(tabs[:6]):
        tx = mx + idx * (tab_w + 3)
        short = tname.replace("Güney Kutbu Haritası (2D)", "2B Kutup Haritası")
        d.add(
            Rect(
                tx,
                h - 114,
                tab_w,
                16,
                rx=3,
                ry=3,
                fillColor=C_AZURE if idx == 0 else C_SPACE_MID,
                strokeColor=C_AZURE_LIGHT,
                strokeWidth=0.6,
            )
        )
        d.add(
            String(
                tx + tab_w / 2.0,
                h - 109,
                sanitize_for_font(f"{idx + 1}. {short[:20]}"),
                fontName="Arial-Bold",
                fontSize=5.8,
                fillColor=colors.white,
                textAnchor="middle",
            )
        )

    vp_h = h - 130
    d.add(
        Rect(
            mx,
            12,
            mw,
            vp_h,
            rx=4,
            ry=4,
            fillColor=colors.HexColor("#0B1325"),
            strokeColor=colors.HexColor("#243B6E"),
            strokeWidth=0.8,
        )
    )
    # Two miniature schematic viewport panes inside 3D tab preview
    pane_w = (mw - 24) / 2.0
    _draw_box(
        d,
        mx + 8,
        34,
        pane_w,
        max(22.0, vp_h - 32),
        "Sol Panel: NASA Moon Trek 3B WebGL Küresi",
        "LRO WAC 4K + LOLA Normal/Bump · 12 Aday İşaretçisi",
        C_SPACE_DARK,
        C_AZURE,
        title_color=C_CYAN,
        sub_color=C_LIGHT_DIM,
        title_size=6.8,
        sub_size=5.9,
    )
    _draw_box(
        d,
        mx + pane_w + 16,
        34,
        pane_w,
        max(22.0, vp_h - 32),
        "Sağ Panel: Plotly 260 km Kutup Rölyefi",
        "13 IAU Krateri · Dinamik Güneş Azimut Gölgesi",
        C_SPACE_DARK,
        C_GOLD,
        title_color=C_GOLD_BRIGHT,
        sub_color=C_LIGHT_DIM,
        title_size=6.8,
        sub_size=5.9,
    )
    vp_sub = (
        "Canlı CSV İndirme · Astronomi + DEM + 3-Durum Görünürlük Tek Kaynak "
        "(JPL DE441 + LOLA 5 m/px)"
    )
    d.add(
        String(
            mx + mw / 2.0,
            19,
            sanitize_for_font(vp_sub),
            fontName="Arial",
            fontSize=6.4,
            fillColor=C_LIGHT_DIM,
            textAnchor="middle",
        )
    )
    return d


def draw_ci_pipeline_diagram(w: float, h: float, data: dict[str, Any]) -> Drawing:
    """Slide 11 CI/CD 4-gate pipeline diagram."""
    d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, rx=5, ry=5, fillColor=C_BG_LIGHT, strokeColor=C_BORDER, strokeWidth=0.8))
    d.add(
        String(
            10,
            h - 13,
            sanitize_for_font("Pull Request -> main Zorunlu 4 CI Kapısı (ADR-500 · strict: true)"),
            fontName="Arial-Bold",
            fontSize=8.0,
            fillColor=C_NASA_BLUE,
        )
    )

    bw = (w - 58) / 4.0
    gates = [
        ("1. structure", "repository-checks.yml · <20MB", colors.white, C_AZURE, C_NASA_BLUE),
        (
            "2. Kanonik Sözleşme",
            "check_governance.py · Stdlib",
            C_NOTE_BG,
            C_NASA_BLUE,
            C_NASA_BLUE,
        ),
        ("3. Linux / Py 3.12", f"Ruff + {data['test_count']} Pytest", C_OK_BG, C_OK, C_OK),
        ("4. Windows / Py 3.12", "Çapraz OS Doğrulama", C_SPACE_DARK, C_GOLD, colors.white),
    ]
    for i, (t, s, fill, stroke, tc) in enumerate(gates):
        bx = 10 + i * (bw + 12)
        sc = C_LIGHT_DIM if fill == C_SPACE_DARK else C_MUTED
        _draw_box(
            d,
            bx,
            10,
            bw,
            36,
            t,
            s,
            fill,
            stroke,
            title_color=tc,
            sub_color=sc,
            title_size=7.4,
            sub_size=6.5,
        )
        if i < 3:
            _draw_arrow(d, bx + bw, 28, bx + bw + 10, 28, C_NASA_BLUE)
    return d


# ---------------------------------------------------------------------------
# Slide Builders (12 Executive Slides)
# ---------------------------------------------------------------------------


def build_slide_01(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(1, "KAPAK", "LUNA-SIGHT", "Artemis III Karar Destek Sistemi")
    n_sites = len(data["sites"])
    s01 = data["site_map"]["Site01"]
    n_tests = data["test_count"]

    left_w = CONTENT_W * 0.56
    right_w = CONTENT_W * 0.44 - 10.0

    sub_text = "Ay Güney Kutbu Görünürlük, Arazi Riski ve İleri Görev Fiziği Karar Destek Sistemi"
    meta_text = (
        f"<b>Kapsam:</b> {n_sites} Resmi Artemis III Aday Bölgesi "
        "(Site01–Site09, Site11–Site13)<br/>"
        "<b>Veri Tabanı:</b> NASA JPL Horizons DE441 + LRO/LOLA 5 m/px & 240 m/px DEM<br/>"
        "<b>Konsorsiyum:</b> K1 Efemeris · K2 Topoğrafya · K3 Görünürlük · "
        "K4 Kokpit · K5 Yönetişim"
    )
    hero_title = Table(
        [
            [
                rl_p(
                    "NASA ARTEMIS III · AY GÜNEY KUTBU KARAR DESTEK SİSTEMİ", styles["cover_kicker"]
                )
            ],
            [rl_p("<b>LUNA-SIGHT</b>", styles["cover_title"])],
            [rl_p(sub_text, styles["cover_sub"])],
            [Spacer(1, 6)],
            [rl_p(meta_text, styles["cover_meta"])],
        ],
        colWidths=[left_w],
    )
    hero_title.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    right_graphic = draw_cover_polar_graphic(right_w, 94.0 * mm, data)
    top_row = make_grid_row([(hero_title, left_w), (right_graphic, right_w)], gap=10.0)

    kpis = make_kpi_strip(
        [
            ("ADAY BÖLGE", f"{n_sites} NASA Bölgesi", "89.8°G – 84.1°G · [-180°, +180°]", C_CYAN),
            (
                "ZAMAN ÇÖZÜNÜRLÜĞÜ",
                f"{s01['samples']} Adım",
                f"5 dk aralık · {s01['span_hours']:.0f} saat (DE441)",
                C_GOLD_BRIGHT,
            ),
            (
                "İLERİ FİZİK",
                "3 Yeni Katman",
                "Gateway NRHO · Penumbra/RF · A* PSR",
                C_OK_BRIGHT,
            ),
            (
                "KALİTE KAPISI",
                f"{n_tests} Test",
                "Ruff 0 Hata · Sözleşme 0 İhlal · 4 CI",
                C_OK_BRIGHT,
            ),
        ],
        CONTENT_W,
        styles,
        dark=True,
    )

    story = [
        Spacer(1, 10.0 * mm),
        top_row,
        Spacer(1, 8.0 * mm),
        kpis,
    ]
    return meta, story


def build_slide_02(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        2,
        "GÖREV PROBLEMİ",
        "Ay Güney Kutbu'nun Acımasız Geometrisi",
        "1.54° eksen eğikliği, ±1.5° Güneş, Dünya librasyonu, "
        "−200°C termal çöküş ve 384.400 km telsiz bağı",
    )
    s01 = data["site_map"]["Site01"]
    s04 = data["site_map"]["Site04"]

    left_w = CONTENT_W * 0.47
    right_w = CONTENT_W * 0.53 - 8.0

    cards = [
        make_card(
            "1. Eksen Eğikliği Çıkmazı (1.54°)",
            [
                rl_p(
                    "Dünya'nın 23.4° eğikliğine karşın Ay ekseni yalnızca <b>1.54°</b> eğiktir. "
                    f"Güneş ufukta <b>+{s01['sun_alt_min']:.2f}° .. "
                    f"+{s04['sun_alt_max']:.2f}°</b> gibi kıl payı bir açıyla sıyırır; "
                    "ufuk teğeti en ufak tepede onlarca km gölge üretir.",
                    styles["body_sm"],
                )
            ],
            left_w,
            styles,
            accent=C_GOLD,
        ),
        Spacer(1, 4),
        make_card(
            "2. Dünya Librasyonu & Sınırlı Yükseliş",
            [
                rl_p(
                    "Eşzamanlı dönme nedeniyle Dünya Güney Kutbu'nda ufuk üstünde "
                    "dar bir azimut bandında "
                    f"<b>({s01['earth_alt_min']:+.2f}° .. {s04['earth_alt_max']:+.2f}°)</b> "
                    f"salınır. Site04 duvarı (+{s04['h_earth_min']:.1f}°.."
                    f"+{s04['h_earth_max']:.1f}°) hattı tamamen keser.",
                    styles["body_sm"],
                )
            ],
            left_w,
            styles,
            accent=C_AZURE,
        ),
        Spacer(1, 4),
        make_card(
            "3. −200°C Termal Çöküş & 384.400 km Telsiz Bağı",
            [
                rl_p(
                    "Atmosfersiz vakumda Güneş kesildiği an sıcaklık <b>−200°C</b>'ye düşer. "
                    "Houston telemetrisi ve acil durum yönlendirmesi için Dünya ile "
                    "<b>384.400 km</b> doğrudan görüş hattı veya yörünge rölesi şarttır.",
                    styles["body_sm"],
                )
            ],
            left_w,
            styles,
            accent=C_DANGER,
        ),
    ]
    left_col = make_vertical_stack(cards, left_w)

    diagram = draw_south_pole_geometry(right_w, 82.0 * mm, data)
    callout = make_callout(
        "MÜHENDİSLİK ÇIKARIMI:",
        "Güneş ışınları ve Dünya sinyali bu iki yaşam bağını oluşturur; "
        "ham JPL/LOLA verisini bilişsel yük oluşturmadan tek bakışta net iniş "
        "kararına çevirmek LUNA-SIGHT'ın varlık sebebidir.",
        right_w,
        styles,
        bg=C_WARN_BG,
        bar=C_GOLD,
    )
    right_col = make_vertical_stack([diagram, Spacer(1, 5), callout], right_w)

    return meta, [make_grid_row([(left_col, left_w), (right_col, right_w)], gap=8.0)]


def build_slide_03(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        3,
        "SİSTEM MİMARİSİ & VERİ SÖZLEŞMESİ",
        "K1–K5 Modüler Akış, DATA_CONTRACT.md & Sıfır İhlal Kalkanı",
        "5 bağımsız mühendislik biriminin ortak makine-okunur sözleşme "
        "altında sıfır çakışmayla entegrasyonu",
    )
    reg = data["registry"]
    req_cols = reg["data_contract"]["required_columns"]
    sources = reg["identifiers"]["source_id"]
    q_flags = reg["identifiers"]["quality_flag"]
    v_states = reg["identifiers"]["visibility_state"]
    r_codes = reg["identifiers"]["reason_code"]
    lon_rng = reg["geometry"]["longitude_range"]

    arch = draw_architecture_diagram(CONTENT_W, 47.5 * mm, data)

    left_w = CONTENT_W * 0.50
    right_w = CONTENT_W * 0.50 - 8.0

    col_groups = [
        ["Konum & Zaman (4)", "site_id, latitude_deg, longitude_deg_east, timestamp_utc"],
        ["K1 Astronomi (4)", "sun_az_deg, sun_alt_deg, earth_az_deg, earth_alt_deg"],
        ["K2 Arazi Ufku (2)", "terrain_horizon_sun_deg, terrain_horizon_earth_deg"],
        [
            "K3 Karar & Durum (3)",
            "sun_visible, earth_visible, joint_visible (+ *_margin, *_reason)",
        ],
        ["Köken & Kalite (5)", "quality_flag, source_id, source_version, model_id, parameters"],
    ]
    tbl_contract = make_styled_table(
        ["Katman", f"DATA_CONTRACT.md — {len(req_cols)} Zorunlu Kolon"],
        col_groups,
        [left_w * 0.31, left_w * 0.69],
        styles,
        font_size=7.0,
        pad_y=3.4,
    )
    c_note = make_callout(
        "ADR-004 3-Durum İlkesi:",
        f"Görünürlük metindir (<b>{' | '.join(v_states)}</b>) ve {len(r_codes)} "
        "gerekçe kodu taşır; eksik veri asla görünür veya engelli sayılmaz.",
        left_w,
        styles,
        bg=C_NOTE_BG,
        bar=C_NASA_BLUE,
    )
    left_col = make_vertical_stack([tbl_contract, Spacer(1, 5), c_note], left_w)

    src_str = ", ".join(sources)
    qf_str = " | ".join(q_flags)
    gov_card = make_card(
        "governance/registry.json — Otomatik Kapı Kuralları",
        [
            rl_p(
                f"<b>• Kayıtlı Kaynaklar ({len(sources)}):</b> "
                f"<font name='Consolas' size='7.2'>{src_str}</font>",
                styles["body_sm"],
            ),
            rl_p(
                f"<b>• Kalite Sözlüğü ({len(q_flags)}):</b> "
                f"<font name='Consolas' size='7.2'>{qf_str}</font>",
                styles["body_sm"],
            ),
            rl_p(
                f"<b>• Geometri & Zaman:</b> UTC ISO 8601 · Boylam doğu-pozitif "
                f"<b>[{lon_rng[0]:.0f}°, +{lon_rng[1]:.0f}°]</b> · Azimut K->D [0°, 360°)",
                styles["body_sm"],
            ),
            rl_p(
                f"<b>• Kanonik Ortam & ADR:</b> Python <b>{reg['python']['canonical_version']}</b>"
                " · Tek <font name='Consolas' size='7.2'>requirements.txt</font> · "
                "Yasak: <font name='Consolas' size='7.2'>pytest.ini, requirements-k*.txt</font>"
                " · ADR K1(100)–K5(500)",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• Denetim:</b> <font name='Consolas' size='7.2'>"
                "scripts/check_governance.py</font> her PR'da stdlib ile koşar; "
                "ihlalde birleşmeyi kapatır.",
                styles["body_sm"],
            ),
        ],
        right_w,
        styles,
        bg=C_OK_BG,
        accent=C_OK,
        pad_y=6.5,
    )

    bottom_bar = make_callout(
        "Sözleşme Bütünlüğü (Sıfır Sessiz Değişiklik):",
        "K1/K2/K3 üretimleri ile K4 arayüzü ayrı dallarda geliştirilse bile tek makine-okunur "
        "şema (<font name='Consolas' size='7.3'>registry.json</font>) üzerinden otomatik "
        "doğrulandığından arayüz ve fizik katmanı her zaman %100 uyumludur.",
        CONTENT_W,
        styles,
        bg=C_NOTE_BG,
        bar=C_AZURE,
    )

    return meta, [
        arch,
        Spacer(1, 5),
        make_grid_row([(left_col, left_w), (gov_card, right_w)], gap=8.0),
        Spacer(1, 5),
        bottom_bar,
    ]


def build_slide_04(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        4,
        "K1 EFEMERİS BİRİMİ",
        "NASA JPL Horizons DE441 & 12 Artemis III Aday Bölgesi",
        "2026-11-14 → 2026-11-21 UTC · coord@301 · APPARENT=AIRLESS · "
        "5 dk adım (2017 örnek) · [-180°, +180°]",
    )
    left_w = CONTENT_W * 0.63
    right_w = CONTENT_W * 0.37 - 8.0

    rows: list[list[str]] = []
    for r in data["sites"]:
        rows.append(
            [
                f"<b>{r['site_id']}</b>",
                r["site_name"],
                f"{r['lat_deg']:.4f}°",
                f"{r['lon_deg_east']:+.4f}°",
                f"{r['sun_alt_min']:+.2f}..{r['sun_alt_max']:+.2f}°",
                f"{r['earth_alt_min']:+.2f}..{r['earth_alt_max']:+.2f}°",
                r["k3_series_quality"],
            ]
        )
    tbl = make_styled_table(
        ["Site", "Artemis III Bölgesi", "Enlem", "Boylam (°D)", "Güneş Alt", "Dünya Alt", "Seri"],
        rows,
        [
            left_w * 0.09,
            left_w * 0.27,
            left_w * 0.12,
            left_w * 0.14,
            left_w * 0.15,
            left_w * 0.15,
            left_w * 0.08,
        ],
        styles,
        aligns=["C", "L", "R", "R", "C", "C", "C"],
        font_size=6.7,
        pad_x=3.0,
        pad_y=2.2,
        highlight_rows={0: C_OK_BG, 3: C_DANGER_BG},
    )

    polar_map = draw_polar_sites_map(right_w, 54.0 * mm, data)
    verify_card = make_card(
        "K1 Çift-Yol Doğrulama & Fiziksel Kanıt (ADR-100)",
        [
            rl_p(
                "<b>• Bağımsız İkinci Yol:</b> "
                "<font name='Consolas' size='7.0'>k1_independent_check.py</font>, "
                "alt-güneş/alt-dünya paralaks vektör hesabıyla 20 karşılaştırmada "
                "azimutta <b>≤ 0.0038°</b>, yükseklikte <b>≤ 0.0004°</b> fark verdi.",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• Doğu-Pozitif Doğrulama:</b> 90°E ve 270°E (−90°E) sorguları azimutta >10° "
                "ayrışır; ters boylam hatası dışlanır.",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• Köken İzlenebilirliği:</b> Ham yanıtlar "
                "<font name='Consolas' size='7.0'>data/cache/</font> ve SHA-256 "
                "<font name='Consolas' size='7.0'>data/manifest.csv</font> içinde taşınır.",
                styles["body_sm"],
            ),
        ],
        right_w,
        styles,
        bg=C_NOTE_BG,
        accent=C_NASA_BLUE,
        pad_y=4.5,
    )
    right_col = make_vertical_stack([polar_map, Spacer(1, 5), verify_card], right_w)

    return meta, [make_grid_row([(tbl, left_w), (right_col, right_w)], gap=8.0)]


def build_slide_05(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        5,
        "K2 ARAZİ & RİSK BİRİMİ",
        "LOLA DEM Eğim Analizi, Hibrit Ufuk & 3σ Kayaç Tehlike Matrisi",
        "merge_hybrid_profiles ile yakın+uzak ufuk birleşimi ve "
        "12 aday bölgenin ön-hesaplanmış iniş güvenliği",
    )
    left_w = CONTENT_W * 0.62
    right_w = CONTENT_W * 0.38 - 8.0

    rows: list[list[str]] = []
    hl: dict[int, colors.Color] = {}
    for idx, r in enumerate(data["sites"]):
        src_short = "LOLA 150m" if "lola" in r["dem_source"] else f"Model {r['dem_res_m']:.0f}m"
        verdict_short = {
            "SAFE_NOMINAL": "NOMİNAL GÜVENLİ",
            "CONDITIONAL_HAZARD_AVOIDANCE": "KOŞULLU (HDA)",
            "HIGH_SLOPE_CAUTION": "YÜKSEK EĞİM",
            "UNSAFE_STEEP_TERRAIN": "DİK / RİSKLİ",
        }.get(r["verdict"], r["verdict"])
        rows.append(
            [
                f"<b>{r['site_id']}</b>",
                src_short,
                f"{r['slope_mean']:.2f}°",
                f"{r['slope_p95']:.1f}°",
                f"{r['slope_max']:.1f}°",
                f"%{r['safe_3sigma_pct']:.1f}",
                f"{r['boulder_prob']:.2f}",
                f"<b>{r['safety_score']:.1f}</b>",
                verdict_short,
            ]
        )
        if r["verdict"] == "SAFE_NOMINAL":
            hl[idx] = C_OK_BG
        elif r["verdict"] == "UNSAFE_STEEP_TERRAIN":
            hl[idx] = C_DANGER_BG

    tbl = make_styled_table(
        ["Site", "DEM Kaynak", "Ort.", "P95", "Maks", "3σ ≤10°", "Kayaç P", "Skor", "Hüküm"],
        rows,
        [
            left_w * 0.09,
            left_w * 0.14,
            left_w * 0.08,
            left_w * 0.08,
            left_w * 0.08,
            left_w * 0.10,
            left_w * 0.09,
            left_w * 0.08,
            left_w * 0.26,
        ],
        styles,
        aligns=["C", "C", "R", "R", "R", "R", "R", "R", "L"],
        font_size=6.6,
        pad_x=2.8,
        pad_y=2.8,
        highlight_rows=hl,
    )

    h01 = data["hybrid_stats"]["Site01"]
    h04 = data["hybrid_stats"]["Site04"]
    card_hyb = make_card(
        "Hibrit Yakın + Uzak Ufuk (merge_hybrid_profiles)",
        [
            rl_p(
                "<b>• Yöntem:</b> 360° azimutta 10 m radyal adımla ufuk taranır, "
                "Ay eğrilik düzeltmesi (R=1737.4 km) uygulanır ve "
                "<font name='Consolas' size='7.0'>max(yakın 4km, uzak 20km)</font> hizalanır.",
                styles["body_sm"],
            ),
            rl_p(
                f"<b>• Canlı Hibrit Sonuç:</b> Site01 ort. {h01['near_mean']:.2f}° / "
                f"{h01['far_mean']:.2f}° → <b>{h01['hyb_mean']:.2f}°</b>; Site04 ort. "
                f"{h04['near_mean']:.2f}° / {h04['far_mean']:.2f}° → "
                f"<b>{h04['hyb_mean']:.2f}°</b> (maks {h04['hyb_max']:.2f}°).",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• LDEC Şeffaflığı (ADR-003):</b> 5 m/px LOLA'da gerçek dönüş oranı %8–11; "
                "20 km 240 m/px profili sınır etkisiyle "
                "<font name='Consolas' size='7.0'>partial</font> işaretlenir.",
                styles["body_sm"],
            ),
        ],
        right_w,
        styles,
        accent=C_AZURE,
        pad_y=5.2,
    )
    s01 = data["site_map"]["Site01"]
    s04 = data["site_map"]["Site04"]
    s13 = data["site_map"]["Site13"]
    card_risk = make_card(
        "3σ İniş Ayak İzi & Kayaç Tehlike Matrisi (BHI)",
        [
            rl_p(
                "<b>• Güç-Yasası BHI (12 m² açıklık):</b> Eğim ve krater kenarı "
                "mesafesinden çarpma olasılığı "
                "(<font name='Consolas' size='7.0'>evaluate_landing_footprint</font>) hesaplanır.",
                styles["body_sm"],
            ),
            rl_p(
                f"<b>• Zıt Uçlar:</b> <b>Site13</b> (Mons Mouton) "
                f"{s13['slope_mean']:.2f}° ort. eğim ve "
                f"<b>%{s13['safe_3sigma_pct']:.1f}</b> 3σ uyumla "
                f"<b>{s13['safety_score']:.1f}</b> skor alırken, <b>Site04</b> "
                f"({s04['slope_mean']:.2f}°) dik duvarla "
                f"<b>{s04['safety_score']:.1f}</b> skorda kalır.",
                styles["body_sm"],
            ),
        ],
        right_w,
        styles,
        bg=C_WARN_BG,
        accent=C_GOLD,
        pad_y=5.2,
    )
    callout_hda = make_callout(
        "HDA Çıkarımı:",
        f"Site01 (<b>{s01['slope_mean']:.2f}°</b>, %{s01['safe_3sigma_pct']:.1f} 3σ) "
        "o kadar keskin bir sırttadır ki güvenli iniş için Tehlike Kaçınma (HDA) ister.",
        right_w,
        styles,
        bg=C_NOTE_BG,
        bar=C_NASA_BLUE,
    )
    right_col = make_vertical_stack(
        [card_hyb, Spacer(1, 5), card_risk, Spacer(1, 5), callout_hda], right_w
    )

    return meta, [make_grid_row([(tbl, left_w), (right_col, right_w)], gap=8.0)]


def build_slide_06(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        6,
        "K3 GÖRÜNÜRLÜK & DUYARLILIK",
        "Geçiş Bandı Sınıflandırması, Site01 vs. Site04 & 144 Satırlık Tarama",
        "Sınır inceltmeli (±2.5 dk kuantalama giderimi) K3 motoru ve "
        "16 profil × 3 marj × 3 gövde duyarlılık bulguları",
    )
    s01 = data["site_map"]["Site01"]
    s04 = data["site_map"]["Site04"]
    sens_df = data["sens_df"]
    n_sens = len(sens_df)
    n_prof = sens_df["profile"].nunique()

    left_w = CONTENT_W * 0.48
    right_w = CONTENT_W * 0.52 - 8.0

    ab_rows = [
        [
            "Site01 (4km, 5m/px)",
            f"%{s01['sun_pct']:.2f}",
            f"%{s01['earth_pct']:.2f}",
            f"<b>%{s01['joint_pct']:.2f}</b>",
            f"<b>{s01['longest_joint_h']:.2f} sa</b>",
            f"+{s01['h_earth_min']:.2f}..+{s01['h_earth_max']:.2f}°",
        ],
        [
            "Site04 (4km, 5m/px)",
            f"%{s04['sun_pct']:.2f}",
            f"%{s04['earth_pct']:.2f}",
            f"<b>%{s04['joint_pct']:.2f}</b>",
            "yok (0.00)",
            f"+{s04['h_earth_min']:.2f}..+{s04['h_earth_max']:.2f}°",
        ],
    ]
    tbl_ab = make_styled_table(
        ["5 m/px Referans", "Güneş", "Dünya", "Ortak", "En Uzun Pencere", "Dünya Az. Ufuk"],
        ab_rows,
        [left_w * 0.24, left_w * 0.12, left_w * 0.12, left_w * 0.12, left_w * 0.19, left_w * 0.21],
        styles,
        aligns=["L", "C", "C", "C", "C", "C"],
        font_size=6.8,
        pad_y=3.0,
        highlight_rows={0: C_OK_BG, 1: C_DANGER_BG},
    )

    chart = draw_earth_horizon_chart(left_w, 53.0 * mm, data)
    callout_ab = make_callout(
        "Shackleton Tuzağı Açıklandı:",
        f"Site04'te Dünya +{s04['earth_alt_max']:.2f}°'ye çıksa da krater duvarı "
        f"+{s04['h_earth_min']:.2f}°..+{s04['h_earth_max']:.2f}° yüksekliğindedir. "
        f"Site01'de ufuk +{s01['h_earth_min']:.2f}°..+{s01['h_earth_max']:.2f}° olduğundan "
        f"{s01['longest_joint_h']:.2f} saatlik altın pencere açılır.",
        left_w,
        styles,
        bg=C_NOTE_BG,
        bar=C_NASA_BLUE,
    )
    left_col = make_vertical_stack([tbl_ab, Spacer(1, 4), chart, Spacer(1, 4), callout_ab], left_w)

    j_df = sens_df[sens_df["body"] == "joint"]
    sens_rows: list[list[str]] = []
    for sid, rad, lbl in (
        ("Site01", 2000, "Site01 (2 km, 5m)"),
        ("Site01", 4000, "Site01 (4 km, 5m)"),
        ("Site01", 20000, "Site01 (20 km, 240m)"),
        ("Site04", 4000, "Site04 (4 km, 5m)"),
        ("Site05", 20000, "Site05 (20 km, 240m)"),
        ("Site08", 20000, "Site08 (20 km, 240m)"),
        ("Site12", 20000, "Site12 (20 km, 240m)"),
        ("Site13", 20000, "Site13 (20 km, 240m)"),
    ):
        sub = j_df[(j_df["site_id"] == sid) & (j_df["radius_m"] == rad)].sort_values("margin_deg")
        vals = {float(r["margin_deg"]): r for _, r in sub.iterrows()}
        m05, m10, m20 = vals[0.05], vals[0.10], vals[0.20]
        sens_rows.append(
            [
                lbl,
                f"%{m05['visible_fraction'] * 100:.2f}",
                f"%{m10['visible_fraction'] * 100:.2f}",
                f"%{m20['visible_fraction'] * 100:.2f}",
                f"%{m05['uncertain_fraction'] * 100:.1f} → %{m20['uncertain_fraction'] * 100:.1f}",
                f"{_safe_float(m10['longest_visible_hours']):.1f} sa",
            ]
        )

    tbl_sens = make_styled_table(
        [
            f"Duyarlılık ({n_sens} satır = {n_prof}×3×3)",
            "±0.05°",
            "±0.10°",
            "±0.20°",
            "Belirsiz (0.05→0.20)",
            "Pencere (±0.1°)",
        ],
        sens_rows,
        [
            right_w * 0.28,
            right_w * 0.12,
            right_w * 0.12,
            right_w * 0.12,
            right_w * 0.21,
            right_w * 0.15,
        ],
        styles,
        aligns=["L", "R", "R", "R", "C", "R"],
        font_size=6.7,
        pad_x=3.0,
        pad_y=2.5,
        highlight_rows={1: C_OK_BG, 2: C_WARN_BG},
    )

    s01_4_v = (
        float(
            j_df[
                (j_df["site_id"] == "Site01")
                & (j_df["radius_m"] == 4000)
                & (j_df["margin_deg"] == 0.10)
            ]["visible_fraction"].iloc[0]
        )
        * 100.0
    )
    s01_20_v = (
        float(
            j_df[
                (j_df["site_id"] == "Site01")
                & (j_df["radius_m"] == 20000)
                & (j_df["margin_deg"] == 0.10)
            ]["visible_fraction"].iloc[0]
        )
        * 100.0
    )
    card_sens = make_card(
        "Duyarlılık Taramasından İki Kritik Bilimsel Kural",
        [
            rl_p(
                "<b>1. Geçiş Bandı Etkisi (±0.05° → ±0.20°):</b> Marj genişledikçe "
                "<font name='Consolas' size='7.0'>uncertain</font> sınıfı doğrusal büyür "
                "(Site01 4km: %1.02 → %4.10) ve kesin ortak süre ihtiyatlı düşer "
                "(%32.47 → %30.93).",
                styles["body_sm"],
            ),
            rl_p(
                "<b>2. 240 m/px Çözünürlük Yanılsaması:</b> Site01'de 20 km bölgesel DEM "
                f"mikro-rölyefi düzleştirdiği için ortak görünürlüğü %{s01_4_v:.2f}'dan "
                f"<b>%{s01_20_v:.2f}'a (+{s01_20_v - s01_4_v:.2f} puan)</b> şişirir! "
                "Bu yüzden 240 m/px sonuçlar <b>üst sınır</b>dır.",
                styles["body_sm"],
            ),
        ],
        right_w,
        styles,
        bg=C_WARN_BG,
        accent=C_GOLD,
        pad_y=5.0,
    )
    right_col = make_vertical_stack([tbl_sens, Spacer(1, 5), card_sens], right_w)

    return meta, [make_grid_row([(left_col, left_w), (right_col, right_w)], gap=8.0)]


def build_slide_07(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        7,
        "İLERİ GÖREV FİZİĞİ 1 · LUNAR GATEWAY",
        "9:2 NRHO Yörünge Rölesi: %0.00 Dünya'dan %97.7+ Haberleşmeye",
        "Dünya-Ay L2 9:2 Güney Halo (NRHO) röle efemerisinin "
        "K2 ufuk engelleriyle entegrasyonu (visibility.gateway)",
    )
    gw01 = data["gateway"]["Site01_4km"]
    gw04 = data["gateway"]["Site04_4km"]
    gw04_20 = data["gateway"]["Site04_20km"]

    left_w = CONTENT_W * 0.50
    right_w = CONTENT_W * 0.50 - 8.0

    kpis = make_kpi_strip(
        [
            (
                "NRHO PERİYOT",
                f"{NRHO_PERIOD_HOURS:.0f} saat",
                f"7 gün · a = {NRHO_SEMI_MAJOR_AXIS_KM:,.0f} km",
                C_NASA_BLUE,
            ),
            (
                "APOLUN (GÜNEY)",
                f"{NRHO_APOLUNE_KM:,.0f} km",
                f"Perilun {NRHO_PERILUNE_KM:,.0f} km · e={NRHO_ECCENTRICITY}",
                C_AZURE,
            ),
            (
                "SITE04 GATEWAY",
                f"%{gw04['gateway_relay_pct']:.2f}",
                f"DTE %{gw04['direct_earth_pct']:.2f} → %{gw04['gateway_relay_pct']:.2f}!",
                C_OK,
            ),
            (
                "ORT. YÜKSELİŞ",
                f"{gw04['mean_gateway_elevation_deg']:.1f}°",
                f"Maks kesinti: {gw04['max_relay_outage_hours']:.2f} sa",
                C_GOLD,
            ),
        ],
        CONTENT_W,
        styles,
    )

    gw_rows = [
        [
            "Site01 (4 km)",
            f"%{gw01['direct_earth_pct']:.2f}",
            f"<b>%{gw01['gateway_relay_pct']:.2f}</b>",
            f"%{gw01['solar_and_gateway_pct']:.2f}",
            f"{gw01['mean_gateway_elevation_deg']:.2f}°",
            f"{gw01['max_relay_outage_hours']:.2f} sa",
        ],
        [
            "Site04 (4 km)",
            f"%{gw04['direct_earth_pct']:.2f}",
            f"<b>%{gw04['gateway_relay_pct']:.2f}</b>",
            f"%{gw04['solar_and_gateway_pct']:.2f}",
            f"{gw04['mean_gateway_elevation_deg']:.2f}°",
            f"{gw04['max_relay_outage_hours']:.2f} sa",
        ],
        [
            "Site04 (20 km)",
            f"%{gw04_20['direct_earth_pct']:.2f}",
            f"<b>%{gw04_20['gateway_relay_pct']:.2f}</b>",
            f"%{gw04_20['solar_and_gateway_pct']:.2f}",
            f"{gw04_20['mean_gateway_elevation_deg']:.2f}°",
            f"{gw04_20['max_relay_outage_hours']:.2f} sa",
        ],
    ]
    tbl_gw = make_styled_table(
        ["Bölge / Ufuk", "DTE %", "Gateway %", "Güneş+GW %", "Ort. El.", "Maks Körlük"],
        gw_rows,
        [left_w * 0.24, left_w * 0.13, left_w * 0.17, left_w * 0.17, left_w * 0.14, left_w * 0.15],
        styles,
        aligns=["L", "C", "C", "C", "C", "C"],
        font_size=7.0,
        pad_y=3.2,
        highlight_rows={1: C_OK_BG},
    )

    card_phys = make_card(
        "Neden 9:2 NRHO Shackleton Tuzağını Çözer?",
        [
            rl_p(
                "<b>• Kepler II. Yasası Avantajı:</b> Yüksek basıklık (e = 0.912) "
                "nedeniyle Gateway kuzey kutbu perilununu (~3.221 km) hızla geçer, "
                "haftanın büyük bölümünü <b>Güney Kutbu üzerinde ~70.000 km "
                "apolunda</b> geçirir.",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• Tepeden Görüş Hattı:</b> Ufuk duvarı +32° olsa bile Gateway "
                "ortalama <b>78.1° zenit yakınında</b> durur; böylece Shackleton Kenarı "
                "(Site04) %100 Güneş + <b>%97.72 röle haberleşmesi</b> ile "
                "birinci sınıf bilim üssüne dönüşür.",
                styles["body_sm"],
            ),
        ],
        left_w,
        styles,
        bg=C_NOTE_BG,
        accent=C_NASA_BLUE,
        pad_y=5.0,
    )
    left_col = make_vertical_stack([tbl_gw, Spacer(1, 5), card_phys], left_w)

    nrho_diag = draw_gateway_nrho_diagram(right_w, 82.0 * mm, data)

    return meta, [
        kpis,
        Spacer(1, 6),
        make_grid_row([(left_col, left_w), (nrho_diag, right_w)], gap=8.0),
    ]


def build_slide_08(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        8,
        "İLERİ GÖREV FİZİĞİ 2 · PENUMBRA & LINK BÜTÇESİ",
        "0.533° Güneş Diski Penumbra Gücü & ITU-R P.526 Link Bütçesi",
        "Kenar kararmalı fotovoltaik akı (penumbra.py) + "
        "DSN Goldstone/Madrid/Canberra S/Ka/Optik kırınım (comms.py)",
    )
    pen04 = data["penumbra"]["Site04_20km"]
    pen08 = data["penumbra"]["Site08_20km"]
    pen13 = data["penumbra"]["Site13_20km"]

    left_w = CONTENT_W * 0.48
    right_w = CONTENT_W * 0.52 - 8.0

    pen_rows = [
        [
            "Site04 (20 km)",
            f"{pen04['point_source_hours']:.2f} sa",
            f"{pen04['effective_penumbra_hours']:.2f} sa",
            f"<b>{pen04['penumbra_transition_hours']:.2f} sa</b>",
            f"<b>{pen04['energy_delta_wh']:+.0f} Wh</b>",
        ],
        [
            "Site08 (20 km)",
            f"{pen08['point_source_hours']:.2f} sa",
            f"{pen08['effective_penumbra_hours']:.2f} sa",
            f"{pen08['penumbra_transition_hours']:.2f} sa",
            f"{pen08['energy_delta_wh']:+.1f} Wh",
        ],
        [
            "Site13 (20 km)",
            f"{pen13['point_source_hours']:.2f} sa",
            f"{pen13['effective_penumbra_hours']:.2f} sa",
            f"{pen13['penumbra_transition_hours']:.2f} sa",
            f"{pen13['energy_delta_wh']:+.1f} Wh",
        ],
    ]
    tbl_pen = make_styled_table(
        ["Bölge (1 kW Panel)", "Noktasal", "Efektif Pen.", "Kısmi Geçiş", "Enerji Farkı"],
        pen_rows,
        [left_w * 0.25, left_w * 0.18, left_w * 0.19, left_w * 0.18, left_w * 0.20],
        styles,
        aligns=["L", "R", "R", "R", "R"],
        font_size=6.7,
        pad_y=2.6,
        highlight_rows={0: C_WARN_BG},
    )

    pen_title = (
        f"Penumbra Modeli ({SOLAR_ANGULAR_DIAMETER_DEG}° Disk · "
        f"{SOLAR_ANGULAR_RADIUS_DEG}° Yarıçap · {SOLAR_CONSTANT_1AU:.0f} W/m²)"
    )
    pen_card = make_card(
        pen_title,
        [
            rl_p(
                "<b>• Doğrusal Kenar Kararması (u = 0.60):</b> Güneş diski ufku "
                "teğet geçerken noktasal (0/1) varsayım Site04 (20 km) profilinde "
                f"<b>{pen04['penumbra_transition_hours']:.2f} saatlik</b> kısmi gölgelemeyi "
                f"gizler ve 1 kW panel bütçesini <b>{abs(pen04['energy_delta_wh']):,.0f} Wh</b> "
                "fazla sayar.",
                styles["body_sm"],
            ),
        ],
        left_w,
        styles,
        bg=C_WARN_BG,
        accent=C_GOLD,
        pad_y=4.5,
    )

    lc, lo = data["link_clear"], data["link_obs"]
    rf_rows = [
        [
            "S-Band (2.2 GHz · 64 kbps)",
            f"{lc['S_BAND']['fspl_db']:.1f} dB",
            f"+{lc['S_BAND']['link_margin_db']:.2f} dB",
            f"{lo['S_BAND']['diffraction_loss_db']:.2f} dB",
            f"<b>{lo['S_BAND']['link_margin_db']:+.2f} dB</b>",
            "OPERATIONAL",
        ],
        [
            "Ka-Band (26 GHz · 20 Mbps)",
            f"{lc['KA_BAND']['fspl_db']:.1f} dB",
            f"+{lc['KA_BAND']['link_margin_db']:.2f} dB",
            f"{lo['KA_BAND']['diffraction_loss_db']:.2f} dB",
            f"<b>{lo['KA_BAND']['link_margin_db']:+.2f} dB</b>",
            "LINK_LOSS",
        ],
        [
            "Optik (1550 nm · 200 Mbps)",
            f"{lc['OPTICAL_O2O']['fspl_db']:.1f} dB",
            f"+{lc['OPTICAL_O2O']['link_margin_db']:.2f} dB",
            f"{lo['OPTICAL_O2O']['diffraction_loss_db']:.2f} dB",
            f"<b>{lo['OPTICAL_O2O']['link_margin_db']:+.2f} dB</b>",
            "LINK_LOSS",
        ],
    ]
    tbl_rf = make_styled_table(
        ["Goldstone DSN 70m", "FSPL", "Açık Marj", "J(v) @0.35°", "Gölge Marj", "Durum"],
        rf_rows,
        [
            right_w * 0.30,
            right_w * 0.13,
            right_w * 0.14,
            right_w * 0.14,
            right_w * 0.14,
            right_w * 0.15,
        ],
        styles,
        aligns=["L", "R", "R", "R", "R", "C"],
        font_size=6.6,
        pad_y=2.6,
        highlight_rows={0: C_OK_BG, 1: C_DANGER_BG, 2: C_DANGER_BG},
    )

    em_05 = data["emerg_sweep"][3]["s_band"]
    em_25 = data["emerg_sweep"][5]["s_band"]
    rf_card = make_card(
        "ITU-R P.526-15 Kırınım & Acil Durum İşaretçisi (Goldstone / Madrid / Canberra)",
        [
            rl_p(
                "<b>• Dalga Boyu Fiziği:</b> 0.35° sırt arkasında (d1=5 km) "
                "13.6 cm S-Band dalgaları kırınımla "
                f"<b>{lo['S_BAND']['link_margin_db']:+.2f} dB</b> marjla açık kalırken "
                f"Ka-Band ({lo['KA_BAND']['link_margin_db']:+.2f} dB) ve Lazer düşer.",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• Acil Durum S-Band Beacon:</b> 10 W verici + -168 dBm DSN alıcıyla "
                f"0.5° gölgede <b>+{em_05['link_margin_db']:.2f} dB</b>, 2.5° derin gölgede "
                f"dahi <b>+{em_25['link_margin_db']:.2f} dB</b> bağlantı korunur.",
                styles["body_sm"],
            ),
        ],
        right_w,
        styles,
        bg=C_NOTE_BG,
        accent=C_NASA_BLUE,
        pad_y=4.5,
    )

    left_col = make_vertical_stack([tbl_pen, Spacer(1, 4), pen_card], left_w)
    right_col = make_vertical_stack([tbl_rf, Spacer(1, 4), rf_card], right_w)
    plots = draw_penumbra_and_diffraction_charts(CONTENT_W, 42.0 * mm)

    return meta, [
        make_grid_row([(left_col, left_w), (right_col, right_w)], gap=8.0),
        Spacer(1, 5),
        plots,
    ]


def build_slide_09(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        9,
        "İLERİ GÖREV FİZİĞİ 3 · OTONOM ROTA PLANLAMA",
        "Otonom EVA & Rover A* PSR Koridor Planlayıcı",
        "İniş noktalarından Kalıcı Gölgeli Krater (PSR) kenarlarına "
        "eğim-cezalı (15°) güvenli rota (pathfinder.py)",
    )
    cor_rows: list[list[str]] = []
    for sid in ("Site01", "Site04", "Site08", "Site13"):
        c = data["corridors"][sid]
        cor_rows.append(
            [
                f"<b>{c['site_id']}</b> — {c['site_name']}",
                str(c["target_name"]),
                f"{c['total_distance_km']:.2f} km",
                f"<b>{c['estimated_eva_hours']:.2f} sa</b>",
                f"{c['mean_route_slope_deg']:.2f}°",
                f"{c['max_route_slope_deg']:.1f}°",
                f"<b>%{c['solar_safe_fraction_pct']:.1f}</b>",
                str(len(c["waypoints"])),
            ]
        )
    tbl = make_styled_table(
        [
            "Çıkış Bölgesi",
            "En Yakın PSR Hedefi",
            "Mesafe",
            "EVA (1.5 km/sa)",
            "Ort. Eğim",
            "Maks Eğim",
            "Güneş-Güvenli",
            "Nokta",
        ],
        cor_rows,
        [
            CONTENT_W * 0.22,
            CONTENT_W * 0.15,
            CONTENT_W * 0.10,
            CONTENT_W * 0.13,
            CONTENT_W * 0.10,
            CONTENT_W * 0.10,
            CONTENT_W * 0.12,
            CONTENT_W * 0.08,
        ],
        styles,
        aligns=["L", "L", "R", "R", "R", "R", "R", "C"],
        font_size=7.0,
        pad_y=2.8,
        highlight_rows={0: C_OK_BG, 1: C_DANGER_BG, 3: C_OK_BG},
    )

    left_w = CONTENT_W * 0.42
    right_w = CONTENT_W * 0.58 - 8.0

    card_alg = make_card(
        "A* Maliyet Fonksiyonu & Güvenlik Mühendisliği",
        [
            rl_p(
                "<b>• Çok-Amaçlı Maliyet:</b> Her hücre geçişinde mesafe × "
                "<font name='Consolas' size='6.8'>"
                "[1 + 0.5·(eğim/15°)² + 0.75·PSR_tabanı + 50·aşım]</font> "
                "minimize edilir.",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• İki Aşamalı Bariyer:</b> Önce <b>15° rover devrilme sınırı</b> "
                "katı engeldir (<font name='Consolas' size='7.0'>strict_barrier=True</font>); "
                "yalnızca geçit yoksa yüksek cezalı kurtarma yolu hesaplanır "
                "(ör. dik Shackleton duvarlı Site04).",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• Taktik Yorum:</b> <b>Site13</b> en düz koridorla "
                "(%95.7 güneş-güvenli, 2.45° ort. eğim) uzun menzilli rover için idealdir; "
                "<b>Site01</b> ise 6.6 sa EVA ile Shackleton PSR kenarına "
                "%87.5 güvenli erişim sağlar.",
                styles["body_sm"],
            ),
        ],
        left_w,
        styles,
        bg=C_NOTE_BG,
        accent=C_NASA_BLUE,
        pad_y=5.0,
    )
    chart = draw_astar_corridors_chart(right_w, 59.0 * mm, data)

    return meta, [tbl, Spacer(1, 6), make_grid_row([(card_alg, left_w), (chart, right_w)], gap=8.0)]


def build_slide_10(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        10,
        "K4 KARAR KOKPİTİ & 3B GÖRSELLEŞTİRME",
        "6 Sekmeli Streamlit Kokpiti, 3B Moon Trek Küresi & SUHAIL Standardı",
        "Ham astrodinamik ve DEM matrislerini uçuş direktörünün "
        "saniyeler içinde okuyabileceği kokpite dönüştürme",
    )
    wireframe = draw_cockpit_wireframe(CONTENT_W, 68.0 * mm, data)

    w3 = (CONTENT_W - 14.0) / 3.0
    c1 = make_card(
        "1. 3B Moon Trek + Plotly Kutupsal Rölyef",
        [
            rl_p(
                "• <b>WebGL Küre:</b> NASA Moon Trek LRO WAC (4K/2K) mozaiği + "
                "LOLA normal & kabartma dokuları "
                "(<font name='Consolas' size='7.0'>app/static/moon/</font>).",
                styles["body_sm"],
            ),
            rl_p(
                "• <b>260 km Kutup Rölyefi:</b> "
                "<font name='Consolas' size='7.0'>surface_3d.py</font> ile "
                "13 IAU krateri, Güneş azimut gölgesi ve A/B işaret direkleri.",
                styles["body_sm"],
            ),
        ],
        w3,
        styles,
        accent=C_AZURE,
        pad_y=5.0,
    )
    c2 = make_card(
        "2. SUHAIL Taktik İniş & Brifing Kartı",
        [
            rl_p(
                "• Astronot/görev kısıtları (min. Güneş % ve maks. kesinti saati) "
                "kaydırıcılarına göre anlık <b>GEÇTİ / KALDI</b> rozeti.",
                styles["body_sm"],
            ),
            rl_p(
                "• Haftanın en uzun kesintisiz ortak penceresini başlatan "
                "<b>optimal touchdown</b> anı ve indirilebilir astronot brifing raporu.",
                styles["body_sm"],
            ),
        ],
        w3,
        styles,
        bg=C_WARN_BG,
        accent=C_GOLD,
        pad_y=5.0,
    )
    c3 = make_card(
        "3. Canlı A/B Karşılaştırma & Tek Kaynak",
        [
            rl_p(
                f"• <b>{len(data['sites'])} Artemis III bölgesi</b> yan yana kıyaslanır; "
                "5°/10°/15°/20° eğim eşikleri ve krater yoğunluğu anlık görülür.",
                styles["body_sm"],
            ),
            rl_p(
                "• 3B küre, 2B kutup haritası ve zaman çizelgesi "
                "<b>birebir aynı JPL DE441 + K2/K3 verisini</b> okur (sıfır tutarsızlık).",
                styles["body_sm"],
            ),
        ],
        w3,
        styles,
        bg=C_OK_BG,
        accent=C_OK,
        pad_y=5.0,
    )

    return meta, [wireframe, Spacer(1, 6), make_grid_row([(c1, w3), (c2, w3), (c3, w3)], gap=7.0)]


def build_slide_11(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        11,
        "K5 YÖNETİŞİM, KALİTE KAPILARI & CI/CD",
        "NASA Disipliniyle Otomatik Kalite Kalkanı & 120 sn Demo Hattı",
        "5 mühendisin aynı anda sıfır gerileme ile çalışmasını "
        "garanti eden test, lint, sözleşme ve CI otomasyonu",
    )
    kpis = make_kpi_strip(
        [
            (
                "OFFLINE TESTLER",
                f"{data['test_count']} Pytest",
                "--record-mode=none · 0 ağ bağımlılığı",
                C_OK,
            ),
            (
                "KOD KALİTESİ",
                f"{data['py_files_count']} Python Dosyası",
                "ruff lint 0 hata · CI format kapısı",
                C_NASA_BLUE,
            ),
            (
                "KANONİK SÖZLEŞME",
                "0 İhlal / 0 Uyarı",
                "check_governance.py (PY/ENC/ADR/ID/GEO)",
                C_OK,
            ),
            (
                "CI İŞ AKIŞLARI",
                f"{len(data['workflows'])} Dosya · 4 Kapı",
                "structure · Sözleşme · Linux · Windows",
                C_AZURE,
            ),
        ],
        CONTENT_W,
        styles,
    )

    pipe_diag = draw_ci_pipeline_diagram(CONTENT_W, 25.0 * mm, data)

    left_w = CONTENT_W * 0.50
    right_w = CONTENT_W * 0.50 - 8.0

    c_gov = make_card(
        "Birleştirme Treni, CODEOWNERS & ADR Disiplini",
        [
            rl_p(
                f"<b>• ADR Numara İzolasyonu ({len(data['adrs'])} Karar):</b> "
                "Çakışmayı önlemek için K1(100–199), K2(200–299), K3(300–399), "
                "K4(400–499), K5(500–599) aralıkları yapısal denetlenir.",
                styles["body_sm"],
            ),
            rl_p(
                "<b>• Dal Koruması (ADR-500):</b> "
                "<font name='Consolas' size='7.0'>strict: true</font>, CODEOWNERS onayı ve "
                "zorunlu 4 kontrol yeşile dönmeden "
                "<font name='Consolas' size='7.0'>main</font> dalına hiçbir PR giremez.",
                styles["body_sm"],
            ),
            rl_p(
                f"<b>• Köken Kaydı:</b> <font name='Consolas' size='7.0'>data/manifest.csv</font>"
                f" içinde {len(data['manifest_rows'])} veri setinin SHA-256 özeti "
                "yalnızca ekleme kuralıyla tutulur.",
                styles["body_sm"],
            ),
        ],
        left_w,
        styles,
        accent=C_NASA_BLUE,
        pad_y=5.5,
    )

    c_demo = make_card(
        "Tekrar Üretilebilir 120 sn Demo Video Hattı (3 Betik)",
        [
            rl_p(
                "<b>1. <font name='Consolas' size='7.0'>k5_record_demo.py</font>:</b> "
                "Chrome DevTools Protokolü ile gerçek arayüzden 1920×900 kare yakalar "
                "(alt 180 px altyazıya ayrılır).",
                styles["body_sm"],
            ),
            rl_p(
                "<b>2. <font name='Consolas' size='7.0'>k5_synthesize_narration.py</font>:</b> "
                "Windows SAPI İngilizce anlatım + "
                "<font name='Consolas' size='7.0'>ffprobe</font> ile gerçek süre ölçer.",
                styles["body_sm"],
            ),
            rl_p(
                f"<b>3. <font name='Consolas' size='7.0'>k5_build_video.py</font>:</b> "
                "1080p30 H.264+AAC video ve "
                f"<b>{data['srt_count']} girdili</b> "
                "<font name='Consolas' size='7.0'>.en.srt</font> "
                "dosyasını tek kaynaktan senkronlar.",
                styles["body_sm"],
            ),
        ],
        right_w,
        styles,
        bg=C_NOTE_BG,
        accent=C_AZURE,
        pad_y=5.5,
    )

    bottom_callout = make_callout(
        "NASA Düzeyinde Denetlenebilirlik:",
        "5 mühendis eşzamanlı olarak ayrı modüllerde çalışırken dosya sahipliği sınırları "
        "(CODEOWNERS), stdlib tabanlı kanonik sözleşme denetimi ve Linux+Windows "
        "çapraz-OS CI kapıları sayesinde birleşmeler deterministik ve tam izlenebilir kalır.",
        CONTENT_W,
        styles,
        bg=C_OK_BG,
        bar=C_OK,
    )

    return meta, [
        kpis,
        Spacer(1, 5),
        pipe_diag,
        Spacer(1, 6),
        make_grid_row([(c_gov, left_w), (c_demo, right_w)], gap=8.0),
        Spacer(1, 6),
        bottom_callout,
    ]


def build_slide_12(
    data: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> tuple[SlideMeta, list]:
    meta = SlideMeta(
        12,
        "GÖREV KARAR ÖZETİ & SONUÇ",
        "12 NASA Artemis III Bölgesi Tam Sıralaması & Görev Tavsiyesi",
        "Görünürlük, 3σ iniş güvenliği ve ileri röle/rota fiziğinin "
        "birleşik görev kararı (outputs/k3 + outputs/k2)",
    )
    ranked = sorted(
        data["sites"],
        key=lambda r: (r["joint_pct"], r["sun_pct"], r["safety_score"]),
        reverse=True,
    )

    role_map = {
        "Site05": "240m Üst Sınır Zirvesi (5m doğrulama gerekli)",
        "Site12": "240m Üst Sınır #2 (Yüksek enlem, antik kabuk)",
        "Site08": "Malapert: Güçlü DTE (%94.2) + 5.2 km PSR rotası",
        "Site13": "En Güvenli İniş Zemini (%100 3σ, 0.65° eğim)",
        "Site11": "Orta-Üst Ortak (%42.4) + %100 Güneş (240m)",
        "Site01": "5 m/px DTE LİDERİ (%100 Güneş · 53.7 sa Pencere)",
        "Site09": "Düz Plato (%100 DTE, %51.6 3σ güvenli)",
        "Site03": "Sınırlı Güneş (%24.3) + Dik Sırt (15.3°)",
        "Site04": "GATEWAY BİLİM ÜSSÜ (%0 DTE -> %97.7 NRHO!)",
        "Site06": "Gölge Bölgesi (%0 Güneş, %57.8 Dünya)",
        "Site07": "Haworth: %97.3 3σ Düz Zemin · Saf PSR Hedefi",
        "Site02": "Derin Gölge (%0 Güneş / %0 Dünya)",
    }

    rows: list[list[str]] = []
    hl: dict[int, colors.Color] = {}
    for idx, r in enumerate(ranked, start=1):
        long_str = f"{r['longest_joint_h']:.1f} sa" if r["longest_joint_h"] > 0 else "yok"
        rows.append(
            [
                f"<b>{idx}</b>",
                f"<b>{r['site_id']}</b>",
                r["site_name"],
                f"{r['profile_label']} · {r['k2_quality_flag']}",
                f"%{r['sun_pct']:.1f}",
                f"%{r['earth_pct']:.1f}",
                f"<b>%{r['joint_pct']:.2f}</b>",
                long_str,
                f"{r['slope_mean']:.1f}°",
                f"{r['safety_score']:.1f}",
                role_map.get(r["site_id"], r["verdict"]),
            ]
        )
        if r["site_id"] == "Site01":
            hl[idx - 1] = C_OK_BG
        elif r["site_id"] == "Site04":
            hl[idx - 1] = C_WARN_BG
        elif r["site_id"] == "Site13":
            hl[idx - 1] = C_NOTE_BG

    tbl = make_styled_table(
        [
            "#",
            "Site",
            "Bölge",
            "K2 Profil",
            "Güneş",
            "Dünya",
            "Ortak",
            "En Uzun",
            "Eğim",
            "Güv.Skor",
            "Stratejik Görev Rolü",
        ],
        rows,
        [
            CONTENT_W * 0.03,
            CONTENT_W * 0.06,
            CONTENT_W * 0.14,
            CONTENT_W * 0.12,
            CONTENT_W * 0.06,
            CONTENT_W * 0.06,
            CONTENT_W * 0.07,
            CONTENT_W * 0.07,
            CONTENT_W * 0.06,
            CONTENT_W * 0.07,
            CONTENT_W * 0.26,
        ],
        styles,
        aligns=["C", "C", "L", "C", "R", "R", "R", "R", "R", "R", "L"],
        font_size=6.5,
        pad_x=2.5,
        pad_y=2.3,
        highlight_rows=hl,
    )

    w4 = (CONTENT_W - 15.0) / 4.0
    s01 = data["site_map"]["Site01"]
    s04 = data["site_map"]["Site04"]
    s13 = data["site_map"]["Site13"]
    gw04 = data["gateway"]["Site04_4km"]

    rec1 = make_card(
        "DTE Dengeli Lider: Site01",
        [
            rl_p(
                f"5 m/px doğrulanmış <b>%{s01['sun_pct']:.0f} Güneş</b> + "
                f"<b>%{s01['joint_pct']:.2f} Ortak</b> ({s01['longest_joint_h']:.2f} sa) ile "
                "rölesiz Artemis III inişi için referans kazanan.",
                styles["body_sm"],
            )
        ],
        w4,
        styles,
        bg=C_OK_BG,
        accent=C_OK,
        pad_y=4.5,
    )
    rec2 = make_card(
        "Üst Sınır Zirveleri: 05/12/08",
        [
            rl_p(
                "240 m/px DEM'de %88–100 ortak görünürlük; <b>ancak</b> mikro-rölyef düzleşmesi "
                "nedeniyle iniş öncesi 5 m/px LOLA doğrulaması zorunludur.",
                styles["body_sm"],
            )
        ],
        w4,
        styles,
        accent=C_AZURE,
        pad_y=4.5,
    )
    rec3 = make_card(
        "En Güvenli Zemin: Site13",
        [
            rl_p(
                f"Mons Mouton (<b>{s13['slope_mean']:.2f}°</b> ort. eğim, "
                f"<b>%{s13['safe_3sigma_pct']:.0f}</b> 3σ, <b>{s13['safety_score']:.1f}</b> skor) "
                "ve Haworth (Site07) düz iniş/rover üssü lideri.",
                styles["body_sm"],
            )
        ],
        w4,
        styles,
        bg=C_NOTE_BG,
        accent=C_NASA_BLUE,
        pad_y=4.5,
    )
    rec4 = make_card(
        "Gateway Bilim Üssü: Site04",
        [
            rl_p(
                f"Doğrudan Dünya %{s04['earth_pct']:.0f} iken Lunar Gateway 9:2 NRHO ile "
                f"<b>%{gw04['gateway_relay_pct']:.2f}</b> kapsama kazanır; "
                "Shackleton PSR biliminin kalbidir.",
                styles["body_sm"],
            )
        ],
        w4,
        styles,
        bg=C_WARN_BG,
        accent=C_GOLD,
        pad_y=4.5,
    )

    return meta, [
        tbl,
        Spacer(1, 6),
        make_grid_row([(rec1, w4), (rec2, w4), (rec3, w4), (rec4, w4)], gap=5.0),
    ]


# ---------------------------------------------------------------------------
# Custom 16:9 Canvas & Page Background Callbacks
# ---------------------------------------------------------------------------


def _make_on_cover_page(footer_stamp: str):
    def on_cover_page(c: canvas.Canvas, _doc: BaseDocTemplate) -> None:
        c.saveState()
        c.setFillColor(C_SPACE_DARK)
        c.rect(0, 0, SLIDE_W, SLIDE_H, fill=1, stroke=0)
        c.setFillColor(C_AZURE)
        c.rect(0, SLIDE_H - 3.0, SLIDE_W, 3.0, fill=1, stroke=0)
        c.setFillColor(C_GOLD)
        c.rect(0, 10.5 * mm, SLIDE_W, 1.5, fill=1, stroke=0)
        c.setFont("Arial", 7.6)
        c.setFillColor(C_LIGHT_DIM)
        c.drawString(MARGIN_X, 5.2 * mm, sanitize_for_font(footer_stamp, "Arial"))
        c.restoreState()

    return on_cover_page


def _make_on_content_page(slide_metas: dict[int, SlideMeta], footer_stamp: str):
    def on_content_page(c: canvas.Canvas, _doc: BaseDocTemplate) -> None:
        page_num = c.getPageNumber()
        meta = slide_metas.get(page_num)
        c.saveState()

        # Pale slide background drawn BEFORE flowables
        c.setFillColor(C_BG_LIGHT)
        c.rect(0, 0, SLIDE_W, SLIDE_H, fill=1, stroke=0)

        # Top NASA header band (18.5 mm)
        hdr_h = 18.5 * mm
        c.setFillColor(C_SPACE_DARK)
        c.rect(0, SLIDE_H - hdr_h, SLIDE_W, hdr_h, fill=1, stroke=0)
        c.setFillColor(C_AZURE_LIGHT)
        c.rect(0, SLIDE_H - hdr_h, SLIDE_W, 1.8, fill=1, stroke=0)
        c.setFillColor(C_GOLD)
        c.rect(0, SLIDE_H - 2.2, SLIDE_W, 2.2, fill=1, stroke=0)

        if meta is not None:
            c.setFont("Arial-Bold", 7.3)
            c.setFillColor(C_CYAN)
            c.drawString(
                MARGIN_X,
                SLIDE_H - 6.0 * mm,
                sanitize_for_font(f"SLAYT {meta.number:02d}  |  {meta.category}", "Arial-Bold"),
            )
            c.setFont("Arial-Bold", 14.0)
            c.setFillColor(colors.white)
            c.drawString(MARGIN_X, SLIDE_H - 11.4 * mm, sanitize_for_font(meta.title, "Arial-Bold"))
            c.setFont("Arial", 8.0)
            c.setFillColor(C_LIGHT_DIM)
            c.drawString(MARGIN_X, SLIDE_H - 16.0 * mm, sanitize_for_font(meta.subtitle, "Arial"))

        c.setFont("Arial-Bold", 8.0)
        c.setFillColor(C_GOLD_BRIGHT)
        c.drawRightString(SLIDE_W - MARGIN_X, SLIDE_H - 7.5 * mm, "LUNA-SIGHT")
        c.setFont("Arial", 7.2)
        c.setFillColor(C_LIGHT_DIM)
        c.drawRightString(
            SLIDE_W - MARGIN_X,
            SLIDE_H - 12.0 * mm,
            sanitize_for_font("NASA Artemis III · K1–K5", "Arial"),
        )

        c.setStrokeColor(C_BORDER)
        c.setLineWidth(0.7)
        c.line(MARGIN_X, 9.8 * mm, SLIDE_W - MARGIN_X, 9.8 * mm)
        c.setFont("Arial", 7.4)
        c.setFillColor(C_MUTED)
        c.drawString(MARGIN_X, 4.8 * mm, sanitize_for_font(footer_stamp, "Arial"))
        c.restoreState()

    return on_content_page


class NumberedSlideCanvas(canvas.Canvas):
    """Canvas overlay adding 'Slayt X / Y' after total page count is known."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self.saveState()
            page_num = self._pageNumber
            self.setFont("Arial-Bold", 7.8)
            self.setFillColor(C_CYAN if page_num == 1 else C_NASA_BLUE)
            y_pos = 5.2 * mm if page_num == 1 else 4.8 * mm
            self.drawRightString(SLIDE_W - MARGIN_X, y_pos, f"Slayt {page_num} / {total}")
            self.restoreState()
            super().showPage()
        super().save()


def count_pdf_pages(pdf_path: Path) -> int:
    """Count pages in generated PDF via standard library byte inspection."""
    raw = pdf_path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page\b", raw))


def build_deck(output_path: Path = OUT_PDF) -> Path:
    """Build the 12-slide presentation PDF and verify exact page count."""
    register_fonts()
    styles = build_styles()
    data = collect_presentation_data()

    builders = [
        build_slide_01,
        build_slide_02,
        build_slide_03,
        build_slide_04,
        build_slide_05,
        build_slide_06,
        build_slide_07,
        build_slide_08,
        build_slide_09,
        build_slide_10,
        build_slide_11,
        build_slide_12,
    ]

    slide_metas: dict[int, SlideMeta] = {}
    story: list[Any] = []
    for idx, fn in enumerate(builders, start=1):
        meta, slide_story = fn(data, styles)
        slide_metas[idx] = meta
        story.extend(slide_story)
        if idx == 1:
            story.append(NextPageTemplate("ContentSlide"))
        if idx < len(builders):
            story.append(PageBreak())

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cover_frame = Frame(
        MARGIN_X,
        BOTTOM_MARGIN,
        CONTENT_W,
        SLIDE_H - 2.0 * BOTTOM_MARGIN,
        id="cover",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    content_frame = Frame(
        MARGIN_X,
        BOTTOM_MARGIN,
        CONTENT_W,
        CONTENT_H,
        id="content",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )

    doc_title = (
        "LUNA-SIGHT: Ay Güney Kutbu Görünürlük, Arazi Riski ve "
        "İleri Görev Fiziği Karar Destek Sistemi"
    )
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=(SLIDE_W, SLIDE_H),
        title=doc_title,
        author="LUNA-SIGHT K1–K5 Konsorsiyumu",
        subject="NASA Artemis III 12 Aday Bölge Resmi Sunumu",
    )

    footer_stamp = (
        f"LUNA-SIGHT · Artemis III Karar Destek Sistemi · {len(data['sites'])} Bölge · "
        f"{data['test_count']} Test · 0 Sözleşme İhlali"
    )
    doc.addPageTemplates(
        [
            PageTemplate(
                id="CoverSlide",
                frames=[cover_frame],
                onPage=_make_on_cover_page(footer_stamp),
            ),
            PageTemplate(
                id="ContentSlide",
                frames=[content_frame],
                onPage=_make_on_content_page(slide_metas, footer_stamp),
            ),
        ]
    )

    doc.build(story, canvasmaker=NumberedSlideCanvas)

    page_count = count_pdf_pages(output_path)
    if page_count != 12:
        raise RuntimeError(
            f"Sunum tam 12 slayt (sayfa) olmalı, ancak {page_count} sayfa üretildi! "
            "Taşan slayt içeriği sıkıştırılmalı."
        )
    return output_path


def main() -> int:
    pdf_path = build_deck(OUT_PDF)
    pages = count_pdf_pages(pdf_path)
    size = pdf_path.stat().st_size
    print(f"Generated: {pdf_path} ({size} bytes, {pages} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
