"""AI hattı: sentetik test_fixture, çevrimdışı HTTP ve bilimsel sınırlar."""

from __future__ import annotations

import base64
import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
import requests
import responses
from PIL import Image
from rasterio import open as raster_open
from rasterio.transform import from_origin

from luna_sight.ai.client import NimClient, NimConfig, NimError, NimNotConfigured, build_session
from luna_sight.ai.hillshade import prepare_dem_hillshade
from luna_sight.ai.imaging import ImagePreparationError, prepare_uploaded_image
from luna_sight.ai.orchestrator import (
    analyze_region,
    ask_followup,
    build_messages,
    load_region_context,
)
from luna_sight.ai.schema import normalize_ai_payload
from luna_sight.ai.store import load, save


@pytest.fixture
def image():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "gray").save(buffer, format="PNG")
    return prepare_uploaded_image(buffer.getvalue(), "test_fixture.png")


@pytest.fixture
def config():
    return NimConfig("https://nim.example/v1", "test-model", "test-secret", 2, 0)


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost.attacker.example/v1",
        "https://127.0.0.1.attacker.example/v1",
        "https://nim.example/v1",
    ],
)
def test_remote_hosts_require_key(url):
    config = NimConfig(url, "model", None, 2, 0)
    assert config.requires_key
    with pytest.raises(NimNotConfigured):
        NimClient(config).chat([])


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/v1",
        "http://127.0.0.1:8000/v1",
        "http://[::1]:8000/v1",
    ],
)
def test_loopback_without_key(url):
    assert not NimConfig(url, "model", None, 2, 0).requires_key


@pytest.mark.parametrize(
    "url",
    [
        "http://nim.example/v1",
        "https://user:secret@nim.example/v1",
        "https://nim.example/v1?api_key=secret",
        "file:///tmp/nim",
    ],
)
def test_reject_unsafe_urls(url):
    with pytest.raises(NimNotConfigured):
        NimConfig(url, "model", None, 2, 0)


@responses.activate
def test_probe_checks_selected_model(config):
    responses.get(config.base_url + "/models", json={"data": [{"id": "other"}]})
    ready, _ = NimClient(config).probe()
    assert not ready
    responses.get(config.base_url + "/models", json={"data": [{"id": config.model}]})
    assert NimClient(config).probe()[0]


@pytest.mark.parametrize("status", [302, 401, 403, 404, 429, 500])
@responses.activate
def test_error_does_not_echo_key(config, status):
    responses.post(config.endpoint, status=status, body=config.api_key)
    with pytest.raises(NimError) as error:
        NimClient(config).chat([])
    assert config.api_key not in str(error.value)
    assert config.api_key not in repr(config)
    assert len(responses.calls) == 1


@pytest.mark.parametrize("content", [None, "", {}, []])
@responses.activate
def test_empty_content_is_failure(config, content):
    responses.post(config.endpoint, json={"choices": [{"message": {"content": content}}]})
    with pytest.raises(NimError):
        NimClient(config).chat([])


@responses.activate
def test_analysis_preserves_science_and_persists_without_image(config, image, tmp_path):
    responses.post(
        config.endpoint,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "A ridge is visible.",
                                "observations": [
                                    {
                                        "feature": "ridge",
                                        "description": "A 10 km ridge.",
                                        "certainty": "observed",
                                    }
                                ],
                                "elevation_m": 999999,
                            }
                        )
                    }
                }
            ]
        },
    )
    context = load_region_context("Site01")
    result = analyze_region(context, image, NimClient(config))
    assert result.metadata.status == "completed"
    assert result.metadata.inference_executed
    assert result.scientific_analysis is context.scientific
    assert result.scientific_analysis.elevation_m is None
    assert result.conflicts
    stored = load(save(result, tmp_path))
    serialized = json.dumps(stored)
    assert "base64" not in serialized
    assert config.api_key not in serialized


@responses.activate
def test_api_down_keeps_science(config, image):
    responses.post(config.endpoint, body=requests.ConnectionError("test_fixture"))
    context = load_region_context("Site01")
    result = analyze_region(context, image, NimClient(config))
    assert result.metadata.status == "failed"
    assert not result.metadata.inference_executed
    assert result.scientific_analysis is context.scientific


def test_thinking_removed_before_parsing():
    result, notes = normalize_ai_payload('<think>private {}</think>{"summary":"Ridge"}')
    assert result.summary == "Ridge"
    assert not notes
    result, _ = normalize_ai_payload("<think>unfinished thought")
    assert not result.summary


