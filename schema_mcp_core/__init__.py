"""Shared core for schema-driven MCP servers over Russian business APIs.

Service-agnostic building blocks; a server package supplies only a catalog
(``endpoints.yaml``) and a thin ``server.py``:

- errors:      unified error envelope
- safety:      read/write/destructive gating
- registry:    schema-driven endpoint catalog (loaded from YAML)
- client:      async HTTP client with auth, 429 backoff, pagination
- credentials: multi-cabinet key store outside the repo
- tools:       the generic MCP tool set (search/describe/call/cabinets)
- doctor:      "can this install actually work" report
"""

__version__ = "0.1.0"
