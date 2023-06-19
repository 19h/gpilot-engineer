from __future__ import annotations

import json
import logging
import os

from typing import Optional

import openai
import requests

logger = logging.getLogger(__name__)

def get_github_copilot_token(api_token: str) -> Optional[str]:
    url = "https://api.github.com/copilot_internal/v2/token"
    headers = {
        "Authorization": f"token {api_token}",
        "Editor-Version": "vscode/1.79.0-insider",
        "Editor-Plugin-Version": "copilot/1.86.92",
        "User-Agent": "GithubCopilot/1.86.92",
        "Accept": "*/*",
        "Accept-Encoding": "gzip,deflate,br",
    }

    response = requests.get(url, headers=headers)

    # Check for successful status code before trying to parse as JSON
    if response.status_code == 200:
        data = response.json()
        return data.get("token")  # Return the 'token' field, if it exists
    else:
        return None  # or raise an exception, or handle error however you prefer


def read_api_key() -> str:
    # get from env (os.getenv('COPILOT_API_KEY')) or throw
    return os.getenv("COPILOT_KEY")


class AI:
    def __init__(self, model="gpt-4", temperature=0.1):
        self.temperature = temperature
        self.token: str = get_github_copilot_token(read_api_key())

        try:
            openai.Model.retrieve(model)
            self.model = model
        except openai.InvalidRequestError:
            print(
                f"Model {model} not available for provided API key. Reverting "
                "to gpt-3.5-turbo. Sign up for the GPT-4 wait list here: "
                "https://openai.com/waitlist/gpt-4-api"
            )
            self.model = "gpt-3.5-turbo"

    def start(self, system, user):
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        return self.next(messages)

    def fsystem(self, msg):
        return {"role": "system", "content": msg}

    def fuser(self, msg):
        return {"role": "user", "content": msg}

    def fassistant(self, msg):
        return {"role": "assistant", "content": msg}

    def next(self, messages: list[dict[str, str]], prompt=None):
        if prompt:
            messages += [{"role": "user", "content": prompt}]

        logger.debug(f"Creating a new chat completion: {messages}")

        request = self._send_request(messages)
        response = self._parse_response(request)

        messages = messages + [{"role": "assistant", "content": response}]

        logger.debug(f"Chat completion finished: {messages}")

        return messages

    def _send_request(self, messages: list[dict[str, str]]) -> requests.Response:
        return requests.post(
            "https://copilot-proxy.githubusercontent.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + self.token},
            json={
                "model": "copilot-chat",
                "messages": messages,
                # "max_tokens": self.max_token_count,
                "stream": True,
            },
        )

    def _parse_response(self, response: requests.Response) -> str:
        result = ""

        for chunk in response.iter_lines():
            parsed_chunk = self._parse_stream_helper(chunk)

            if parsed_chunk is not None:
                parsed_chunk = json.loads(parsed_chunk)
                delta = parsed_chunk["choices"][0]["delta"]

                if "content" in delta:
                    result += delta["content"]

        return result

    def _parse_stream_helper(self, line: bytes) -> Optional[str]:
        if line:
            if line.strip() == b"data: [DONE]":
                return None
            if line.startswith(b"data: "):
                line = line[len(b"data: ") :]
                return line.decode("utf-8")
            else:
                return None
        return None
