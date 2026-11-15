"""LunarSight AI React penceresi ile sunucu arasındaki oturum köprüsü."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
import re
import traceback
from collections.abc import MutableMapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from luna_sight.ai.client import NimClient, NimError, load_config
from luna_sight.ai.hillshade import prepare_dem_hillshade
from luna_sight.ai.imaging import (
    REPO_ROOT,
    ImagePreparationError,
    PreparedImage,
    prepare_rendered_capture,
    prepare_uploaded_image,
)
from luna_sight.ai.orchestrator import (
    RegionContext,
    analyze_region,
    ask_followup,
    load_region_context,
)
from luna_sight.ai.store import save
from luna_sight.terrain.sites import get_candidate_site

_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def public_configuration() -> dict[str, Any]:
    """Tarayıcıya anahtar ve sunucu adresi gönderilmez."""
    try:
        config = load_config()
        return {
            "model": config.model,
            "configured": bool(config.api_key) or not config.requires_key,
        }
    except NimError:
        return {"model": "", "configured": False}


def _prepare_image(request: dict) -> PreparedImage:
    site = get_candidate_site(request["site_id"])
    kind = request.get("kind")
    if kind == "dem":
        directory = Path(os.environ.get("LUNA_SIGHT_DEM_DIR", str(REPO_ROOT / "data/cache/lola")))
        return prepare_dem_hillshade(
            directory / f"{site.site_id}_final_adj_5mpp_surf.tif",
            site.latitude_deg,
            site.longitude_deg_east,
        )
    if kind not in ("capture", "upload"):
        raise ImagePreparationError("Geçersiz görüntü kaynağı.")
    data_url = request.get("data_url")
    if (
        not isinstance(data_url, str)
        or len(data_url) > 6_000_000
        or not re.match(r"^data:image/(png|jpeg|webp);base64,", data_url)
    ):
        raise ImagePreparationError(
            "Geçerli bir PNG, JPEG veya WEBP görüntüsü gerekiyor (en çok 4 MB)."
        )
    try:
        data = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    except (ValueError, binascii.Error):
        raise ImagePreparationError("Görüntü aktarımı bozuk.") from None
    if len(data) > 4 * 1024 * 1024:
        raise ImagePreparationError("Görüntü dosyası 4 MB sınırını aşıyor.")
    if kind == "capture":
        return prepare_rendered_capture(data, "Kullanıcının seçtiği mevcut 3B görünüm.")
    return prepare_uploaded_image(data, str(request.get("filename", "görüntü"))[:120])


def _image_reply(image: PreparedImage, kind: str) -> dict:
    return {
        "kind": kind,
        "dataUrl": image.data_url,
        "width": image.width,
        "height": image.height,
        "sourceLabel": image.source_label,
        "provenance": image.provenance_note,
    }


def _scene_context(request: dict) -> RegionContext:
    """Seçili anın değerlerini tarayıcının gönderdiği sayılardan değil kaynak dosyadan al."""
    context = load_region_context(request["site_id"])
    scene = request.get("scene")
    if not isinstance(scene, dict):
        return context
    snapshot: dict = {"timestamp": scene.get("timestamp"), "scenario": scene.get("scenario")}
    if scene.get("caseActive"):
        snapshot["note"] = (
            "Connecting Ridge gösterim vakası açık. Nominal K2/K3 özeti sanal yamayı "
            "temsil etmez. Görselden yama sonrası fiziksel ölçüm veya görünürlük çıkarma."
        )
    else:
        path = REPO_ROOT / "app/static/moon/data/timeseries.json"
        data = json.loads(path.read_text(encoding="utf-8"))[context.site_id]
        timestamp = scene.get("timestamp")
        if timestamp not in data["timestamps"] or scene.get("scenario") not in (
            "0deg",
            "2000m",
            "4000m",
        ):
            raise ImagePreparationError(
                "Seçilen UTC anı veya ufuk senaryosu kaynak veride bulunamadı."
            )
        index = data["timestamps"].index(timestamp)
        suffix = "2km" if scene["scenario"] == "2000m" else "4km"
        for body in ("sun", "earth"):
            altitude = data[f"{body}_alt"][index]
            horizon = 0 if scene["scenario"] == "0deg" else data[f"{body}_horizon_{suffix}"][index]
            margin = altitude - horizon
            snapshot[body] = {
                "azimuth_deg": data[f"{body}_az"][index],
                "altitude_deg": altitude,
                "horizon_deg": horizon,
                "margin_deg": margin,
                "state": "visible" if margin > 0.1 else "blocked" if margin < -0.1 else "uncertain",
            }
        snapshot["source"] = "app/static/moon/data/timeseries.json; nominal, ±0.10° transition band"
    return replace(
        context,
        scientific=replace(
            context.scientific,
            additional={**context.scientific.additional, "selected_scene": snapshot},
        ),
    )


def handle_component_request(request: Any, state: MutableMapping) -> bool:
    """Yeni isteği bir kez işle; rerun/replay aynı modeli tekrar çağırmaz.

    True: yeni yanıt hazır, component argümanlarının iletilmesi için rerun gerekir.
    False: bekleyen yeni istek yok. Durum yalnızca bu kullanıcının oturumundadır.
    """
    if not isinstance(request, dict):
        return False
    request_id = request.get("id")
    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        return False
    handled = state.setdefault("lunar_ai_handled", [])
    if request_id in handled:
        return False
    # Çağrıdan önce işaretle: Streamlit tekrar çalıştırsa da ücretli istek tekrarlanmaz.
    handled.append(request_id)
    del handled[:-100]
    reply: dict = {"id": request_id, "ok": False}
    try:
        action = request.get("action")
        if action not in ("prepare", "analyze", "ask"):
            raise ImagePreparationError("Desteklenmeyen AI işlemi.")
        load_config()  # .env içindeki DEM dizinini de yükle.
        image = _prepare_image(request)
        reply["image"] = _image_reply(image, request["kind"])
        if action == "prepare":
            reply["ok"] = True
        else:
            context = _scene_context(request)
            client = NimClient(load_config(timeout=90, max_retries=0))
            if action == "analyze":
                mode = request.get("mode", "caption")
                if mode not in ("caption", "detect", "point"):
                    raise ImagePreparationError("Geçersiz görsel analiz modu.")
                focus = str(request.get("focus", ""))[:300]
                if mode == "detect":
                    focus += (
                        " Locate clearly visible requested features with approximate normalized "
                        "image boxes in the box field. Return null if unsupported."
                    )
                elif mode == "point":
                    focus += (
                        " Mark clearly visible feature centers with approximate normalized "
                        "image points in the point field. Do not recommend a landing spot. "
                        "Return null if unsupported."
                    )
                result = analyze_region(context, image, client, focus=focus)
                reply["analysis"] = result.to_dict()
                reply["ok"] = result.metadata.inference_executed
                if not reply["ok"]:
                    reply["error"] = result.metadata.notes[-1]
                try:
                    save(result)
                except OSError:
                    reply["saveWarning"] = "Sonuç mevcut; disk kaydı yazılamadı."
            else:
                question = str(request.get("question", "")).strip()
                if not question or len(question) > 2000:
                    raise ImagePreparationError("Soru 1–2000 karakter olmalı.")
                image_key = hashlib.sha256((context.site_id + image.data_url).encode()).hexdigest()
                if state.get("lunar_ai_history_image") != image_key:
                    state["lunar_ai_history"] = []
                    state["lunar_ai_history_image"] = image_key
                history = state.setdefault("lunar_ai_history", [])
                reply["answer"] = ask_followup(context, image, client, question, history)
                history.extend(
                    [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": reply["answer"]},
                    ]
                )
                del history[:-6]
                reply["ok"] = True
    except (NimError, ImagePreparationError) as exc:
        reply["error"] = str(exc)
    except OSError:
        reply["error"] = "Kaynak verisi okunamadı. DEM ve uygulama veri dosyalarını kontrol edin."
    except (KeyError, TypeError, ValueError) as exc:
        logging.getLogger(__name__).warning(
            "LunarSight AI %s at %s",
            type(exc).__name__,
            [
                (Path(frame.filename).name, frame.lineno)
                for frame in traceback.extract_tb(exc.__traceback__)
            ],
        )
        reply["error"] = "İstek veya bölge bilgisi geçersiz. Görüntüyü yeniden hazırlayın."
    state["lunar_ai_response"] = reply
    return True


def render_lunar_component(component: Any) -> None:
    import streamlit as st

    request = component(
        configuration=public_configuration(),
        ai_response=st.session_state.get("lunar_ai_response"),
        default=None,
        key="lunar_sight_globe",
    )
    if isinstance(request, dict) and request.get("id") not in st.session_state.get(
        "lunar_ai_handled", []
    ):
        with st.spinner("LunarSight AI isteği işleniyor…"):
            if handle_component_request(request, st.session_state):
                st.rerun()
