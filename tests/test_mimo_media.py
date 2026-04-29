import base64

import httpx
import pytest

from openclaw_medical_harness.media import MimoMediaClient


def make_transport(routes):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, str(request.url))
        if key not in routes:
            return httpx.Response(404, json={"error": "not found"})
        status_code, payload = routes[key]
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


def test_mimo_synthesize_speech_parses_audio_payload():
    audio_b64 = base64.b64encode(b"wave-bytes").decode("utf-8")
    transport = make_transport(
        {
            (
                "POST",
                "https://api.xiaomimimo.com/v1/chat/completions",
            ): (
                200,
                {
                    "model": "mimo-v2-tts",
                    "choices": [
                        {
                            "message": {
                                "audio": {
                                    "data": audio_b64,
                                }
                            }
                        }
                    ],
                    "usage": {"total_tokens": 12},
                },
            )
        }
    )
    client = MimoMediaClient(api_key="test-key", client=httpx.Client(transport=transport))
    result = client.synthesize_speech(text="hello", voice="default_en", audio_format="wav")
    assert result["model"] == "mimo-v2-tts"
    assert result["audio_bytes"] == len(b"wave-bytes")
    assert result["voice"] == "default_en"


def test_mimo_analyze_audio_uses_omni_model():
    transport = make_transport(
        {
            (
                "POST",
                "https://api.xiaomimimo.com/v1/chat/completions",
            ): (
                200,
                {
                    "model": "mimo-v2-omni",
                    "choices": [
                        {
                            "message": {
                                "content": "The audio is a calm spoken explanation.",
                                "reasoning_content": "audio reasoning",
                            }
                        }
                    ],
                    "usage": {"prompt_tokens_details": {"audio_tokens": 12}},
                },
            )
        }
    )
    client = MimoMediaClient(api_key="test-key", client=httpx.Client(transport=transport))
    result = client.analyze_audio(prompt="describe", audio_url="https://example.com/a.wav")
    assert result["mode"] == "audio_understanding"
    assert "calm spoken explanation" in result["content"]


def test_mimo_analyze_video_uses_omni_model():
    transport = make_transport(
        {
            (
                "POST",
                "https://api.xiaomimimo.com/v1/chat/completions",
            ): (
                200,
                {
                    "model": "mimo-v2-omni",
                    "choices": [
                        {
                            "message": {
                                "content": "The video shows a clinician explaining a treatment plan.",
                                "reasoning_content": "video reasoning",
                            }
                        }
                    ],
                    "usage": {"prompt_tokens_details": {"video_tokens": 64}},
                },
            )
        }
    )
    client = MimoMediaClient(api_key="test-key", client=httpx.Client(transport=transport))
    result = client.analyze_video(prompt="describe", video_url="https://example.com/v.mp4")
    assert result["mode"] == "video_understanding"
    assert "clinician" in result["content"]


def test_mimo_video_package_parses_json():
    transport = make_transport(
        {
            (
                "POST",
                "https://api.xiaomimimo.com/v1/chat/completions",
            ): (
                200,
                {
                    "model": "mimo-v2-pro",
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"title":"Diabetes Explainer","hook":"Start strong","narration_script":"Text",'
                                    '"scenes":[{"scene_id":"s1","visual":"doctor","duration_seconds":10,'
                                    '"voiceover":"intro","overlay_text":"A1C matters"}],"captions":["A1C matters"],'
                                    '"cta":"Book follow-up","compliance_notes":["No diagnosis without clinician review"]}'
                                )
                            }
                        }
                    ],
                    "usage": {"total_tokens": 99},
                },
            )
        }
    )
    client = MimoMediaClient(api_key="test-key", client=httpx.Client(transport=transport))
    result = client.create_video_package(brief="Explain A1C to a patient")
    assert result["rendered_video"] is False
    assert result["package"]["title"] == "Diabetes Explainer"


def test_mimo_runtime_report_flags_video_generation_unavailable():
    client = MimoMediaClient(api_key="test-key")
    report = client.runtime_report()
    assert report.supported["audio_synthesis"] is True
    assert report.supported["video_generation"] is False


def test_mimo_requires_api_key():
    client = MimoMediaClient(api_key="")
    with pytest.raises(Exception):
        client.synthesize_speech(text="hello")
