"""
Minimal Claude wrapper for the skip tracer + dialer.

Exposes get_claude_model(model_name) -> object with .generate_response(...),
matching the interface the agents expect. No provider factory, no extra SDKs.
"""
import os
from anthropic import Anthropic


class ModelResponse:
    """Thin holder so callers can read .content (a string)."""
    def __init__(self, content):
        self.content = content


class ClaudeModel:
    def __init__(self, api_key, model_name="claude-haiku-4-5"):
        self.model_name = model_name
        self.client = Anthropic(api_key=api_key)

    def generate_response(self, system_prompt, user_content, temperature=0.7, max_tokens=1024):
        resp = self.client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens or 1024,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return ModelResponse(resp.content[0].text.strip())


def get_claude_model(model_name="claude-haiku-4-5"):
    """Return a ready Claude model, or None if no API key is set."""
    api_key = os.getenv("ANTHROPIC_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return ClaudeModel(api_key, model_name)
