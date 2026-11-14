"""LUNA SIGHT - K4 Streamlit arayuzu (iskelet).

Issue #4 (A/B karsilastirma deneyimi) icin arayuz kabugu.
K1-K3 modulleri `src/luna_sight/` altinda henuz bulunmadigi icin bilimsel
degerler uretilmez; tum durumlar veri sozlesmesindeki `missing` kalite
bayragi ile gosterilir. Veri geldiginde `load_visibility()` fonksiyonu
gercek modullere baglanacak.

Sozlesme: docs/DATA_CONTRACT.md
"""

from __future__ import annotations

import datetime as dt
import importlib
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DATA_CONTRACT_COLUMNS = [
    "site_id",
    "latitude_deg",
    "longitude_deg_east",
    "timestamp_utc",
    "sun_az_deg",
    "sun_alt_deg",
    "earth_az_deg",
    "earth_alt_deg",
    "terrain_horizon_sun_deg",
    "terrain_horizon_earth_deg",
    "sun_visible",
    "earth_visible",
    "joint_visible",
    "quality_flag",
    "source_id",
    "source_version",
    "model_id",
    "parameters",
]

MODULES = {
    "K1 efemeris (Horizons)": "luna_sight.ephemeris",
    "K2 arazi (LOLA)": "luna_sight.terrain",
    "K3 gorunurluk": "luna_sight.visibility",
}


def module_available(dotted_name: str) -> bool:
    """Modul gercekten uygulanmis ve ice aktarilabiliyor mu.

    `src/luna_sight/*` klasorleri bos olsa bile Python bunlari namespace paketi
    sayip ice aktarir; bu yuzden once en az bir `.py` dosyasi aranir.
    """
    directory = SRC_DIR.joinpath(*dotted_name.split("."))
    if not any(directory.rglob("*.py")):
        return False
    try:
        importlib.import_module(dotted_name)
        return True
    except Exception:  # noqa: BLE001 - eksik modul beklenen durum
        return False


def empty_contract_frame() -> pd.DataFrame:
    """Sozlesme alanlariyla bos veri cercevesi; uydurma deger icermez."""
    return pd.DataFrame(
        {column: pd.Series(dtype="object") for column in DATA_CONTRACT_COLUMNS}
    )


def load_visibility(site: str, start_utc: dt.datetime, hours: int) -> pd.DataFrame:
    """K3 ciktisini dondurur.

    Modul hazir olmadigi icin her zaman sozlesmeye uygun bos cerceve doner.
    Baglanti noktasi: K3 `src/luna_sight/visibility/` altinda arayuz yayinladiginda
    burasi guncellenecek. Bos cerceve `quality_flag=missing` anlamina gelir.
    """
    _ = (site, start_utc, hours)
    return empty_contract_frame()


