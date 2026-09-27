import type { Configuration } from './get-simulation'
import { scenarioLabels, modalityLabels } from './labels'
import { formatFractionAsPercent, formatNumber, formatReais } from '@/utils/format'

export type FieldId =
  | 'modalidade'
  | 'subestacao'
  | 'potencia'
  | 'capacidade'
  | 'carga_inicial'
  | 'carga_faixa'
  | 'eficiencia'
  | 'disponibilidade_bateria'
  | 'degradacao'
  | 'vida_util_bateria'
  | 'tipo'
  | 'linha'
  | 'ganho'
  | 'disponibilidade_circuito'
  | 'vida_util_circuito'
  | 'cenario'
  | 'taxa'
  | 'horizonte'
  | 'investimento'
  | 'opex'
  | 'residual'
  | 'preco'
  | 'receitas'
  | 'reposicoes'

export type ConfigField = {
  id: FieldId
  label: string
  /** O valor já formatado com a unidade. `null` quando o bloco não existe nesta modalidade. */
  value: string | null
  block: 'geral' | 'bateria' | 'equipamento' | 'financeira'
}

const percent = (fraction: number) => `${formatFractionAsPercent(fraction, 1)} %`

/**
 * Os campos de `Configuracao` como a tela os mostra, um por linha, com unidade. O bloco que a
 * modalidade não tem sai com `value: null`, e cada tela decide se mostra "sem bateria" ou some.
 * `lineName` é o nome da linha do cadastro: a configuração só guarda o código.
 */
export function configurationFields(config: Configuration, lineName?: string): ConfigField[] {
  const { bateria: battery, equipamento: equipment, financeira: financial } = config
  const financials = financial

  const field = (
    id: FieldId,
    label: string,
    block: ConfigField['block'],
    value: string | null,
  ): ConfigField => ({ id, label, block, value })

  return [
    field('modalidade', 'Modalidade', 'geral', modalityLabels[config.modalidade]),

    field('subestacao', 'Ponto de conexão da bateria', 'bateria', battery?.subestacao ?? null),
    field(
      'potencia',
      'Potência da bateria',
      'bateria',
      battery ? `${formatNumber(battery.potencia_mw)} MW` : null,
    ),
    field(
      'capacidade',
      'Capacidade da bateria',
      'bateria',
      battery ? `${formatNumber(battery.capacidade_mwh)} MWh` : null,
    ),
    field(
      'carga_inicial',
      'Carga no início da janela',
      'bateria',
      // Omitida, a API assume `soc_min` (o contrato guarda `null`): a tela diz o que valeu.
      battery
        ? battery.soc_inicial == null
          ? `Assume a carga mínima (${percent(battery.soc_min)})`
          : percent(battery.soc_inicial)
        : null,
    ),
    field(
      'carga_faixa',
      'Carga mínima e máxima',
      'bateria',
      battery ? `${percent(battery.soc_min)} a ${percent(battery.soc_max)}` : null,
    ),
    field(
      'eficiencia',
      'Eficiência de ida e volta',
      'bateria',
      battery ? percent(battery.eficiencia_ida_volta) : null,
    ),
    field(
      'disponibilidade_bateria',
      'Disponibilidade da bateria',
      'bateria',
      battery ? percent(battery.disponibilidade) : null,
    ),
    field(
      'degradacao',
      'Degradação por ciclo e por ano',
      'bateria',
      battery
        ? `${percent(battery.degradacao_por_ciclo)} · ${percent(battery.degradacao_por_ano)} a.a.`
        : null,
    ),
    field(
      'vida_util_bateria',
      'Vida útil da bateria',
      'bateria',
      battery ? `${battery.vida_util_anos} anos` : null,
    ),

    field('tipo', 'Tipo de intervenção', 'equipamento', equipment ? 'Adição de circuito' : null),
    field(
      'linha',
      'Linha que recebe o circuito novo',
      'equipamento',
      equipment ? (lineName ?? equipment.cod_equipamento) : null,
    ),
    field(
      'ganho',
      'Ganho de limite',
      'equipamento',
      equipment ? `${formatNumber(equipment.ganho_limite_mw)} MW` : null,
    ),
    field(
      'disponibilidade_circuito',
      'Disponibilidade do circuito',
      'equipamento',
      equipment ? percent(equipment.disponibilidade) : null,
    ),
    field(
      'vida_util_circuito',
      'Vida útil do circuito',
      'equipamento',
      equipment ? `${equipment.vida_util_anos} anos` : null,
    ),

    field('cenario', 'Cenário', 'financeira', scenarioLabels[financials.cenario]),
    field(
      'taxa',
      'Taxa de desconto',
      'financeira',
      `${formatFractionAsPercent(financials.taxa_desconto_aa, 2)} % a.a.`,
    ),
    field('horizonte', 'Horizonte', 'financeira', `${financials.horizonte_anos} anos`),
    field(
      'investimento',
      'Investimento inicial',
      'financeira',
      formatReais(financials.capex_reais),
    ),
    field(
      'opex',
      'Custo de operação fixo e variável',
      'financeira',
      `${formatReais(financials.opex_fixo_reais_ano)}/ano · ${formatReais(financials.opex_variavel_reais_mwh)}/MWh`,
    ),
    field('residual', 'Valor residual', 'financeira', formatReais(financials.valor_residual_reais)),
    field(
      'preco',
      'Preço da energia',
      'financeira',
      financials.preco_energia_reais_mwh == null
        ? 'premissa'
        : `${formatReais(financials.preco_energia_reais_mwh)}/MWh`,
    ),
    field(
      'receitas',
      'Receitas adicionais',
      'financeira',
      `${formatReais(financials.receitas_adicionais_reais_ano)}/ano`,
    ),
    field(
      'reposicoes',
      'Reposições',
      'financeira',
      financials.reposicoes && financials.reposicoes.length > 0
        ? financials.reposicoes
            .map((item) => `ano ${item.ano}: ${formatReais(item.valor_reais)}`)
            .join(' · ')
        : 'nenhuma',
    ),
  ]
}
