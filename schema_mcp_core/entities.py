# core/entities.py
"""Business-entity taxonomy: makes the catalog legible to the agent/LLM.

Loads a curated `entities.yaml` and exposes three things the tools use:
- entity_of(spec)  -> which business entities a method belongs to
- expand(query)    -> (cleaned tokens, matched entity keys) for smarter search
- stopwords        -> RU/EN noise words stripped from queries

Every method degrades gracefully: a missing/broken yaml yields an empty index,
and callers fall back to the pre-entity behaviour.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .text import stem, tokens as _tokens

_DEFAULT_PATH = Path(__file__).resolve().parent / "entities.yaml"

# RU/EN filler words that carry no routing signal.
STOPWORDS: set[str] = {
    "дай", "дайка", "ка", "покажи", "показать", "мне", "мой", "моя", "мои", "что",
    "какие", "какой", "сколько", "по", "на", "с", "со", "в", "во", "и", "а",
    "у", "за", "до", "от", "как", "есть", "это", "пожалуйста", "ну",
    "please", "show", "get", "list", "all", "me", "my", "the", "a", "of", "for",
}


class EntityIndex:
    def __init__(self, entities: list[dict[str, Any]]):
        self.entities = entities
        self.stopwords = STOPWORDS
        # synonym phrase -> entity key (lowercased)
        self._syn: dict[str, str] = {}
        # Односложные синонимы сверяются ОСНОВОЙ, а не буквой в букву: раздел
        # называется «Вакансии», спрашивают «вакансию», и без стемминга раздел
        # не находится ни разу.
        self._syn_stem: dict[str, str] = {}
        for e in entities:
            self._syn.setdefault(e["key"].lower(), e["key"])
            self._syn_stem.setdefault(stem(e["key"]), e["key"])
            for syn in e.get("synonyms", []):
                low = syn.lower()
                self._syn.setdefault(low, e["key"])
                if " " not in low:
                    # Первый победил: файл отсортирован по числу методов, и
                    # «документы» должны вести в раздел документов, а не в
                    # полку файлов, которая упоминает то же слово в названии.
                    self._syn_stem.setdefault(stem(low), e["key"])

    @classmethod
    def load(cls, path: str | Path | None = None) -> "EntityIndex":
        p = Path(path) if path else _DEFAULT_PATH
        try:
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            entities = raw.get("entities", [])
            if not isinstance(entities, list):
                entities = []
        except Exception:  # noqa: BLE001 — never break the server on a bad file
            entities = []
        return cls(entities)

    def entity_of(self, spec: Any) -> list[str]:
        """Entity keys for a spec via lowercase section-name substring match."""
        section = (getattr(spec, "section", "") or "").lower()
        if not section:
            return []
        keys: list[str] = []
        for e in self.entities:
            if any(sub in section for sub in e.get("match", [])):
                keys.append(e["key"])
        return keys

    def expand(self, query: str) -> tuple[list[str], set[str]]:
        """Return (cleaned tokens, matched entity keys).

        - cleaned tokens: lowercased, stopwords removed (still feed token search).
        - entity keys: any synonym phrase contained in the query maps to its entity.
        """
        q = query.lower()
        tokens = [t for t in _tokens(q) if t not in self.stopwords]
        keys: set[str] = set()
        for syn, key in self._syn.items():
            if " " in syn and syn in q:
                keys.add(key)
        for t in tokens:
            key = self._syn_stem.get(stem(t))
            if key:
                keys.add(key)
        return tokens, keys
