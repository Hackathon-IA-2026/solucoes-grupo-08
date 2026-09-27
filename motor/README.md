# motor

Pacote Python puro que responde a pergunta do ARCO: dada a série de cortes de uma restrição, uma configuração de investimento e um conjunto de premissas, qual teria sido o resultado técnico e financeiro.

- Sem I/O, sem banco, sem rede, sem relógio. Tudo entra por parâmetro.
- Determinístico: mesma entrada, mesmo resultado.
- Toda regra questionável é uma `Premissa` com fonte e status (`premissas.py`).
- `METODO_VERSAO` (`versao.py`) identifica o conjunto de regras e vai carimbado em todo resultado.

## Estrutura

| Módulo | Papel |
|---|---|
| `tipos.py` | Contrato de entrada e saída: série, configurações, resultado |
| `premissas.py` | `Premissa`, `Premissas` e os valores padrão, com fonte e status |
| `cenarios.py` | Valores iniciais por cenário (conservador, referência, otimista) |
| `ocorrencias.py` | Agrupamento dos intervalos de corte em ocorrências |
| `equipamento.py` | Efeito da adição de circuito sobre a série de corte |
| `bateria.py` | Despacho da bateria sobre o corte residual |
| `economia.py` | Fluxo de caixa anual, VPL, TIR, payback e custo por MWh |
| `simular.py` | Orquestra as três modalidades e monta o `Resultado` |
| `montar.py` | A configuração inteira de uma simulação nova, a partir da alavanca |
| `variacao.py` | Variação de uma revisão: uma alavanca muda, o resto fica |
| `diagnosticos.py` | O que o explorador lê para decidir a próxima variação |
| `relatorio.py` | A parte calculada do relatório da simulação |
| `versao.py` | `METODO_VERSAO` |

## Testes

Os invariantes do cálculo estão em `tests/test_invariantes.py`, como testes de propriedade (Hypothesis) e casos de ouro.

```bash
uv run pytest motor
uv run pyright motor
```
