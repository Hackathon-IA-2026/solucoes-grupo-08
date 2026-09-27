import type { FieldId } from './configuration-fields'

/**
 * Um texto por campo de `Configuracao`, indexado por `FieldId`. Mesmo rótulo, mesmo tooltip nas
 * etapas 4 e 5 (onde o campo é editável), na tela Resultado ("Configuração desta revisão") e no
 * Comparador: escrever o texto uma vez evita divergir entre telas. Fonte: `docs/features/
 * tooltips-campos/16-tooltips-dos-campos.md`, que cita `docs/premissas.md`, `docs/limites.md` e
 * as descrições de `motor/src/arco_motor/tipos.py`.
 */
export const fieldTooltips: Record<FieldId, string> = {
  modalidade:
    'Tipo de intervenção hipotética que o cálculo aplica sobre o histórico: bateria, adição de circuito, ou as duas. Na combinada o circuito reduz o corte primeiro e a bateria atua sobre o que sobra.',
  subestacao:
    'Subestação da restrição onde a bateria se liga à rede. A bateria se prende a uma subestação, nunca a uma linha. O custo de conexão não é calculado à parte: inclua-o no investimento inicial.',
  potencia:
    'Potência máxima de carga e descarga, em MW. Limita quanto corte a bateria absorve em cada meia hora.',
  capacidade:
    'Energia que a bateria armazena, em MWh. Capacidade dividida pela potência dá as horas de duração: 400 MWh e 100 MW são 4 horas.',
  carga_inicial:
    'Estado de carga (SoC) com que a bateria começa o histórico, fração da capacidade de 0 a 1. Vazio assume a carga mínima, que é a hipótese conservadora.',
  carga_faixa:
    'Piso e teto do estado de carga, fração de 0 a 1. A bateria nunca descarrega abaixo do piso nem carrega acima do teto — protege a vida útil.',
  eficiencia:
    'Fração da energia absorvida que volta para a rede; o resto se perde em calor. Referência de 0,85 (NREL 2025 e piso do leilão de reserva de capacidade). Pesa na devolução, não na absorção.',
  disponibilidade_bateria:
    'Fração do tempo em que a bateria está operacional, de 0 a 1. Multiplica a potência. O padrão do tipo é 1,0; os cenários usam 0,95 a 0,98 (CAISO 2024, Lazard 2025).',
  degradacao:
    'Fração da capacidade perdida a cada ciclo completo de carga e descarga, acumulada ao longo do histórico (referência do PNNL: 0,0076 % por ciclo), mais a perda por calendário, fração por ano — esta não entra na réplica dos 12 meses.',
  vida_util_bateria:
    'Anos em que a bateria opera. Referência da EPE: 20 anos; NREL: 15; PNNL: 25 com reposições.',
  tipo: 'Hoje só adição de circuito: uma linha nova em paralelo. Recondutoramento e aumento de limite do existente ficaram fora, porque não resolvem limite de tensão.',
  linha:
    'Qual linha da restrição ganha o circuito paralelo. A revisão salva guarda o código dela no cadastro do ONS.',
  ganho:
    'Quanto o limite operativo da restrição sobe com o circuito novo, em MW. É a premissa mais exposta do produto: o cálculo assume que 1 MW a mais no limite evita até 1 MW de corte, e essa sensibilidade real depende da rede e não foi estimada.',
  disponibilidade_circuito:
    'Fração do tempo em que o circuito novo está em operação, de 0 a 1. Multiplica o ganho de limite.',
  vida_util_circuito:
    'Anos em que o circuito opera. Referência: 25 anos (vida econômica da EPE); 30 é o prazo de concessão.',
  cenario:
    'Conjunto de valores iniciais para os campos financeiros: conservador, referência ou otimista. Só preenche o formulário; você pode alterar qualquer valor depois. Fontes: EPE (PDE 2035), NREL, PNNL, Lazard e Banco de Preços da ANEEL.',
  taxa: 'Taxa ao ano, em termos reais, que traz os fluxos futuros a valor presente. Fração: 0,08 é 8 % ao ano. Referência de 8 % (WACC regulatório, EPE); conservador 12 % (custo do capital próprio).',
  horizonte:
    'Quantos anos o fluxo de caixa cobre. A energia recuperada nos 12 meses históricos é repetida em cada ano do horizonte.',
  investimento:
    'CAPEX: custo total de implantar a intervenção, em reais, no ano zero. Para bateria, inclua a conexão à subestação. Para circuito, o preço por km do Banco de Preços da ANEEL vezes o comprimento é o ponto de partida.',
  opex: 'OPEX: custo fixo anual, em R$ por ano, mais o custo variável, em R$ por MWh recuperado, que multiplica a energia recuperada de cada ano.',
  residual:
    'Quanto o ativo ainda vale ao fim do horizonte, em reais. Entra como receita no último ano. Padrão zero, por ser a hipótese conservadora.',
  preco:
    'Valor de cada MWh recuperado, em R$ por MWh, fixo para todo o horizonte. Ponto de partida: 216 R$/MWh, o CMO médio ponderado de 2025 nas meias horas de corte local por confiabilidade. Não é receita contratada: energia recuperável não é receita capturável.',
  receitas:
    'Receita além da energia recuperada, em R$ por ano, como serviço ancilar ou arbitragem. Entra igual em todo ano do horizonte.',
  reposicoes:
    'Gastos pontuais de substituição de equipamento ao longo do horizonte, como troca de módulos da bateria. Cada reposição tem o ano do fluxo e o valor em reais.',
}
