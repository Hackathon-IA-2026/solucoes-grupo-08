# ia

As funções do ARCO que usam modelo de linguagem. **Não são acessório:** o vínculo entre o texto da restrição e o cadastro só existe porque alguém lê texto livre de operador, e sem vínculo não há ranking nem simulação. Sem `GEMINI_API_KEY` o que quebra é a construção da base, não um enfeite.

1. `extrair`: lê um texto de restrição do ONS e devolve os equipamentos citados, com tensão, terminais, circuito e papel, tipados em Pydantic. Só é chamado onde a regra determinística **não leu nada**: ela resolve 29 das 64 restrições e 92,9% da energia, é grátis e não varia.
   Duas conferências, e é delas que vem a confiança, não do modelo: todo nome devolvido tem de estar no texto de entrada, e o equipamento passa pelo **mesmo `casar()`** que confere o regex, contra o cadastro do snapshot.
2. `relatorio`: o relatório da simulação. `escrever_prosa` é o **analista**: lê a parte calculada por código — cabeçalho, revisões, diferenças, sensibilidade observada, fronteiras, premissas expostas — e escreve cinco seções de prosa, em uma chamada. `verificar` é o **verificador**, código puro: todo número da prosa tem de existir na parte calculada, com a mesma unidade e tolerância de dois algarismos significativos; nenhuma forma de recomendação passa; cada seção cabe no seu limite. Falhou um, o relatório fica `barrado`.

Toda ida ao modelo passa por `chamada.chamar`, que escolhe modelo, esforço e versão do prompt pelo papel (`extrator`, `analista`) em `config.py`, retenta só erro de rede, 429 e 5xx, dá uma segunda chance a resposta fora do esquema e abre um span OpenTelemetry por chamada. Com `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY`, `configurar_rastro()` manda o rastro ao Langfuse Cloud; sem elas, ao console.

Modelo em uso: `gemini-3.8-flash` nos dois papéis, gravado em cada extração e em cada relatório com a versão do prompt — é o que permite reprocessar só o que veio do modelo antigo quando um dos dois mudar.
