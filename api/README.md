# api

API HTTP do ARCO em FastAPI. Orquestra: lê a base derivada, chama o motor, persiste simulações e revisões no Postgres e expõe o contrato OpenAPI.

```bash
make api                     # http://localhost:8000, documentação em /docs
uv run pytest api
make contrato                # regenera contratos/openapi.json
```

Configuração pelo `.env` (ver `.env.exemplo`): `DATABASE_URL`, `SNAPSHOT_REPO`.

Rotas: restrições (lista, detalhe, série e ocorrências), premissas e snapshot; simular, salvar e listar simulações e revisões; variações, relatórios e tarefas de exploração. A lista completa está em `/docs` com a API no ar, ou em `contratos/openapi.json`.
