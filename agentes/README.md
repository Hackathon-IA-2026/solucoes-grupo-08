# agentes

O MCP do ARCO e o explorador de variações. Roda na mesma máquina da API e fala com ela por HTTP (`api.py`): não importa `arco_api` e não toca o banco.

```bash
make agentes                                              # MCP em http://localhost:8100, com a API no ar
uv run arco-agentes explorar <simulacao_id> "<pedido>"    # uma exploração pela CLI
uv run arco-agentes explorar <simulacao_id> "<pedido>" --referencia   # a mesma, sem modelo
uv run pytest agentes
```

## MCP do ARCO

`servidor.py`, em `fastmcp`, com ferramentas escritas à mão e dois perfis no mesmo processo:

- `/mcp` é o **chat**: consultar restrições e simulações, conferir e criar simulação, disparar e acompanhar a exploração, ler o relatório. Conecta a Claude, ChatGPT e outros clientes MCP. `listar_restricoes`, `conferir_simulacao` e `explorar_variacoes` devolvem cartões que o cliente desenha na conversa (`interfaces/`).
- `/explorador/mcp` é o **explorador**: consultas, disparo de um lote de variações e encerramento.

**Nenhum número nasce aqui.** As ferramentas repassam o que a API calculou, resumido e formatado (`resumos.py`); conta e regra de negócio são da API e do motor.

## Explorador

`explorador.py`: laço de rodadas em código, uma decisão por rodada. Cada variação muda uma alavanca de uma revisão e vira revisão nova pela API, que monta pelo motor. Dois decisores:

- `DecisorDoModelo`: Strands Agents com Gemini (`GEMINI_API_KEY`).
- `ArvoreDeReferencia` (`referencia.py`): tudo predefinido, sem modelo. É a linha de base contra a qual o modelo se justifica.

Quem dispara a exploração é a API: ao criar a tarefa, ela chama este processo em `ARCO_AGENTES_URL`. `tests/avaliacao/` é o conjunto de avaliação do explorador, com o modelo e a árvore sobre os mesmos casos.

## Configuração

Pelo `.env` da raiz (ver `.env.exemplo`): `ARCO_API_URL`, `ARCO_MCP_PORTA`, `ARCO_PAINEL_URL` e `GEMINI_API_KEY`. O MCP não tem autenticação, como a API: para expor pela internet, ver `infra/README.md`.
