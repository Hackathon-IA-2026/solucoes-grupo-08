# ARCO, Análise Retrospectiva do Corte

> Refaz, meia hora a meia hora, os cortes de geração eólica e solar (constrained-off) registrados pelo ONS com uma intervenção hipotética (circuito novo na linha que limita a rede, bateria, ou os dois) e calcula quanta energia teria sido recuperada e quanto isso vale (VPL, TIR, payback). Apoia a decisão de investimento em gargalos de transmissão, com premissas visíveis e fonte rastreável em cada resultado.

## Demo

- **Link da demo:** local, com o projeto rodando: painel em http://localhost:5173, API em http://localhost:8000/docs e MCP em http://localhost:8100/mcp.

## Tecnologias utilizadas

- Linguagem: Python 3.14 e TypeScript
- Framework(s): FastAPI, SQLAlchemy e Alembic, Pydantic; React 19 com Vite; fastmcp e Strands Agents
- Banco de dados: PostgreSQL 18 (Docker Compose); DuckDB no preparo da base
- APIs / Serviços externos: Portal de Dados Abertos do ONS; Google Gemini (`gemini-3.8-flash`); GitHub Releases (snapshots dos dados); Langfuse (opcional)

## Como rodar o projeto

```bash
# Clone o repositório
git clone https://github.com/Hackathon-IA-2026/solucoes-grupo-08.git
cd solucoes-grupo-08

# Instale as dependências
cp .env.exemplo .env   # GITHUB_TOKEN enquanto o repositório for privado; GEMINI_API_KEY para a IA
make bootstrap         # dependências, snapshot 2026-09-21 dos dados do ONS, Postgres, esquema e carga

# Rode o projeto
make api       # API em http://localhost:8000
make web       # painel em http://localhost:5173
make agentes   # MCP em http://localhost:8100/mcp (com a API no ar)
make test      # testes
```

## Pré-requisitos

[uv](https://docs.astral.sh/uv/) (instala o Python 3.14), Node 22 com [pnpm](https://pnpm.io/), Docker com Compose e `make`.

## Licença

Este projeto está sob a licença MIT — veja o arquivo [LICENSE](./LICENSE) para mais detalhes. Dados do [Portal de Dados Abertos do ONS](https://dados.ons.org.br/) sob licença CC-BY, Operador Nacional do Sistema Elétrico (ONS). Componentes visuais de terceiros com licença própria em `web/src/lib/cojeev/NOTICES.txt`.
