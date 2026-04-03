"""LLM abstraction – calls an OpenAI-compatible chat completions endpoint."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import openai
from pydantic import ValidationError

from app.config import AppConfig
from app.models import AnalysisPlan
from app.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2


class LLMService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = openai.OpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
        )

    def generate_analysis_plan(
        self,
        question: str,
        schema_context: list[dict[str, Any]],
        selected_tables: list[str],
    ) -> tuple[AnalysisPlan, dict[str, Any], dict[str, Any]]:
        """Call the LLM and return (parsed plan, raw request payload, raw response payload)."""
        user_prompt = build_user_prompt(question, schema_context, selected_tables)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        request_payload: dict[str, Any] = {
            "model": self._config.llm.model,
            "messages": messages,
            "temperature": self._config.llm.temperature,
            "max_tokens": self._config.llm.max_tokens,
        }

        last_error: Exception | None = None
        raw_response: dict[str, Any] = {}

        for attempt in range(1, _MAX_RETRIES + 2):
            try:
                response = self._client.chat.completions.create(
                    model=request_payload["model"],
                    messages=request_payload["messages"],
                    temperature=request_payload["temperature"],
                    max_tokens=request_payload["max_tokens"],
                )
                raw_response = response.model_dump(mode="json")
                content = response.choices[0].message.content or ""
                plan = self._parse_plan(content)
                return plan, request_payload, raw_response

            except (json.JSONDecodeError, ValidationError, KeyError, IndexError) as exc:
                logger.warning("LLM parse attempt %d failed: %s", attempt, exc)
                last_error = exc
            except openai.APIError as exc:
                logger.error("OpenAI API error: %s", exc)
                raise

        raise RuntimeError(
            f"Failed to parse a valid AnalysisPlan after {_MAX_RETRIES + 1} attempts. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _parse_plan(raw_text: str) -> AnalysisPlan:
        """Extract JSON from the LLM reply, tolerating markdown fences."""
        cleaned = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        data = json.loads(cleaned)
        return AnalysisPlan.model_validate(data)
