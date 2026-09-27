# ARCO. Alvos de desenvolvimento. `make` lista todos.
.RECIPEPREFIX := >
.DEFAULT_GOAL := ajuda
SHELL := /bin/bash

S ?= latest
# Pasta do snapshot: o `latest` vira o nome gravado por `make snapshot` em ultimo.txt.
SNAP = $(if $(filter latest,$(S)),$(shell cat dados/snapshots/ultimo.txt 2>/dev/null),$(S))

ajuda: ## lista os alvos
> @grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n", $$1, $$2}'

instalar: ## dependências Python (uv) e web (pnpm)
> uv sync --all-packages
> pnpm -C web install

COMPOSE := docker compose $(if $(wildcard .env),--env-file .env) -f infra/docker-compose.yml

db: ## sobe o Postgres em docker e espera ficar saudável (porta: ARCO_PG_PORTA no .env)
> $(COMPOSE) up -d --wait

db-parar: ## para o Postgres
> $(COMPOSE) down

snapshot: ## baixa o snapshot S (padrão: o mais recente) das releases e confere os hashes
> uv run arco-dados baixar --tag $(S) --destino dados/snapshots

ingerir: ## baixa do bucket do ONS para dados/snapshots/novo (o job diário faz o mesmo)
> uv run arco-dados ingerir --destino dados/snapshots/novo

preparar: ## snapshot → artefatos em dados/derivado/ (DuckDB, não toca banco)
> @test -n "$(SNAP)" || { echo "Nenhum snapshot em dados/snapshots. Rode make snapshot."; exit 1; }
> uv run arco-dados preparar --snapshot dados/snapshots/$(SNAP)

banco: db preparar migrar ## do zero ao banco pronto: esquema, carga do snapshot S e vínculos validados
> $(MAKE) carregar A=dados/derivado/$(SNAP)
> $(MAKE) semear

bootstrap: instalar snapshot banco ## prepara a máquina inteira, do clone à API com dado
> @echo "Pronto. make api sobe a API; make web, a interface."

api: ## API em http://localhost:8000 (docs em /docs)
> uv run uvicorn arco_api.main:app --reload --port 8000

agentes: ## MCP do ARCO em http://localhost:8100/mcp (chat) e /explorador/mcp; exige a API no ar
> uv run arco-agentes servir

web: ## interface em http://localhost:5173
> pnpm -C web dev

test: ## todos os testes
> uv run pytest
> pnpm -C web test

lint: ## ruff, pyright, oxlint e tsc
> uv run ruff check .
> uv run ruff format --check .
> uv run pyright
> pnpm -C web lint
> pnpm -C web typecheck

formatar: ## formata Python e web
> uv run ruff format .
> uv run ruff check --fix .
> pnpm -C web format

migrar: ## sobe o esquema do banco até a última migration
> uv run --directory api alembic upgrade head

carregar: ## artefatos do preparo → banco (A=pasta dos artefatos)
> uv run python -m arco_api.comandos carregar --artefatos $(A)

vinculos: ## lista os vínculos pendentes de conferência
> uv run python -m arco_api.comandos vinculos

semear: ## aplica os vínculos validados do CSV versionado
> uv run python -m arco_api.comandos semear

exportar-vinculos: ## grava os validados no CSV versionado, para entrar por PR
> uv run python -m arco_api.comandos exportar

contrato: ## regenera contratos/openapi.json e o cliente TypeScript do web a partir da API
> uv run python -m arco_api.contrato
> pnpm -C web run gerar-cliente

tunel: ## expõe a API na internet por túnel efêmero da Cloudflare, URL sorteada (PORTA=8000)
> @PORTA=$(or $(PORTA),8000) infra/tunel.sh

tunel-fixo: ## o mesmo, na URL fixa do subdomínio configurado no painel (exige a API no ar)
> @PORTA=$(or $(PORTA),8000) infra/tunel-fixo.sh

servidor: ## sobe a API, o MCP e o túnel da URL fixa juntos; um Ctrl+C derruba os três
> @PORTA=$(or $(PORTA),8000) infra/servidor.sh

.PHONY: ajuda instalar db db-parar snapshot ingerir preparar banco migrar carregar vinculos semear exportar-vinculos bootstrap api agentes web test lint formatar contrato tunel tunel-fixo servidor
