"""Shared environment configuration and LangChain provider adapters."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from saaf.knowledge.retrieval import DEFAULT_MODEL, Embeddings

OPENAI_CHAT_MODEL = "gpt-4.1-mini"
GEMINI_CHAT_MODEL = "gemini-3.1-flash-lite"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"
RATE_LIMIT_AR = "بلغت خدمة الذكاء الاصطناعي حد الاستخدام مؤقتاً. حاول مرة أخرى لاحقاً."


def is_rate_limited(error: BaseException) -> bool:
    """Recognize quota errors including failures wrapped by retrieval."""
    seen = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if (getattr(current, "status_code", None) == 429
                or getattr(current, "code", None) == 429
                or getattr(current, "status", None) == "RESOURCE_EXHAUSTED"):
            return True
        current = current.__cause__ or current.__context__
    return False


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str

    def require_key(self) -> str:
        names = ("OPENAI_API_KEY",) if self.provider == "openai" else (
            "GOOGLE_API_KEY", "GEMINI_API_KEY",
        )
        for name in names:
            key = os.getenv(name, "").strip()
            if key:
                return key
        raise ValueError(f"set {' or '.join(names)} for {self.provider}")


def load_environment() -> None:
    load_dotenv(Path(".env"), override=False)


def _config(role: str, openai_default: str, gemini_default: str) -> ProviderConfig:
    variable = f"SAAF_{role}_PROVIDER"
    provider = os.getenv(variable, "").strip().lower() or "openai"
    if provider not in {"openai", "gemini"}:
        raise ValueError(f"{variable} must be openai or gemini")
    default = openai_default if provider == "openai" else gemini_default
    return ProviderConfig(provider, os.getenv(f"SAAF_{role}_MODEL", "").strip() or default)


def embedding_config() -> ProviderConfig:
    return _config("EMBEDDING", DEFAULT_MODEL, GEMINI_EMBEDDING_MODEL)


def chat_config() -> ProviderConfig:
    return _config("CHAT", OPENAI_CHAT_MODEL, GEMINI_CHAT_MODEL)


def build_embeddings(config: ProviderConfig) -> Embeddings:
    key = config.require_key()
    if config.provider == "openai":
        return OpenAIEmbeddings(model=config.model, api_key=key, check_embedding_ctx_length=False)
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(model=config.model, google_api_key=key, vertexai=False)


def build_structured_chat(config: ProviderConfig, schema: type):
    key = config.require_key()
    if config.provider == "openai":
        return ChatOpenAI(model=config.model, api_key=key).with_structured_output(
            schema, method="json_schema", strict=True,
        )
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=config.model, google_api_key=key, vertexai=False,
    ).with_structured_output(schema, method="json_schema")
