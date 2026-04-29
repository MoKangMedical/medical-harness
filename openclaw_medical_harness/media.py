"""Xiaomi MiMo media integration for audio and video workflows."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import httpx

from .env import getenv


MIMO_DEFAULT_BASE_URL = "https://api.xiaomimimo.com/v1"
MIMO_TEXT_MODEL = "mimo-v2-pro"
MIMO_OMNI_MODEL = "mimo-v2-omni"
MIMO_TTS_MODEL = "mimo-v2-tts"


class MimoMediaError(RuntimeError):
    """Raised when MiMo media APIs fail."""


@dataclass
class MimoRuntimeReport:
    provider: str
    base_url: str
    has_api_key: bool
    supported: dict[str, bool]
    limitations: list[str]


class MimoMediaClient:
    """Thin HTTP client around Xiaomi MiMo OpenAI-compatible media APIs."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or getenv("MIMO_API_KEY")
        self.base_url = (base_url or getenv("MIMO_API_BASE_URL") or MIMO_DEFAULT_BASE_URL).rstrip("/")
        self.client = client

    def runtime_report(self) -> MimoRuntimeReport:
        return MimoRuntimeReport(
            provider="xiaomi-mimo",
            base_url=self.base_url,
            has_api_key=bool(self.api_key),
            supported={
                "audio_synthesis": True,
                "audio_understanding": True,
                "video_understanding": True,
                "video_script_packaging": True,
                "video_generation": False,
            },
            limitations=[
                "Official public docs expose TTS, audio understanding, and video understanding.",
                "Official public docs do not expose a rendered video generation endpoint.",
            ],
        )

    def synthesize_speech(
        self,
        *,
        text: str,
        voice: str = "mimo_default",
        audio_format: str = "wav",
        style: str = "",
        user_prompt: str = "",
        temperature: float = 0.6,
        top_p: float = 0.95,
    ) -> dict[str, Any]:
        if not text.strip():
            raise ValueError("text is required for speech synthesis")

        assistant_text = text.strip()
        if style.strip():
            assistant_text = f"<style>{style.strip()}</style>{assistant_text}"

        messages: list[dict[str, Any]] = []
        if user_prompt.strip():
            messages.append({"role": "user", "content": user_prompt.strip()})
        messages.append({"role": "assistant", "content": assistant_text})

        payload = {
            "model": MIMO_TTS_MODEL,
            "messages": messages,
            "audio": {
                "format": audio_format,
                "voice": voice,
            },
            "temperature": temperature,
            "top_p": top_p,
        }
        data = self._chat_completion(payload)
        message = self._first_message(data)
        audio = message.get("audio") or {}
        audio_b64 = audio.get("data")
        if not audio_b64:
            raise MimoMediaError("MiMo TTS response did not contain audio data")
        return {
            "provider": "xiaomi-mimo",
            "model": data.get("model", MIMO_TTS_MODEL),
            "voice": voice,
            "format": audio_format,
            "text": text,
            "styled_text": assistant_text,
            "audio_base64": audio_b64,
            "audio_bytes": len(base64.b64decode(audio_b64)),
            "usage": data.get("usage", {}),
        }

    def analyze_audio(
        self,
        *,
        prompt: str,
        audio_url: str = "",
        audio_base64: str = "",
        mime_type: str = "audio/wav",
        max_completion_tokens: int = 1024,
    ) -> dict[str, Any]:
        input_audio = self._build_audio_input(audio_url=audio_url, audio_base64=audio_base64, mime_type=mime_type)
        payload = {
            "model": MIMO_OMNI_MODEL,
            "messages": [
                self._default_system_message(),
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": input_audio,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt.strip() or "Please describe the content of the audio.",
                        },
                    ],
                },
            ],
            "max_completion_tokens": max_completion_tokens,
        }
        data = self._chat_completion(payload)
        message = self._first_message(data)
        return {
            "provider": "xiaomi-mimo",
            "model": data.get("model", MIMO_OMNI_MODEL),
            "mode": "audio_understanding",
            "content": message.get("content", ""),
            "reasoning_content": message.get("reasoning_content", ""),
            "usage": data.get("usage", {}),
        }

    def analyze_video(
        self,
        *,
        prompt: str,
        video_url: str = "",
        video_base64: str = "",
        mime_type: str = "video/mp4",
        fps: int = 2,
        media_resolution: str = "default",
        max_completion_tokens: int = 1024,
    ) -> dict[str, Any]:
        video_input = self._build_video_input(video_url=video_url, video_base64=video_base64, mime_type=mime_type)
        payload = {
            "model": MIMO_OMNI_MODEL,
            "messages": [
                self._default_system_message(),
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {
                                "url": video_input,
                            },
                            "fps": fps,
                            "media_resolution": media_resolution,
                        },
                        {
                            "type": "text",
                            "text": prompt.strip() or "Please describe the content of the video.",
                        },
                    ],
                },
            ],
            "max_completion_tokens": max_completion_tokens,
        }
        data = self._chat_completion(payload)
        message = self._first_message(data)
        return {
            "provider": "xiaomi-mimo",
            "model": data.get("model", MIMO_OMNI_MODEL),
            "mode": "video_understanding",
            "content": message.get("content", ""),
            "reasoning_content": message.get("reasoning_content", ""),
            "usage": data.get("usage", {}),
        }

    def create_video_package(
        self,
        *,
        brief: str,
        audience: str = "patients",
        duration_seconds: int = 60,
        language: str = "zh",
        tone: str = "clear medical education",
    ) -> dict[str, Any]:
        if not brief.strip():
            raise ValueError("brief is required for video package generation")

        prompt = (
            "Create a production-ready video package for the following brief.\n"
            "Return valid JSON only with keys: title, hook, narration_script, scenes, captions, cta, compliance_notes.\n"
            "Each scene must include: scene_id, visual, duration_seconds, voiceover, overlay_text.\n"
            f"Audience: {audience}\n"
            f"Duration seconds: {duration_seconds}\n"
            f"Language: {language}\n"
            f"Tone: {tone}\n"
            f"Brief: {brief.strip()}"
        )
        payload = {
            "model": MIMO_TEXT_MODEL,
            "messages": [
                self._default_system_message(),
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": 2048,
            "temperature": 0.8,
            "top_p": 0.95,
        }
        data = self._chat_completion(payload)
        message = self._first_message(data)
        content = message.get("content", "")
        parsed = self._try_parse_json(content)
        return {
            "provider": "xiaomi-mimo",
            "model": data.get("model", MIMO_TEXT_MODEL),
            "mode": "video_script_packaging",
            "rendered_video": False,
            "official_video_generation_supported": False,
            "package": parsed,
            "raw_content": content,
            "usage": data.get("usage", {}),
        }

    def generate_video(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {
            "provider": "xiaomi-mimo",
            "supported": False,
            "reason": "Official Xiaomi MiMo public docs currently expose video understanding, not rendered video generation.",
            "recommended_flow": "Use create_video_package() to generate storyboard, narration, captions, and scene plan, then render with a separate video engine.",
        }

    def _chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise MimoMediaError("MIMO_API_KEY is not configured")

        response = self._request(
            "POST",
            "/chat/completions",
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        data = response.json()
        if response.status_code >= 400:
            raise MimoMediaError(f"MiMo API error {response.status_code}: {data}")
        if "error" in data:
            raise MimoMediaError(f"MiMo API returned error: {data['error']}")
        return data

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self.client is not None:
            return self.client.request(method, f"{self.base_url}{path}", timeout=60.0, **kwargs)
        with httpx.Client(timeout=60.0) as client:
            return client.request(method, f"{self.base_url}{path}", **kwargs)

    @staticmethod
    def _default_system_message() -> dict[str, str]:
        return {
            "role": "system",
            "content": (
                "You are MiMo, an AI assistant developed by Xiaomi. "
                "Today's date: Saturday, April 11, 2026. Your knowledge cutoff date is December 2024."
            ),
        }

    @staticmethod
    def _first_message(data: dict[str, Any]) -> dict[str, Any]:
        choices = data.get("choices") or []
        if not choices:
            raise MimoMediaError("MiMo response did not contain choices")
        message = choices[0].get("message") or {}
        if not message:
            raise MimoMediaError("MiMo response did not contain a message payload")
        return message

    @staticmethod
    def _build_audio_input(*, audio_url: str, audio_base64: str, mime_type: str) -> str:
        if audio_url.strip():
            return audio_url.strip()
        if audio_base64.strip():
            return MimoMediaClient._to_data_url(audio_base64.strip(), mime_type)
        raise ValueError("Either audio_url or audio_base64 is required")

    @staticmethod
    def _build_video_input(*, video_url: str, video_base64: str, mime_type: str) -> str:
        if video_url.strip():
            return video_url.strip()
        if video_base64.strip():
            return MimoMediaClient._to_data_url(video_base64.strip(), mime_type)
        raise ValueError("Either video_url or video_base64 is required")

    @staticmethod
    def _to_data_url(raw_base64: str, mime_type: str) -> str:
        if raw_base64.startswith("data:"):
            return raw_base64
        return f"data:{mime_type};base64,{raw_base64}"

    @staticmethod
    def _try_parse_json(content: str) -> Any:
        text = content.strip()
        if not text:
            return {}
        for candidate in (text, MimoMediaClient._extract_json_block(text)):
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return {"raw": content}

    @staticmethod
    def _extract_json_block(content: str) -> str:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return ""
        return content[start : end + 1]
