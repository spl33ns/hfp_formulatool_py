from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


class OperatorConfigError(ValueError):
    pass


REQUIRED_KEYS = {"AND", "OR", "EQ", "NEQ", "LPAREN", "RPAREN"}


DEFAULT_CONFIG = {
    "AND": ["&", "AND"],
    "OR": ["|", "OR"],
    "NOT": ["!", "NOT"],
    "NEQ": ["<>", "!="],
    "EQ": ["="],
    "LPAREN": ["("],
    "RPAREN": [")"],
}


def _default_config_path() -> Path:
    # core/operator_config.py -> project root -> config/operators.json
    return Path(__file__).resolve().parents[1] / "config" / "operators.json"


def _is_word_operator(token: str) -> bool:
    # Treat purely alphabetic tokens as keywords that require word boundaries (e.g. AND/OR/NOT).
    return token.isalpha()


def _normalize_token(token: str) -> str:
    token = token.strip()
    # Keyword operators are matched case-insensitively.
    if _is_word_operator(token):
        return token.upper()
    return token


@dataclass(frozen=True)
class OperatorConfig:
    """Validated operator configuration loaded from JSON.

    `mapping` contains normalized tokens (keywords uppercased, symbols unchanged).
    """

    mapping: dict[str, tuple[str, ...]]
    source_path: Path

    def summary(self) -> dict[str, list[str]]:
        # For logging/debugging only (keep it small).
        keys = ["AND", "OR", "NOT", "EQ", "NEQ", "LPAREN", "RPAREN"]
        return {k: list(self.mapping.get(k, ())) for k in keys if k in self.mapping}

    @property
    def expression_ops(self) -> list[tuple[str, str, bool]]:
        """Return [(token, type, is_word)] sorted by longest-match-first."""
        ops: list[tuple[str, str, bool]] = []
        for token in self.mapping.get("LPAREN", ()):
            ops.append((token, "LPAREN", False))
        for token in self.mapping.get("RPAREN", ()):
            ops.append((token, "RPAREN", False))
        for token in self.mapping.get("NOT", ()):
            ops.append((token, "NOT", _is_word_operator(token)))
        for token in self.mapping.get("AND", ()):
            ops.append((token, "AND", _is_word_operator(token)))
        for token in self.mapping.get("OR", ()):
            ops.append((token, "OR", _is_word_operator(token)))
        ops.sort(key=lambda item: len(item[0]), reverse=True)
        return ops

    @property
    def eq_ops(self) -> tuple[str, ...]:
        return tuple(sorted(self.mapping.get("EQ", ()), key=len, reverse=True))

    @property
    def neq_ops(self) -> tuple[str, ...]:
        return tuple(sorted(self.mapping.get("NEQ", ()), key=len, reverse=True))


_CACHE: dict[str, OperatorConfig] = {}


def load_operator_config(path: Path | None = None, *, log_extra: dict[str, str] | None = None) -> OperatorConfig:
    """Load and validate operator config.

    Special logs:
    - CONFIG_LOAD_START / CONFIG_LOAD_OK / CONFIG_LOAD_FAILED
    """
    resolved = (path or _default_config_path()).resolve()
    cache_key = str(resolved)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    if log_extra:
        logger.info("CONFIG_LOAD_START: path=%s", resolved, extra=log_extra)
    else:
        logger.info("CONFIG_LOAD_START: path=%s", resolved)

    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:
        if log_extra:
            logger.error("CONFIG_LOAD_FAILED: path=%s error=%s", resolved, exc, exc_info=True, extra=log_extra)
        else:
            logger.error("CONFIG_LOAD_FAILED: path=%s error=%s", resolved, exc, exc_info=True)
        raise OperatorConfigError(f"CONFIG_LOAD_FAILED: could not load operator config at {resolved}") from exc

    if not isinstance(raw, dict):
        msg = "CONFIG_LOAD_FAILED: operator config JSON must be an object/dict"
        if log_extra:
            logger.error("%s path=%s", msg, resolved, extra=log_extra)
        else:
            logger.error("%s path=%s", msg, resolved)
        raise OperatorConfigError(msg)

    missing = REQUIRED_KEYS.difference(raw.keys())
    if missing:
        msg = f"CONFIG_LOAD_FAILED: missing required keys: {sorted(missing)}"
        if log_extra:
            logger.error("%s path=%s", msg, resolved, extra=log_extra)
        else:
            logger.error("%s path=%s", msg, resolved)
        raise OperatorConfigError(msg)

    mapping: dict[str, tuple[str, ...]] = {}
    seen: dict[str, str] = {}

    def _iter_tokens(value: object) -> Iterable[str]:
        if not isinstance(value, list):
            raise OperatorConfigError("CONFIG_LOAD_FAILED: operator values must be lists of strings")
        for item in value:
            if not isinstance(item, str):
                raise OperatorConfigError("CONFIG_LOAD_FAILED: operator values must be strings")
            token = _normalize_token(item)
            if not token:
                raise OperatorConfigError("CONFIG_LOAD_FAILED: operator token must not be empty")
            yield token

    try:
        for key, value in raw.items():
            tokens = tuple(_iter_tokens(value))
            # Don't enforce NOT as required, but if present it must not be empty.
            if key in REQUIRED_KEYS and not tokens:
                raise OperatorConfigError(f"CONFIG_LOAD_FAILED: '{key}' must have at least one token")
            if tokens:
                mapping[key] = tokens
                for token in tokens:
                    if token in seen and seen[token] != key:
                        raise OperatorConfigError(
                            f"CONFIG_LOAD_FAILED: duplicate token '{token}' in '{key}' and '{seen[token]}'"
                        )
                    seen[token] = key
    except OperatorConfigError as exc:
        if log_extra:
            logger.error("CONFIG_LOAD_FAILED: path=%s error=%s", resolved, exc, extra=log_extra)
        else:
            logger.error("CONFIG_LOAD_FAILED: path=%s error=%s", resolved, exc)
        raise

    config = OperatorConfig(mapping=mapping, source_path=resolved)
    _CACHE[cache_key] = config

    summary = config.summary()
    if log_extra:
        logger.info("CONFIG_LOAD_OK: path=%s summary=%s", resolved, summary, extra=log_extra)
    else:
        logger.info("CONFIG_LOAD_OK: path=%s summary=%s", resolved, summary)

    return config

