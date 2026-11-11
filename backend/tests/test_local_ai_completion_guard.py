"""Regression tests for local AI response completeness.

Run from backend/: python -m unittest discover -s tests -p 'test_local_ai_completion_guard.py'
"""
import asyncio
import unittest
from unittest.mock import patch

from app.local_ai import LocalAIClient, LocalAIError


class _Response:
    is_error = False

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class _Client:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, *_args, **_kwargs):
        return _Response(self.payload)


class CompletionGuardTests(unittest.TestCase):
    def _run(self, finish_reason, content, reasoning=""):
        payload = {"choices": [{"finish_reason": finish_reason, "message": {
            "content": content, "reasoning_content": reasoning,
        }}]}
        client = LocalAIClient()
        with patch("app.local_ai.httpx.AsyncClient", side_effect=lambda **_: _Client(payload)):
            return asyncio.run(client._generate_with_embedded("Explain coke burn", None))

    def test_rejects_truncated_answer_even_if_text_is_present(self):
        with self.assertRaisesRegex(LocalAIError, "truncated"):
            self._run("length", "Regeneration removes sulfur and")

    def test_accepts_completed_answer(self):
        result = self._run("stop", "Regeneration burns deposited coke.")
        self.assertEqual(result.text, "Regeneration burns deposited coke.")

    def test_rejects_truncated_reasoning_only_response(self):
        with self.assertRaisesRegex(LocalAIError, "truncated"):
            self._run("length", "", "Unfinished reasoning")
