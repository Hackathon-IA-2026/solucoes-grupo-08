"""Versão do método de cálculo.

Sobe quando o resultado muda para a mesma entrada (regra nova, estratégia padrão nova,
premissa padrão alterada). Toda revisão de simulação grava a versão que usou.

Histórico:
- 0.1.0 (2026-09-15): fundação. Tipos e premissas definidos; cálculos ainda não implementados.
- 0.2.0 (2026-09-17): decisões de 16 e 17 de setembro. Escopo em restrição de linha por razão
  CNF; preço da energia vira valor fixo de 216 R$/MWh no lugar da série de CMO; correção de
  minutos ligada por padrão, pelo campo num_minutos_cnf; fonte de geração por flag, padrão
  eólica.
- 0.3.0 (2026-09-17): feature 01. O motor passa a calcular: adição de circuito com
  sensibilidade, bateria com despacho guloso, combinada na ordem equipamento-bateria, e a
  conta econômica com VPL, TIR, payback e custo por MWh. A correção de minutos entra em
  vigor pelo campo minutos_cnf, e campo vazio significa sem correção. Contrato: Intervalo
  troca minutos_restricao por minutos_cnf, e TipoIntervencao passa a ter só adicao_circuito.
- 0.4.0 (2026-09-18): a série do ONS é esparsa, e o motor passa a tratá-la como tal. O período
  vem declarado em periodo_inicio e periodo_fim, e não mais do número de linhas, que fazia um
  ano parecer dois meses e inflava a anualização por cinco. A bateria passa a descarregar na
  folga entre dois cortes, medida pelos carimbos de tempo, em vez de esperar linhas de corte
  zero que a série esparsa não tem.
- 0.5.0 (2026-09-21): feature 07. Entra a regra de ocorrência, que o motor não tinha: a
  premissa regra_ocorrencia_intervalos_tolerados existia desde 0.1.0 e nunca era lida.
  `agrupar` junta intervalos com corte cuja distância entre carimbos é de até
  `tolerados + 1` meias horas, e o padrão zero exige folga zero. Nenhum resultado existente
  muda: é cálculo novo sobre o dado observado, ao lado do que já havia.
- 0.5.1 (2026-09-21): correção, mesmo resultado. `ConfigBateria.soc_inicial` vazio passa a
  assumir `soc_min` em vez de zero. Zero era carga proibida sempre que `soc_min` fosse maior
  que zero, então omitir um campo opcional derrubava o pedido com 422 sem que quem o montou
  tivesse escolhido nada. Nenhuma entrada que antes calculava muda: com `soc_min` no padrão
  zero, o valor assumido é o mesmo de antes. O cálculo passa a ler `carga_inicial`.
- 0.6.0 (2026-09-21): feature 15. `premissas_usadas` passa a carimbar `fonte_geracao`, a
  premissa declarada em 0.1.0 e nunca lida por ninguém. **Nenhum número muda**, e é por isso que
  é menor e não correção: a saída ganha um campo. O `Resultado` serializado da mesma entrada
  passa a ter uma chave a mais, e o comparador, que faz a união das chaves, desenha a linha nova
  com um lado vazio ao pôr lado a lado uma revisão de antes e uma de depois. Mesma graduação da
  0.5.0, que era saída nova ao lado da que havia; a 0.5.1 foi correção porque ali o `Resultado`
  era idêntico. O contrato não muda de forma — `premissas_usadas` já é `dict[str, Premissa]`.
  A fonte era a única entrada do cálculo que não sobrevivia ao salvamento, então a revisão não
  era reproduzível e a coluna "o que mudou" dizia "mesmos parâmetros" com o número diferente ao
  lado. O motor carimba e não lê: quem filtra a série pela fonte é quem a monta, antes dele.
- 0.7.0 (2026-09-22): feature 17, marco 0. Entra `relatorio.derivar`, a parte calculada do
  relatório da simulação: ordenações com empate, diferenças contra a base e a anterior,
  sensibilidade observada por par consecutivo, fronteiras entre as revisões cobertas, o que
  variou e o que ficou parado, premissas expostas. **Nenhum resultado muda**: é cálculo novo ao
  lado do que havia, a mesma graduação da 0.5.0.
- 0.8.0 (2026-09-23): feature 17, marco 1. Entram `montar_configuracao`, a configuração inteira
  de uma simulação nova a partir da alavanca, com o investimento por custo unitário vezes
  quantidade, e `montar_variacao`, que troca uma alavanca de uma revisão e reajusta o custo pela
  mesma conta, dentro da faixa permitida do explorador. Premissas padrão novas:
  `bateria_duracao_horas` e `teto_alavanca_capacidade`, que `simular` não lê. **Nenhum resultado
  muda**: é regra nova ao lado da que havia, a mesma graduação da 0.5.0. Sobe porque a revisão
  que o explorador salvar tem a configuração montada por esta regra, e a versão diz qual.
- 0.9.0 (2026-09-23): feature 17, marco 1. `Resultado` ganha `diagnosticos`: saturação da
  bateria (meias horas com corte em que ela terminou cheia, episódios que a pegaram vazia ou com
  carga) e corte residual por hora do dia. Mais `diagnosticos.cruzamentos` entre revisões.
  **Nenhum número existente muda**: saída nova, a mesma graduação da 0.6.0. O teto de carga do
  despacho passou para `bateria.teto_mwh`, sem mudar conta, para o diagnóstico ler o mesmo "cheia".
- 0.10.0 (2026-09-23): feature 17, marco 1, ADR 0014. `relatorio.derivar` compara cada revisão
  com a de onde ela nasceu (`revisao_anterior_id`), e não com a vizinha na ordem de gravação,
  nas diferenças "vs anterior" e na sensibilidade; e potência com capacidade mudando na mesma
  duração passa a ser a alavanca potência, com a capacidade acompanhando como o custo. **A saída
  do relatório muda para a mesma entrada** numa simulação com ramos ou com variação de potência;
  numa cadeia linear sem essa variação, não. Nenhum `Resultado` de simulação muda, e por isso
  a versão não entra em `MUDAM_RESULTADO`: revisões das duas versões continuam comparáveis.
"""

METODO_VERSAO = "0.10.0"

MUDAM_RESULTADO = ("0.2.0", "0.3.0", "0.4.0")
"""As versões acima em que o resultado muda para a mesma entrada. As outras acrescentaram cálculo
ou campo sem mexer em número. É o que diz se duas revisões de versões diferentes são comparáveis
na sensibilidade do relatório (`relatorio.derivar`). **Versão nova que muda resultado entra
aqui** — um teste confere que toda versão listada existe no histórico acima."""