def horizon_figure() -> go.Figure:
    """Ufuk gorunumu; veri yokken yalnizca sembol gostergesi cizer."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=[],
            theta=[],
            mode="markers",
            name="Gunes",
            marker={"symbol": "circle", "size": 12, "color": "#f5a623"},
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=[],
            theta=[],
            mode="markers",
            name="Dunya",
            marker={"symbol": "diamond", "size": 12, "color": "#4a90d9"},
        )
    )
    fig.add_trace(
        go.Scatterpolar(
            r=[],
            theta=[],
            mode="lines",
            name="Arazi ufku",
            line={"color": "#8c8c8c", "dash": "dot"},
        )
    )
    fig.update_layout(
        title="Yerel ufuk gorunumu (azimut / yukseklik)",
        polar={
            "radialaxis": {"range": [0, 90], "title": "Yukseklik (derece)"},
            "angularaxis": {"direction": "clockwise", "rotation": 0, "period": 360},
        },
        showlegend=True,
        height=430,
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
    )
    fig.add_annotation(
        text="Veri yok: K2 ufuk profili ve K1 efemeris bekleniyor",
        showarrow=False,
        x=0.5,
        y=-0.12,
        xref="paper",
        yref="paper",
        font={"size": 12, "color": "#8c8c8c"},
    )
    return fig


def timeline_figure() -> go.Figure:
    """Zaman cizelgesi; seri gelmeden bos eksen cizer."""
    fig = go.Figure()
    fig.update_layout(
        title="Gorunurluk zaman cizelgesi (UTC)",
        xaxis={"title": "Zaman (UTC)"},
        yaxis={"title": "Durum"},
        height=320,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
    )
    fig.add_annotation(
        text="Veri yok: K3 gorunurluk motoru bekleniyor",
        showarrow=False,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        font={"size": 12, "color": "#8c8c8c"},
    )
    return fig


def status_badges() -> None:
    """Modul hazirlik durumunu seffaf bicimde gosterir."""
    columns = st.columns(len(MODULES))
    for column, (label, dotted) in zip(columns, MODULES.items()):
        ready = module_available(dotted)
        column.metric(label, "hazir" if ready else "bekliyor", "ok" if ready else "-")


def sidebar() -> tuple[str, str, dt.datetime, int]:
    st.sidebar.header("Karsilastirma kurulumu")
    st.sidebar.caption(
        "Aday bolgeler K2 arazi modulunden gelecek; henuz tanimli degil."
    )
    site_a = st.sidebar.selectbox("Bolge A", ["(veri yok)"], index=0, disabled=True)
    site_b = st.sidebar.selectbox("Bolge B", ["(veri yok)"], index=0, disabled=True)

    st.sidebar.divider()
    today_utc = dt.datetime.now(dt.UTC).replace(second=0, microsecond=0)
    start_utc = st.sidebar.datetime_input(
        "Baslangic (UTC)",
        value=today_utc,
        step=dt.timedelta(minutes=5),
        help="Veri sozlesmesi: UTC, ISO 8601, varsayilan tarama 5 dakika.",
    )
    hours = st.sidebar.slider(
        "Analiz penceresi (saat)",
        min_value=1,
        max_value=168,
        value=168,
        step=1,
        help="Veri sozlesmesi varsayilani 168 saat.",
    )
    st.sidebar.divider()
    st.sidebar.caption(
        "Bu ekran veri gelene kadar sayi uretmez. Eksik veri ne `visible` ne "
        "`blocked` sayilir (docs/DATA_CONTRACT.md)."
    )
    return site_a, site_b, start_utc, hours


def main() -> None:
    st.set_page_config(page_title="LUNA SIGHT", page_icon="🌙", layout="wide")
    st.title("LUNA SIGHT")
    st.caption(
        "Ay'in guney kutbundaki aday inis bolgelerini Gunes/Dunya ufuk konumlari "
        "uzerinden karsilastiran prototip. Rol: K4 arayuz."
    )

    site_a, site_b, start_utc, hours = sidebar()
    status_badges()

    if not all(module_available(name) for name in MODULES.values()):
        st.info(
            "Bilimsel moduller henuz bagli degil. Arayuz iskeleti calisiyor; "
            "tum sonuclar `missing` kalite durumundadir.",
            icon="ℹ️",
        )

    frame_a = load_visibility(site_a, start_utc, hours)
    frame_b = load_visibility(site_b, start_utc, hours)

    compare_tab, horizon_tab, timeline_tab, source_tab = st.tabs(
        ["Karsilastirma", "Ufuk gorunumu", "Zaman cizelgesi", "Kaynak ve sinirlar"]
    )

    with compare_tab:
        left, right = st.columns(2)
        for column, site, frame in ((left, site_a, frame_a), (right, site_b, frame_b)):
            with column:
                st.subheader(f"Bolge: {site}")
                if frame.empty:
                    st.warning("Veri yok (kalite: `missing`)", icon="⚠️")
                    st.dataframe(empty_contract_frame(), height=160)
                else:
                    st.dataframe(frame)
                st.caption("Gunes ve Dunya ayri sembollerle isaretlenir.")

    with horizon_tab:
        st.plotly_chart(horizon_figure())

    with timeline_tab:
        st.plotly_chart(timeline_figure())
        st.caption(f"Pencere: {start_utc.isoformat()} + {hours} saat")

    with source_tab:
        st.markdown(
            """
**Kaynak ve kapsam**

- Veri sozlesmesi: `docs/DATA_CONTRACT.md` (UTC, dogu-pozitif boylam, derece).
- Efemeris: JPL Horizons (K1) - henuz bagli degil.
- Arazi/ufuk: LRO/LOLA (K2) - henuz bagli degil.
- Gorunurluk siniflari: `visible`, `blocked`, `uncertain`; kalite: `valid`,
  `partial`, `missing`, `test_fixture`.
- Bilimsel sinir: bu prototip inis guvenligi karari vermez; yalnizca
  karsilastirmali on degerlendirme sunar.
"""
        )
        st.divider()
        st.caption(
            "Kaynak kimligi, surum ve parametreler veri geldiginde burada listelenecek."
        )

    st.divider()
    st.caption(
        "Depo: github.com/kingos352/luna-sight | Dal: k4/dev-environment | "
        "Durum: arayuz iskeleti"
    )


if __name__ == "__main__":
    main()
