#!/usr/bin/env python3
"""Fake OpenAI-compatible verifier for testing the local flow without spending tokens.

Extracts acceptance ids from the prompt and returns a PASS for each one.
Do not use in production.
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

CRITERIA_RE = re.compile(r"^\s*-\s+id:\s*([A-Za-z0-9_-]+)\s*$", re.MULTILINE)


def criteria_from_prompt(prompt: str) -> list[str]:
    ids = CRITERIA_RE.findall(prompt)
    unique = list(dict.fromkeys(ids))
    return unique or ["A1", "A2"]


def make_verdict(prompt: str) -> dict[str, object]:
    criteria = [
        {"id": criterion_id, "status": "PASS", "evidence": "local mock"}
        for criterion_id in criteria_from_prompt(prompt)
    ]
    return {
        "verdict": "PASS",
        "summary": "Local mock: every criterion has simulated evidence.",
        "criteria": criteria,
        "findings": [],
        "protected_files_changed": False,
        "tests_weakened": False,
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            request = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            request = {}

        messages = request.get("messages") if isinstance(request, dict) else None
        prompt = ""
        if isinstance(messages, list):
            prompt = "\n".join(
                message.get("content", "")
                for message in messages
                if isinstance(message, dict) and isinstance(message.get("content"), str)
            )

        body = json.dumps(
            {
                "id": "mock-verifier",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(make_verdict(prompt), ensure_ascii=False),
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 1200,
                    "completion_tokens": 120,
                    "total_tokens": 1320,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    port = int(os.environ.get("MOCK_VERIFIER_PORT", "8765"))
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