def test_unknown_feature_and_certainty_normalized():
    result, _ = normalize_ai_payload(
        json.dumps(
            {
                "observations": [
                    {
                        "feature": "alien",
                        "description": "Shape",
                        "certainty": "100%",
                    }
                ],
                "slope_deg": 12,
            }
        )
    )
    assert result.observations[0].feature == "other"
    assert result.observations[0].certainty == "uncertain"
    assert not hasattr(result, "slope_deg")


def test_scientific_values_match_recorded_outputs():
    context = load_region_context("Site01")
    assert context.scientific.horizon_mean_deg == -0.372568
    assert context.scientific.horizon_max_deg == 2.215202
    assert context.scientific.joint_visible_fraction == 0.319552
    assert context.scientific.longest_joint_window_hours == 53.6848


def write_dem(path, data, crs=None):
    with raster_open(
        path,
        "w",
        driver="GTiff",
        width=64,
        height=64,
        count=1,
        dtype="float32",
        transform=from_origin(-160, 160, 5, 5),
        nodata=-9999,
        crs=crs or "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +R=1737400 +units=m",
    ) as ds:
        ds.write(data.astype("float32"), 1)


def test_hillshade_flat_surface_and_provenance(tmp_path):
    path = tmp_path / "test_fixture.tif"
    write_dem(path, np.zeros((64, 64)))
    image = prepare_dem_hillshade(path, -90, 0, span_m=300)
    pixels = np.asarray(Image.open(io.BytesIO(base64.b64decode(image.data_url.split(",")[1]))))
    assert pixels.min() == pixels.max()
    assert pixels[0, 0, 0] == pytest.approx(255 / np.sqrt(2), abs=1)
    assert image.is_rendered
    assert image.width == 60
    assert "5 m/piksel" in image.provenance_note
    messages = build_messages(load_region_context("Site01"), image)
    assert image.provenance_note in messages[1]["content"][0]["text"]


def test_hillshade_rejects_earth_and_outside_coverage(tmp_path):
    path = tmp_path / "test_fixture.tif"
    write_dem(path, np.zeros((64, 64)), crs="EPSG:3857")
    with pytest.raises(ImagePreparationError):
        prepare_dem_hillshade(path, -90, 0, span_m=300)
    write_dem(path, np.zeros((64, 64)))
    with pytest.raises(ImagePreparationError):
        prepare_dem_hillshade(path, -89, 0, span_m=300)


def test_hillshade_rejects_nodata(tmp_path):
    path = tmp_path / "test_fixture.tif"
    write_dem(path, np.full((64, 64), -9999))
    with pytest.raises(ImagePreparationError):
        prepare_dem_hillshade(path, -90, 0, span_m=300)


@responses.activate
def test_followup_includes_provenance(config, image):
    responses.post(config.endpoint, json={"choices": [{"message": {"content": "Answer"}}]})
    assert ask_followup(load_region_context("Site01"), image, NimClient(config), "What?")
    payload = json.loads(responses.calls[0].request.body)
    assert image.provenance_note in payload["messages"][1]["content"][0]["text"]


def test_retry_429_and_503_over_real_local_http():
    statuses = [429, 503, 200]
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            status = statuses.pop(0)
            body = json.dumps({"choices": [{"message": {"content": "test_fixture OK"}}]}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Retry-After", "0")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = NimConfig(f"http://127.0.0.1:{server.server_port}/v1", "test-model", None, 2, 2)
    try:
        with build_session(max_retries=2, backoff_factor=0) as session:
            answer = NimClient(config, session=session).chat(
                [
                    {"role": "user", "content": "test_fixture"},
                ]
            )
        assert answer == "test_fixture OK"
        assert len(received) == 3
        assert all(body["model"] == "test-model" for body in received)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("send_headers", [False, True])
def test_slow_inference_is_not_replayed(send_headers):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers["Content-Length"])))
            if send_headers:
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
            time.sleep(0.15)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = NimConfig(f"http://127.0.0.1:{server.server_port}/v1", "test-model", None, 0.03, 2)
    try:
        with build_session(max_retries=2, backoff_factor=0) as session:
            with pytest.raises(NimError) as error:
                NimClient(config, session=session).chat([{"role": "user", "content": "fixture"}])
        assert "yanıt vermedi" in str(error.value) or "zaman aşımı" in str(error.value)
        assert len(received) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
