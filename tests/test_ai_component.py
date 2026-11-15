"""LunarSight AI pencere köprüsü: replay, hata ve kaynak sınırları (test_fixture)."""

import io
import json

import pytest
import responses
from PIL import Image

from luna_sight.ai import component
from luna_sight.ai.client import NimConfig
from luna_sight.ai.imaging import ImagePreparationError, prepare_uploaded_image
from luna_sight.ai.schema import normalize_observation


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "gray").save(buffer, format="PNG")
    image = prepare_uploaded_image(buffer.getvalue(), "test_fixture.png")
    config = NimConfig("https://nim.example/v1", "test-model", "test-secret", 2, 0)
    monkeypatch.setattr(component, "load_config", lambda **kwargs: config)
    monkeypatch.setattr(component, "_prepare_image", lambda request: image)
    monkeypatch.setattr(component, "save", lambda result: tmp_path / "result.json")
    return config, image


def request(action="analyze", request_id="test_fixture_1"):
    return {"id": request_id, "site_id": "Site01", "kind": "dem", "action": action}


def test_prepare_does_not_call_model_and_replay_is_ignored(bridge, monkeypatch):
    monkeypatch.setattr(component, "NimClient", lambda *args: pytest.fail("model called"))
    state = {}
    assert component.handle_component_request(request("prepare"), state)
    assert state["lunar_ai_response"]["ok"]
    assert state["lunar_ai_response"]["image"]["dataUrl"].startswith("data:image/")
    assert not component.handle_component_request(request("prepare"), state)
    assert "test-secret" not in json.dumps(state)


@responses.activate
def test_analysis_reaches_client_exactly_once(bridge):
    config, _ = bridge
    responses.post(
        config.endpoint,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "test_fixture sırt",
                                "observations": [
                                    {
                                        "feature": "ridge",
                                        "description": "Sırt seçiliyor",
                                        "point": [0.5, 0.4],
                                    }
                                ],
                            }
                        )
                    }
                }
            ]
        },
    )
    state = {}
    assert component.handle_component_request(request(), state)
    assert not component.handle_component_request(request(), state)
    assert len(responses.calls) == 1
    result = state["lunar_ai_response"]
    assert result["ok"]
    assert result["analysis"]["metadata"]["inferenceExecuted"]
    assert result["analysis"]["scientificAnalysis"]["horizon_mean_deg"] == -0.372568
    assert "test-secret" not in json.dumps(result)


@responses.activate
def test_provider_failure_is_not_a_fake_success(bridge):
    config, _ = bridge
    responses.post(config.endpoint, status=503, body="test-secret")
    state = {}
    component.handle_component_request(request(), state)
    reply = state["lunar_ai_response"]
    assert not reply["ok"]
    assert "503" in reply["error"]
    assert "test-secret" not in json.dumps(reply)
    assert not reply["analysis"]["aiAnalysis"]["observations"]


@responses.activate
def test_questions_use_session_history(bridge):
    config, _ = bridge
    responses.post(config.endpoint, json={"choices": [{"message": {"content": "İlk cevap"}}]})
    responses.post(config.endpoint, json={"choices": [{"message": {"content": "İkinci cevap"}}]})
    state = {}
    first = {**request("ask"), "question": "İlk soru"}
    second = {**request("ask", "test_fixture_2"), "question": "İkinci soru"}
    component.handle_component_request(first, state)
    component.handle_component_request(second, state)
    assert state["lunar_ai_response"]["answer"] == "İkinci cevap"
    body = json.loads(responses.calls[-1].request.body)
    assert any(message.get("content") == "İlk cevap" for message in body["messages"])


def test_selected_scene_is_read_from_source_not_browser_numbers():
    payload = {
        **request(),
        "scene": {
            "timestamp": "2026-11-14T00:00:00+00:00",
            "scenario": "4000m",
            "earth": {"altitude_deg": 999999},
        },
    }
    scene = component._scene_context(payload).scientific.additional["selected_scene"]
    assert scene["earth"]["altitude_deg"] == -5.0359
    assert scene["earth"]["state"] == "blocked"
    payload["scene"]["scenario"] = "0deg"
    assert (
        component._scene_context(payload).scientific.additional["selected_scene"]["earth"][
            "horizon_deg"
        ]
        == 0
    )


def test_virtual_case_is_not_passed_as_nominal_science():
    context = component._scene_context({**request(), "scene": {"caseActive": True}})
    scene = context.scientific.additional["selected_scene"]
    assert "note" in scene
    assert "earth" not in scene


@pytest.mark.parametrize("data_url", ["data:image/png;base64,!!!", "file:///secrets", "bad"])
def test_bad_upload_rejected(data_url):
    with pytest.raises(ImagePreparationError):
        component._prepare_image({**request(), "kind": "upload", "data_url": data_url})


@pytest.mark.parametrize(
    "box,point",
    [
        ([-1, 0, 1, 1], [float("nan"), 0.4]),
        ([0.8, 0.2, 0.1, 0.9], [True, 0.5]),
        ([0.2, 0.2, 3, 0.9], ["0.3", 0.5]),
    ],
)
def test_invalid_grounding_is_dropped(box, point):
    observation = normalize_observation(
        {"feature": "ridge", "description": "test_fixture", "box": box, "point": point}
    )
    assert observation.box is None
    assert observation.point is None


def test_public_config_never_exposes_key(bridge):
    assert component.public_configuration() == {"model": "test-model", "configured": True}


@pytest.mark.parametrize("mode,field", [("detect", "box field"), ("point", "point field")])
@responses.activate
def test_detection_and_point_modes_request_real_visual_grounding(bridge, mode, field):
    config, _ = bridge
    responses.post(
        config.endpoint, json={"choices": [{"message": {"content": '{"summary":"test_fixture"}'}}]}
    )
    state = {}
    component.handle_component_request({**request(), "mode": mode, "focus": "ridge"}, state)
    payload = json.loads(responses.calls[0].request.body)
    assert field in payload["messages"][-1]["content"]
    assert state["lunar_ai_response"]["ok"]
