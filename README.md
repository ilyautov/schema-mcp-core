# schema-mcp-core

Основа для MCP-серверов над российскими деловыми API. Сам по себе ничего не
подключает: сервер приносит каталог методов (`endpoints.yaml`) и тонкий
`server.py`, всё остальное берёт отсюда.

Так устроены [hh-mcp-ru](https://github.com/ilyautov/hh-mcp-ru),
[diadoc-mcp-ru](https://github.com/ilyautov/diadoc-mcp-ru),
[sbis-mcp-ru](https://github.com/ilyautov/sbis-mcp-ru),
[chestny-znak-mcp-ru](https://github.com/ilyautov/chestny-znak-mcp-ru) и
[vk-mcp-ru](https://github.com/ilyautov/vk-mcp-ru).

## Что внутри

| модуль | зачем |
|---|---|
| `registry` | каталог методов из YAML: поиск словами, описание, пагинация |
| `safety` | класс доступа read / write / destructive |
| `client` | асинхронный HTTP: авторизация, повтор на 429, пагинация, белый список доменов |
| `credentials` | ключи на несколько кабинетов, файл вне репозитория с правами 600 |
| `tools` | готовый набор инструментов MCP: поиск, описание, вызов, кабинеты |
| `doctor` | отчёт «взлетит ли эта установка», список сервисов задаёт вызывающий |
| `paginate` | выкачать все страницы одним вызовом, только для чтения |
| `entities`, `workflows` | карта сущностей и готовые сценарии, если сервер их приносит |

## Зачем отдельный пакет

Ядро это 2 200 строк, а сервер поверх него 66. Пять серверов, живущих
отдельными репозиториями, иначе несли бы пять копий одного кода, и правка
безопасности в одном месте оставляла бы четыре непочиненных.

## Минимальный сервер

```python
from mcp.server.fastmcp import FastMCP
from schema_mcp_core.client import MarketplaceClient, ServiceConfig
from schema_mcp_core.registry import Catalog
from schema_mcp_core.tools import register_generic_tools

catalog = Catalog.from_yaml(Path(__file__).parent / "endpoints.yaml")
config = ServiceConfig(service="hh", base_url="https://api.hh.ru", ...)
mcp = FastMCP("hh-mcp-ru")
register_generic_tools(mcp, prefix="hh", catalog=catalog, client_factory=...)
```

Живой пример с авторизацией и кабинетами лежит в любом из пяти серверов выше.

## Что ядро НЕ делает

Не ходит в сеть само, не хранит ключи в репозитории, не пишет в сервис без
подтверждения: методы класса `write` и `destructive` требуют явного согласия
на стороне вызова.

## Установка

```
pip install schema-mcp-core
```

## Кто это сделал

[Илья Утов](https://github.com/ilyautov), лаборатория
[AI Frontier](https://aifrontier.tech). На этом ядре собраны
[**business-mcp-ru**](https://github.com/ilyautov/business-mcp-ru) и пять его
серверов: hh.ru, VK, Диадок, СБИС, Честный знак.

Остальные проекты одним списком, разобранные по назначению:
[ilyautov.github.io](https://ilyautov.github.io/).

MIT.
