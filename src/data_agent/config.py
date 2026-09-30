"""Explicit environment loading and application configuration."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def load_environment() -> None:
    """Load optional local settings at application startup, preserving process values."""
    load_dotenv()


def development_cors_origins() -> list[str]:
    """Optional explicit origins from the host process; empty means no cross-origin access."""
    origins = [origin.strip() for origin in os.environ.get("DATA_AGENT_CORS_ORIGINS", "").split(",") if origin.strip()]
    if "*" in origins:
        raise ValueError("DATA_AGENT_CORS_ORIGINS requires explicit development origins")
    return origins


def database_config() -> dict[str, str]:
    """Read the existing DB_* settings only when database work is requested."""
    return {
        "host": os.environ["DB_HOST"],
        "port": os.environ["DB_PORT"],
        "database": os.environ["DB_DATABASE"],
        "user": os.environ["DB_USERNAME"],
        "password": os.environ["DB_PASSWORD"],
    }


def default_data_root() -> Path:
    """Preserve repository-relative extraction in a checkout; use cwd when installed."""
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "pyproject.toml").is_file() and (checkout / "data").is_dir():
        return checkout
    return Path.cwd()


def policy_chroma_path() -> Path:
    """Resolve policy persistence without creating files or loading the environment."""
    root = Path(os.environ.get("POLICY_STORAGE_ROOT") or "var/policy").expanduser()
    if not root.is_absolute():
        root = default_data_root() / root
    return root.resolve() / "chroma"


def etl_output_path(data_root: Path) -> Path:
    """Resolve against the application root, never a tool-supplied directory."""
    root = Path(data_root).expanduser()
    if not root.is_absolute():
        raise ValueError('ETL application data root must be absolute')
    configured = Path(os.environ.get('ETL_STORAGE_ROOT') or 'var/etl').expanduser()
    return ((root / configured) if not configured.is_absolute() else configured).resolve() / 'outputs'


@dataclass(frozen=True)
class PolicyIngestionSettings:
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chunk_tokens: int = 600
    overlap_tokens: int = 80
    embedding_batch_size: int = 64
    max_file_bytes: int = 10 * 1024 * 1024
    max_text_chars: int = 2_000_000
    max_pages: int = 200
    max_chunks: int = 2000
    parser_timeout_seconds: int = 30
    encoding_name: str = "cl100k_base"

    def __post_init__(self):
        for name in ("embedding_dimensions", "chunk_tokens", "embedding_batch_size", "max_file_bytes",
                     "max_text_chars", "max_pages", "max_chunks", "parser_timeout_seconds"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"Invalid policy setting: {name}")
        if type(self.overlap_tokens) is not int or not 0 <= self.overlap_tokens < self.chunk_tokens or self.chunk_tokens > 8000:
            raise ValueError("Invalid chunk size/overlap")
        if not self.embedding_model.strip() or self.embedding_batch_size * self.chunk_tokens > 250_000:
            raise ValueError("Invalid embedding configuration")

    @property
    def chunking_version(self):
        return f"sections-v1:{self.encoding_name}:{self.chunk_tokens}:{self.overlap_tokens}"


def policy_ingestion_settings():
    return PolicyIngestionSettings(
        embedding_model=os.environ.get("POLICY_EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_dimensions=int(os.environ.get("POLICY_EMBEDDING_DIMENSIONS", "1536")),
        chunk_tokens=int(os.environ.get("POLICY_CHUNK_TOKENS", "600")),
        overlap_tokens=int(os.environ.get("POLICY_CHUNK_OVERLAP", "80")),
        embedding_batch_size=int(os.environ.get("POLICY_EMBEDDING_BATCH_SIZE", "64")))


def policy_retrieval_top_k():
    value = int(os.environ.get("POLICY_RETRIEVAL_TOP_K", "5"))
    if not 1 <= value <= 100:
        raise ValueError("POLICY_RETRIEVAL_TOP_K must be between 1 and 100")
    return value
