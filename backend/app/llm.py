"""LLM client.

Works with any OpenAI-compatible endpoint (Groq, OpenAI, Gemini, Ollama, OpenRouter...).
`LLM_PROVIDER=mock` gives an offline, deterministic "LLM" built from simple text
heuristics so the whole application can be demoed and tested without API keys.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Optional

from .config import settings
from .models import Trace
from . import textutils as tu

log = logging.getLogger("crag.llm")


def parse_json(text: str) -> dict:
    """Extract the first JSON object from an LLM response (tolerates code fences / prose)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


class LLMError(RuntimeError):
    """An LLM problem explained in plain language (shown directly in the UI)."""


def today() -> str:
    return date.today().isoformat()


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self._client = None
        if self.provider != "mock":
            from openai import OpenAI

            self._client = OpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key or "not-needed",  # Ollama ignores the key
                timeout=60,
                max_retries=3,
            )
        self._json_mode_supported = True

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"

    def chat(
        self,
        system: str,
        user: str,
        *,
        task: str,
        payload: Optional[dict] = None,
        json_mode: bool = False,
        trace: Optional[Trace] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Send one chat request. `task`/`payload` are only used by the mock LLM."""
        if self.is_mock:
            out = MockLLM.respond(task, payload or {})
            if trace:
                trace.add_llm(len(system + user) // 4, len(out) // 4)
            return out

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        kwargs: dict[str, Any] = dict(
            messages=messages,
            temperature=settings.llm_temperature if temperature is None else temperature,
        )
        if json_mode and self._json_mode_supported:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._call(kwargs)
        if trace and resp.usage:
            trace.add_llm(resp.usage.prompt_tokens, resp.usage.completion_tokens)
        elif trace:
            trace.add_llm(0, 0)
        text = resp.choices[0].message.content or ""
        # Reasoning models (DeepSeek-R1, Qwen3...) may include their thinking inline.
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    # ------------------------------------------------------------------ robustness
    def _call(self, kwargs: dict):
        """One request with automatic recovery from the most common provider problems."""
        import openai

        for attempt in range(3):
            try:
                return self._client.chat.completions.create(model=self.model, **kwargs)
            except openai.AuthenticationError as e:
                raise LLMError(
                    f"The {self.provider} API key was rejected. Check LLM_API_KEY in backend/.env "
                    f"(and that LLM_PROVIDER={self.provider} matches the key).") from e
            except openai.RateLimitError as e:
                raise LLMError(
                    f"{self.provider} rate limit reached. Wait a minute, lower TOP_K, or use "
                    f"EVALUATOR_BACKEND=embedding to make fewer LLM calls.") from e
            except openai.APIConnectionError as e:
                raise LLMError(
                    f"Could not connect to {settings.llm_base_url}. Check your internet connection"
                    + (" and that Ollama is running (`ollama serve`)." if self.provider == "ollama" else ".")) from e
            except (openai.NotFoundError, openai.BadRequestError) as e:
                msg = str(e).lower()
                if "response_format" in kwargs and ("response_format" in msg or "json" in msg):
                    log.warning("JSON mode rejected by %s; retrying without it", self.model)
                    self._json_mode_supported = False
                    kwargs.pop("response_format")
                    continue
                if "model" in msg and any(w in msg for w in ("not found", "does not exist", "decommission",
                                                             "deprecated", "not supported", "no longer")):
                    old = self.model
                    new = self._pick_available_model()
                    if new and new != old:
                        log.warning("Model %s is not available; switching to %s", old, new)
                        self.model = new
                        settings.llm_model = new
                        continue
                    raise LLMError(f"Model '{old}' is not available on {self.provider}. "
                                   f"Set LLM_MODEL in backend/.env to a current model.") from e
                raise LLMError(f"{self.provider} rejected the request: {e}") from e
        raise LLMError("LLM request failed after retries.")

    def _pick_available_model(self) -> Optional[str]:
        """Ask the provider which models exist and choose a good chat model."""
        try:
            ids = [m.id for m in self._client.models.list().data]
        except Exception as e:
            log.warning("could not list models: %s", e)
            return None
        skip = ("whisper", "tts", "guard", "embed", "vision", "audio", "image", "moderation", "orpheus", "prompt")
        chat = [i for i in ids if not any(s in i.lower() for s in skip)]
        prefs = ("gpt-oss-120b", "llama-3.3-70b", "gpt-4o-mini", "gemini-2.5-flash", "gemini-flash",
                 "flash", "gpt-oss-20b", "llama", "qwen", "gemma", "mistral")
        for p in prefs:
            for i in chat:
                if p in i.lower():
                    return i
        return chat[0] if chat else None

    def ping(self) -> dict:
        """Tiny request used by the diagnostics page."""
        out = self.chat_json('Reply with JSON only: {"ok": true}', "ping", task="ping")
        return {"ok": bool(out.get("ok", True)), "model": self.model}

    def chat_json(self, system: str, user: str, **kw) -> dict:
        return parse_json(self.chat(system, user, json_mode=True, **kw))


class MockLLM:
    """Heuristic stand-in for an LLM. Not smart — but transparent and deterministic."""

    @staticmethod
    def respond(task: str, p: dict) -> str:
        fn = getattr(MockLLM, f"_{task}", None)
        if fn is None:
            return "{}"
        return fn(p)

    @staticmethod
    def _ping(p: dict) -> str:
        return '{"ok": true}'

    # -- retrieval evaluator ------------------------------------------------
    @staticmethod
    def _grade(p: dict) -> str:
        q, doc = p["question"], p["document"]
        cov = tu.coverage(q, doc)
        score = round(min(1.0, cov * 1.15), 2)
        reason = f"{int(cov * 100)}% of the question's key terms appear in the document"
        if p.get("time_sensitive") and p.get("origin") == "local":
            if score > 0.4:
                reason += "; capped because the question asks for current information"
            score = min(score, 0.4)
        return json.dumps({"score": score, "reason": reason})

    # -- query rewriter -----------------------------------------------------
    @staticmethod
    def _rewrite(p: dict) -> str:
        q = p["question"]
        kws = [w for w in re.findall(r"[A-Za-z0-9\.\-\+#]+", q) if w.lower() not in tu.STOPWORDS]
        query = " ".join(kws) or q
        if p.get("mode") == "web" and tu.is_time_sensitive(q) and not re.search(r"20\d\d", q):
            query += f" {date.today().year}"
        return json.dumps({"query": query})

    # -- generator ----------------------------------------------------------
    @staticmethod
    def _generate(p: dict) -> str:
        q, docs = p["question"], p["docs"]
        scored = []
        for i, d in enumerate(docs, 1):
            for s in tu.split_sentences(d):
                scored.append((tu.coverage(q, s), i, s))
        scored.sort(key=lambda x: -x[0])
        best = [x for x in scored[:3] if x[0] >= 0.25]
        if not best:
            return ("The available information is insufficient to answer this question "
                    "reliably.")
        return " ".join(f"{s} [{i}]" for _, i, s in best)

    # -- answer validator ---------------------------------------------------
    @staticmethod
    def _validate(p: dict) -> str:
        answer, context, q = p["answer"], p["context"], p["question"]
        refused = "insufficient" in answer.lower()
        sents = [re.sub(r"\[\d+\]", "", s).strip() for s in tu.split_sentences(answer)]
        sents = [s for s in sents if tu.keyword_set(s)]
        support = [tu.coverage(s, context) for s in sents] or [0.0]
        grounded = min(support) >= 0.6 or refused
        answers = (not refused) and tu.coverage(q, answer) >= 0.3
        score = round((sum(support) / len(support)) * (1.0 if answers else 0.4), 2)
        return json.dumps({"grounded": grounded, "answers_question": answers, "score": score,
                           "issues": "" if grounded and answers else "weak support or no direct answer"})

    # -- evaluation judges --------------------------------------------------
    @staticmethod
    def _judge_relevance(p: dict) -> str:
        a = p["answer"]
        s = 0.1 if "insufficient" in a.lower() else min(1.0, tu.coverage(p["question"], a) * 1.3)
        return json.dumps({"score": round(s, 2)})

    @staticmethod
    def _judge_correctness(p: dict) -> str:
        facts = p.get("facts") or []
        if not facts:
            return json.dumps({"score": 0.0})
        hit = sum(1 for f in facts if tu.coverage(f, p["answer"]) >= 0.6)
        return json.dumps({"score": round(hit / len(facts), 2)})


_llm: Optional[LLMClient] = None


_llm_lock = __import__("threading").Lock()


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        with _llm_lock:
            if _llm is None:
                _llm = LLMClient()
    return _llm
