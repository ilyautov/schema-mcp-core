"""Schema-driven endpoint catalog.

The catalog is the source of truth for what the server can do. Each service
ships a YAML file (`endpoints.yaml`) describing endpoints as records. The
generic executor can call ANY endpoint in the catalog by `operation_id`, and
can also call arbitrary paths not in the catalog (full coverage from day one).

A catalog record:
    operation_id: wb_get_sales          # unique, snake_case, service-prefixed
    section: statistics                  # grouping for browse/search
    method: GET
    host: statistics-api.wildberries.ru  # per-endpoint (WB is multi-host)
    path: /api/v1/supplier/sales         # may contain {placeholders}
    scope: statistics                    # token category / permission needed
    safety: read                         # read | write | destructive
    summary: Sales and returns since a date.
    pagination: lastchangedate           # cursor style or 'none'
    rate_limit: "1 req/min"
    doc: https://dev.wildberries.ru/en/openapi/reports
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import yaml

from .text import concepts, stem, stems, tokens, wants_write


@dataclass
class EndpointSpec:
    operation_id: str
    method: str
    host: str
    path: str
    section: str = "general"
    scope: str = ""
    safety: str = "read"
    summary: str = ""
    pagination: str = "none"
    # dotted path to the array of rows in a response (varies per endpoint):
    # "result.items", "items", "result.rows", "result.operations", ...
    items_path: str = "result.items"
    rate_limit: str = ""
    doc: str = ""
    # Russian (and other) search aliases so RU queries hit English summaries.
    keywords: list[str] = field(default_factory=list)
    # free-form param hints surfaced in describe_method
    params: dict[str, Any] = field(default_factory=dict)
    # business-entity tags, filled at catalog load from EntityIndex (see entities.py)
    entity: list[str] = field(default_factory=list)
    # False, когда путь взят не из официальной спеки, а восстановлен по SDK или
    # документации: вызов стоит считать разведкой, глагол и параметры проверять
    # на живом контуре. Каталоги из OpenAPI оставляют True.
    verified: bool = True

    @property
    def path_params(self) -> list[str]:
        return re.findall(r"\{([^}]+)\}", self.path)

    def render_path(self, values: dict[str, Any]) -> str:
        """Substitute {placeholders}; raises KeyError listing what's missing."""
        out = self.path
        for name in self.path_params:
            if name not in values:
                raise KeyError(name)
            # Percent-encode: an agent-supplied value must not inject extra path
            # segments (../), a query (?) or a fragment (#) into the URL.
            out = out.replace("{" + name + "}", quote(str(values[name]), safe=""))
        return out

    def to_summary_dict(self) -> dict:
        return {
            "operation_id": self.operation_id,
            "section": self.section,
            "method": self.method,
            "path": self.path,
            "safety": self.safety,
            "summary": self.summary,
            "entity": self.entity,
        }


class Catalog:
    """Loaded, searchable set of EndpointSpec records."""

    def __init__(self, specs: list[EndpointSpec], default_host: str = "",
                 entities: Optional[Any] = None):
        self.default_host = default_host
        self.entities: Optional[Any] = entities  # EntityIndex | None — used by search()
        self._by_id: dict[str, EndpointSpec] = {}
        self._stem_index: dict[str, dict[str, set[str]]] = {}
        for s in specs:
            if not s.host:
                s.host = default_host
            if entities is not None:
                s.entity = entities.entity_of(s)
            self._by_id[s.operation_id] = s

    @classmethod
    def from_yaml(cls, path: str | Path, default_host: str = "",
                  entities: Optional[Any] = None) -> "Catalog":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        default_host = raw.get("default_host", default_host)
        specs: list[EndpointSpec] = []
        for rec in raw.get("endpoints", []):
            specs.append(EndpointSpec(**rec))
        return cls(specs, default_host=default_host, entities=entities)

    def get(self, operation_id: str) -> Optional[EndpointSpec]:
        return self._by_id.get(operation_id)

    def all(self) -> list[EndpointSpec]:
        return list(self._by_id.values())

    def sections(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self._by_id.values():
            out[s.section] = out.get(s.section, 0) + 1
        return dict(sorted(out.items()))

    def in_section(self, section: str) -> list[EndpointSpec]:
        return [s for s in self._by_id.values() if s.section == section]

    # Вес поля в оценке. Summary написан для человека, поэтому совпадение в нём
    # значит больше, чем совпадение в пути или в служебном scope.
    _FIELD_WEIGHTS = (("summary", 2.0), ("name", 1.5), ("keywords", 1.0),
                      ("scope", 0.5))

    def _index(self, spec: EndpointSpec) -> dict[str, set[str]]:
        """Основы слов по полям, считаются один раз на метод."""
        cached = self._stem_index.get(spec.operation_id)
        if cached is None:
            cached = {
                "summary": stems(spec.summary),
                "name": stems(spec.operation_id) | stems(spec.path) | stems(spec.section),
                "keywords": stems(" ".join(spec.keywords)),
                "scope": stems(spec.scope),
            }
            self._stem_index[spec.operation_id] = cached
        return cached

    def search(self, query: str, limit: int = 15) -> list[EndpointSpec]:
        """Поиск по каталогу: основы слов, веса полей и доля покрытия запроса.

        Считается не «сколько раз слово встретилось», а «сколько слов запроса
        вообще нашлось»: запрос из двух слов, у которого совпало оба, обязан
        стоять выше того, где совпало одно, даже если это одно встретилось
        трижды. Без этого «поиск вакансий» отдавал случайный метод из двадцати
        с одинаковой оценкой 1.0.
        """
        if self.entities is not None:
            raw_terms, entity_keys = self.entities.expand(query)
        else:
            raw_terms = [t for t in tokens(query)]
            entity_keys = set()
        groups = concepts(raw_terms)
        if not groups and not entity_keys:
            return []
        # «Покажи документы» и «подпиши документ» это разные намерения: во
        # втором случае читающий метод не ответ.
        write_intent = wants_write(raw_terms)
        scored: list[tuple[float, float, EndpointSpec]] = []
        for s in self._by_id.values():
            idx = self._index(s)
            score = 0.0
            hit = 0
            for group in groups:
                best = 0.0
                for field_name, weight in self._FIELD_WEIGHTS:
                    pool = idx[field_name]
                    for term in group:
                        if term in pool:
                            best = max(best, weight)
                        elif len(term) >= 5 and any(h.startswith(term) for h in pool):
                            # «документ» и «документооборот» для спрашивающего
                            # одно и то же. Порог в пять букв: на коротком корне
                            # приставка цепляет чужие слова.
                            best = max(best, weight * 0.75)
                if best:
                    hit += 1
                    score += best
            if entity_keys and set(s.entity) & entity_keys:
                score += 3.0  # раздел, названный своим именем, важнее случайных совпадений
            if not score:
                continue
            if groups:
                score += 2.0 * hit / len(groups)  # покрытие запроса, а не частота
            # Разрыв ничьих: читающий метод полезнее пишущего, когда спрашивают
            # «как посмотреть», а короткий путь общее длинного с тремя {id}.
            # Намерение это не разрыв ничьих, а полноценный сигнал: на «опубликуй
            # вакансию» список опубликованных вакансий совпадает со словами
            # запроса лучше, чем метод публикации, и без надбавки выигрывает его.
            prefers = s.safety != "read" if write_intent else s.safety == "read"
            if prefers:
                score += 1.0
            tie = -0.1 * len(s.path_params)
            scored.append((score, tie, s))
        scored.sort(key=lambda x: (x[0], x[1], -len(x[2].path)), reverse=True)
        return [s for _, _, s in scored[:limit]]
