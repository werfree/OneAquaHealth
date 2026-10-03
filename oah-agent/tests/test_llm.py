"""Tests for provider selection.

The behaviour worth pinning is *precedence*: an explicit choice always wins over
inference, and inference only fires when nothing is set. Getting this wrong
would silently send a demo at a paid endpoint or at a model that is not running,
which is exactly the kind of failure that is hard to see from the outside.
"""

import os
import unittest
from unittest import mock

from oah_agent import llm


class ProviderSelectionTests(unittest.TestCase):
    def test_explicit_provider_beats_the_environment(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
            self.assertEqual(llm.active_provider("ollama"), "ollama")

    def test_llm_provider_is_used_when_no_argument_is_given(self):
        with mock.patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True):
            self.assertEqual(llm.active_provider(), "ollama")

    def test_an_openai_key_infers_openai(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            self.assertEqual(llm.active_provider(), "openai")

    def test_an_ollama_base_url_infers_ollama(self):
        with mock.patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://box:11434"}, clear=True):
            self.assertEqual(llm.active_provider(), "ollama")

    def test_nothing_configured_falls_back_to_ollama(self):
        # A local default with no key is the friendlier failure: it does not
        # reach for a paid API that the user never configured.
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(llm.active_provider(), "ollama")

    def test_aliases_are_accepted(self):
        self.assertEqual(llm.active_provider("LOCAL"), "ollama")
        self.assertEqual(llm.active_provider("GPT"), "openai")


class ModelSelectionTests(unittest.TestCase):
    def test_ollama_uses_the_ollama_default_without_configuration(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(llm.default_model("ollama"), "deepseek-v4.1-flash:cloud")

    def test_provider_specific_model_wins(self):
        env = {"OLLAMA_MODEL": "llama3.1", "LLM_MODEL": "generic"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(llm.default_model("ollama"), "llama3.1")

    def test_generic_model_fills_the_gap(self):
        with mock.patch.dict(os.environ, {"LLM_MODEL": "generic"}, clear=True):
            self.assertEqual(llm.default_model("openai"), "generic")


class ClientTests(unittest.TestCase):
    def test_ollama_client_targets_the_openai_compatible_endpoint(self):
        with mock.patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://box:11434/"}, clear=True):
            with mock.patch("openai.OpenAI") as fake:
                llm.client("ollama")
        fake.assert_called_once()
        self.assertEqual(fake.call_args.kwargs["base_url"], "http://box:11434/v1")

    def test_openai_without_a_key_is_a_clear_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                llm.client("openai")
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    def test_describe_reports_provider_and_model(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(llm.describe("ollama"), "ollama/deepseek-v4.1-flash:cloud")


class _Completions:
    """Records the arguments of each call and fails the first if told to."""

    def __init__(self, reject_response_format=False):
        self.calls = []
        self.reject_response_format = reject_response_format

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.reject_response_format and "response_format" in kwargs:
            raise ValueError("response_format is not supported")
        return "ok"


class _FakeClient:
    def __init__(self, completions):
        self.chat = mock.Mock(completions=completions)


class JsonCompletionTests(unittest.TestCase):
    def test_response_format_is_used_when_supported(self):
        completions = _Completions()
        llm.json_completion(_FakeClient(completions), model="m", messages=[])
        self.assertEqual(len(completions.calls), 1)
        self.assertEqual(completions.calls[0]["response_format"], {"type": "json_object"})

    def test_a_rejected_response_format_is_retried_without_it(self):
        completions = _Completions(reject_response_format=True)
        result = llm.json_completion(_FakeClient(completions), model="m", messages=[])
        self.assertEqual(result, "ok")
        self.assertEqual(len(completions.calls), 2)
        self.assertNotIn("response_format", completions.calls[1])

    def test_an_unrelated_error_is_not_swallowed(self):
        class Boom:
            def create(self, **kwargs):
                raise RuntimeError("connection refused")

        with self.assertRaises(RuntimeError):
            llm.json_completion(_FakeClient(Boom()), model="m", messages=[])


if __name__ == "__main__":
    unittest.main()
