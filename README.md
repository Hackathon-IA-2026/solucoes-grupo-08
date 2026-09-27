# ARCO, Análise Retrospectiva do Corte

> Ferramenta de apoio à decisão de investimento em gargalos de transmissão. O ARCO refaz, meia hora a meia hora, os cortes de geração eólica e solar (constrained-off) que o ONS registrou, com a intervenção que se quer testar: um circuito novo na linha que limita a rede, uma bateria no local, ou os dois. Devolve quanta energia teria sido recuperada e quanto isso vale (VPL, TIR, payback), com as premissas visíveis, editáveis e carimbadas em cada resultado.

Projeto da Equipe GPU para o [Hackathon IA COPPE 2026](https://hackathon-ia.coppe.ufrj.br/), Desafio 1, constrained-off.

## A pergunta que o ARCO responde

> Dado o histórico observado nesta restrição, qual teria sido o resultado técnico e econômico da configuração de investimento informada pelo usuário?

O ARCO não prevê o futuro e não escolhe o melhor investimento. Ele reproduz o passado sob uma hipótese contrafactual e entrega evidência para uma decisão. Os limites do método estão [mais abaixo](#limites-do-método) e aparecem na interface.

## Demo

- **Link da demo:** local, com o projeto rodando (ver [Como rodar o projeto](#como-rodar-o-projeto)). Três portas de entrada para o mesmo cálculo:
  - **painel web:** http://localhost:5173;
  - **API**, com documentação interativa: http://localhost:8000/docs;
  - **MCP do ARCO:** http://localhost:8100/mcp. Conecta a clientes como Claude e ChatGPT; pelo chat, a pessoa cria a simulação e um agente explora variações dela.
- O snapshot da demonstração é o `2026-09-21`, publicado nas releases deste repositório. Sendo a release mais recente, é ele que `make bootstrap` baixa.

## Tecnologias utilizadas

- **Linguagens:** Python 3.14 e TypeScript.
- **Frameworks:**
  - back: FastAPI, SQLAlchemy com Alembic, Pydantic;
  - interface: React 19 com Vite e TanStack Query;
  - agentes: fastmcp e Strands Agents.
- **Banco de dados:** PostgreSQL 18, em Docker Compose. DuckDB para preparar a base a partir dos Parquet do ONS.
- **APIs e serviços externos:**
  - [Portal de Dados Abertos do ONS](https://dados.ons.org.br/), pelo bucket público;
  - Google Gemini (`gemini-3.8-flash`), para extração e relatório;
  - GitHub Releases, como depósito dos snapshots;
  - Langfuse, opcional, para o rastro das chamadas ao modelo;
  - AWS Amplify, para o build da interface publicada (`amplify.yml`);
  - Cloudflare Tunnel, opcional, para expor a API local.

## Pré-requisitos

- [uv](https://docs.astral.sh/uv/), que instala o Python 3.14 sozinho.
- Node 22 e [pnpm](https://pnpm.io/).
- Docker com Compose.
- `make`.
- Opcional:
  - `GEMINI_API_KEY`, para as funções de IA;
  - `GITHUB_TOKEN` com acesso a este repositório, enquanto ele for privado, para baixar o snapshot.

## Como rodar o projeto

```bash
git clone https://github.com/Hackathon-IA-2026/solucoes-grupo-08.git
cd solucoes-grupo-08
cp .env.exemplo .env   # preencha as chaves que tiver; o arquivo explica cada uma

make bootstrap   # dependências, snapshot mais recente, Postgres, esquema, carga e vínculos
make api         # API em http://localhost:8000 (documentação em /docs)
make web         # painel em http://localhost:5173
make agentes     # MCP do ARCO em http://localhost:8100/mcp (exige a API no ar)
make test        # testes de todos os pacotes
```

`make` sem argumento lista todos os alvos.

**Sem acesso às releases**, o snapshot pode ser montado direto do bucket público do ONS, sem token. O nome da pasta vira o `snapshot_id`, então use a data:

```bash
make instalar
uv run arco-dados ingerir --destino dados/snapshots/AAAA-MM-DD
make banco S=AAAA-MM-DD
```

**A IA e a chave.** O `make bootstrap` prepara a base só com a regra determinística, sem chave e sem rede além do download. Com `GEMINI_API_KEY`:

- `uv run arco-dados preparar --com-modelo --snapshot dados/snapshots/<data>` manda ao modelo os textos de restrição que a regra não leu, e o vínculo proposto passa pela mesma conferência contra o cadastro;
- a mesma chave liga o relatório da simulação e o explorador por modelo.

Sem ela, o cálculo, o painel, a API e o MCP funcionam; as restrições que só o modelo lê ficam fora do ranking.

## Como o repositório está organizado

| Pasta | O que é |
|---|---|
| `motor/` | Cálculo puro e determinístico: série de cortes + configuração + premissas → resultado técnico e financeiro. Sem I/O. |
| `dados/` | Ingestão dos dados abertos do ONS, snapshots datados, base derivada e vínculos entre texto de restrição e equipamento |
| `api/` | API HTTP (FastAPI), persistência das simulações e revisões, geração do contrato OpenAPI |
| `contratos/` | `openapi.json` gerado pela API. Fronteira entre backend e interface |
| `web/` | Painel (React, TypeScript, Vite) com cliente gerado do contrato |
| `ia/` | Extração de equipamentos dos textos de restrição e relatório da simulação, sempre conferidos por código |
| `agentes/` | MCP do ARCO e o explorador de variações. Fala com a API por HTTP |
| `infra/` | Docker Compose com o Postgres e scripts do túnel |

Direção de dependência: `api → dados → motor`; `ia → motor`; `agentes → ia → motor`, e `agentes` fala com a `api` por HTTP. Cada pacote tem o próprio `README.md`.

## Para quem avalia: execução técnica e uso de dados

**Maturidade técnica.** Solução funcional de ponta a ponta: painel, API, MCP e explorador por agente.

- A CI roda em todo PR:
  - Python: ruff, pyright, pytest sobre Postgres 18, migrations do zero e conferência de que o contrato OpenAPI não derivou;
  - interface: oxlint, tsc, vitest e build.
- O motor tem testes de propriedade (Hypothesis) para os invariantes do cálculo: a energia evitada nunca passa da cortada em nenhum intervalo, mais limite nunca recupera menos, e a combinada nunca recupera menos que o equipamento sozinho. Há também casos de ouro com resultado conhecido.

**Uso dos dados.** Os dados do ONS entram como publicados, sem planilha intermediária:

- corte eólico e solar por conjunto, a cada meia hora;
- cadastro de linhas, transformadores e subestações;
- CMO semi-horário.

A lista está em `dados/src/arco_dados/fontes.py`.

**Integração.**

- **Com o ONS:** o ARCO lê o mesmo bucket público que o ONS mantém, no formato original.
- **Com outros sistemas:** a API segue um contrato OpenAPI versionado (`contratos/openapi.json`), de onde sai o cliente tipado da interface. Qualquer sistema consome o cálculo pela mesma fronteira.
- **Com clientes de IA:** o MCP do ARCO usa o mesmo protocolo do MCP de dados abertos do ONS. Um agente pode falar com os dois.
- **Com quem decide o investimento:** os resultados são as métricas desse trabalho, com fluxo de caixa exposto: VPL, TIR, payback simples e descontado, custo por MWh.

**Segurança e conformidade.**

- Nenhum segredo no repositório: `.env` fica fora do git, e `.env.exemplo` documenta cada variável.
- O ARCO usa só dado público, sob CC-BY e com atribuição, e não trata dado pessoal: a simulação não guarda autor.
- A API e o MCP não têm autenticação, por decisão: o uso previsto é local. O CORS vem restrito à interface local.
- Para expor a API num endereço fixo, `infra/README.md` descreve como fechá-la com Cloudflare Access, sem mexer no código.

**Rastreabilidade.** Todo número tem origem que se confere.

- **Snapshot datado e imutável.** Cada cópia do dado do ONS é publicada em release com o sha256 de cada arquivo e os dicionários de dados da versão usada. O download confere cada hash, e nenhum cálculo lê o bucket ao vivo.
- **Cada simulação grava o que a produziu:** `snapshot_id`, `metodo_versao`, parâmetros, premissas e avisos.
- **Revisão nunca se apaga.** Recalcular cria revisão nova ligada à anterior.
- **Toda premissa tem fonte e status** (`nao_verificada`, `proposta`, `validada`), e `validada` exige autor e data. O registro é `motor/src/arco_motor/premissas.py`, e o que não está validado aparece como tal na tela.
- **A IA não produz número.**
  - O equipamento que o modelo extrai de um texto só vira vínculo se o nome estiver no texto e se casar, por código, com o cadastro do snapshot.
  - O relatório é barrado se algum número da prosa não existir na parte calculada.
  - Modelo e versão do prompt ficam gravados em cada extração e em cada relatório.

## Limites do método

1. **O resultado é contrafactual.** Diz o que teria acontecido sob as hipóteses informadas se o passado se repetisse com a intervenção disponível. Não é previsão.
2. **Associação não é causalidade.** A associação histórica entre o texto da restrição e um equipamento não prova, sozinha, causalidade física nem sensibilidade unitária. A conversão entre reforço e corte recuperável é premissa visível e editável.
3. **O histórico pode não representar o futuro.** Rede, geração, carga, preços e regulação mudam. Vários gargalos têm obras previstas.
4. **Energia recuperável não é receita capturável.** O valor atribuído à energia é premissa, não contrato.
5. **A simulação apoia a decisão, não a substitui.** Não substitui estudo elétrico, regulatório nem de engenharia.

## Dados

Todos os dados vêm do [Portal de Dados Abertos do ONS](https://dados.ons.org.br/) e são publicados sob licença [CC-BY](http://www.opendefinition.org/licenses/cc-by). O ONS revisa arquivos depois de publicados, então o ARCO trabalha sobre snapshots datados e imutáveis. Detalhes em [dados/README.md](dados/README.md).

Atribuição: Operador Nacional do Sistema Elétrico (ONS), Portal de Dados Abertos. Conjuntos usados: restrição de operação por constrained-off; cadastro de linhas, transformadores e subestações; custo marginal de operação semi-horário.

## Créditos de terceiros

Parte dos componentes visuais do painel vem do Cojeev UI (MIT), com trechos adaptados do ThreeUI (MIT) e geometria de ícones do lucide (ISC). Os avisos de licença estão em `web/src/lib/cojeev/NOTICES.txt`.

## Equipe

| Pessoa | Papel na inscrição |
|---|---|
| Guilherme Vasconcellos Marcelino | Especialista temático |
| Luciano Bernardino | Scrum Master / Gerente de projeto |
| Brener Silva | Desenvolvedor |
| Luciano Chinilato | Desenvolvedor |
| Thomas Farias Viana | Desenvolvedor |

## Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](./LICENSE) para mais detalhes. Os dados do ONS estão sob CC-BY, com a atribuição acima.
