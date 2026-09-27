import type { Report, ReportState } from '@/features/saved-simulations/api/report'

/**
 * Relatório de teste, com números fictícios só coerentes o bastante para exercer os blocos da
 * tela (3 revisões cobertas, uma diferença, uma sensibilidade). Usado apenas por
 * `simulation-report.test.tsx`.
 */
const BASE: Report = {
  id: 1,
  simulacao_id: 7,
  nome: 'Bateria em Açu III, cenário de referência',
  pergunta: 'Se uma bateria em Açu III existisse, quanto corte teria evitado?',
  estado: 'pronto',
  erro: null,
  gerado_em: '2026-09-22T14:10:00-03:00',
  snapshot_id: '2026-09-21',
  metodo_versao: '0.7.0',
  modelo: 'gemini-3.8-flash',
  versao_prompt: 'analista-1',
  revisoes_cobertas: [1, 2, 3],
  revisoes_novas: [
    { revisao_id: 106, posicao: 4, criada_em: '2026-09-22T15:02:00-03:00' },
    { revisao_id: 107, posicao: 5, criada_em: '2026-09-22T15:20:00-03:00' },
  ],
  verificacao: {
    resultado: 'passou',
    numeros_na_prosa: 12,
    encontrados: 12,
    tolerancia: '2 algarismos significativos',
    contagens: {
      leitura_geral: [6, 6],
      o_que_variou: [2, 2],
      sensibilidade: [4, 4],
      fora_do_metodo: [4, 4],
      perguntas_que_ficaram: [3, 3],
    },
    falhas: [],
  },
  cabecalho: {
    restricao_id: 'exemplo',
    nome_curto: 'LT 500 kV Açu III / Milagres II · C1',
    texto: 'LIMITE DE ESCOAMENTO DA GERAÇÃO EÓLICA NA REGIÃO DE AÇU III',
    instrucao_operacao: 'IO-ON.NE.5NE',
    contingencia: 'LT 500 kV Açu III / Milagres II',
    subestacoes: ['Açu III', 'Milagres II'],
    presente_no_snapshot: true,
    snapshot_id: '2026-09-21',
    periodo_inicio: '2025-09-01T00:00:00-03:00',
    periodo_fim: '2026-09-01T00:00:00-03:00',
    energia_cortada_mwh: 334_200,
    fonte: 'eolica',
    fatia_por_fonte: [{ fonte: 'eolica', fatia: 0.62 }],
    ocorrencias: {
      total: 174,
      energia_mwh: 334_200,
      maiores: [],
      aviso: 'A contagem de ocorrências é sensível a artefato de apuração.',
    },
    equipamentos: [
      {
        cod_equipamento: 'EX-C1',
        nome: 'LT 500 kV Açu III / Milagres II C1',
        papel: 'monitorado',
        procedencia: 'automatica',
        tensao_kv: 500,
        subestacao_de: 'Açu III',
        subestacao_para: 'Milagres II',
        comprimento_km: 285,
        capacidade_longa_mva: 2_910,
      },
    ],
    avisos: [],
  },
  trilha: [
    {
      revisao_id: 101,
      posicao: 1,
      criada_em: '2026-09-20T10:05:00-03:00',
      procedencia: 'por_pessoa',
      origem_do_texto: 'resumo_da_configuracao',
      texto: 'Bateria de 50 MW e 100 MWh em Açu III, cenário de referência.',
    },
    {
      revisao_id: 102,
      posicao: 2,
      criada_em: '2026-09-20T10:40:00-03:00',
      procedencia: 'por_pessoa',
      origem_do_texto: 'nota_da_pessoa',
      texto: 'Dobrar a potência mantendo a capacidade.',
    },
    {
      revisao_id: 103,
      posicao: 3,
      criada_em: '2026-09-20T11:15:00-03:00',
      procedencia: 'por_pessoa',
      origem_do_texto: 'nota_da_pessoa',
      texto: 'Com 100 MW a bateria esvaziou cedo; dobrar a capacidade.',
    },
  ],
  prosa: {
    leitura_geral:
      'A simulação pergunta se uma bateria em Açu III teria evitado corte. A energia recuperada ficou entre 21.500 MWh e 41.300 MWh, de 334.200 MWh cortados no período.',
    o_que_variou: [
      'Potência da bateria, de 50 MW para 100 MW entre a rev 1 e a rev 2: a energia recuperada subiu 3.400 MWh.',
      'Capacidade da bateria, de 100 MWh para 200 MWh entre a rev 2 e a rev 3: a fração recuperada passou de 7,5 % para 12,4 %.',
    ],
    sensibilidade:
      'Entre as revisões cobertas, cada MW de potência a mais moveu o VPL em R$ -466 mil, e cada MWh de capacidade, em R$ 477 mil.',
    fora_do_metodo:
      'O resultado é contrafactual e não é previsão. Energia recuperável não é receita capturável.',
    perguntas_que_ficaram: [
      'A taxa de desconto ficou fixa em todas as revisões: como o VPL se comporta com outras taxas?',
    ],
  },
  derivados: {
    base: { revisao_id: 101, posicao: 1 },
    ordenacoes: {
      vpl: [
        { posicao: 1, revisao_id: 103, posicao_da_revisao: 3, valor: -23_800_000, empate_com: [] },
        { posicao: 2, revisao_id: 101, posicao_da_revisao: 1, valor: -48_200_000, empate_com: [] },
        { posicao: 3, revisao_id: 102, posicao_da_revisao: 2, valor: -71_500_000, empate_com: [] },
      ],
      fracao_recuperada: [],
      payback_descontado: [],
      custo_por_mwh: [],
    },
    diferencas: [
      {
        revisao_id: 102,
        o_que_mudou: 'Potência da bateria: 50 → 100 MW',
        delta_vpl_vs_base_reais: -23_300_000,
        delta_vpl_vs_anterior_reais: -23_300_000,
        delta_energia_vs_base_mwh: 3_400,
        delta_energia_vs_anterior_mwh: 3_400,
        delta_fracao_vs_base: 0.011,
        delta_payback_simples_vs_base_anos: 4.7,
      },
    ],
    sensibilidades: [
      {
        de_revisao_id: 101,
        para_revisao_id: 102,
        tipo: 'numerica',
        campo: 'bateria.potencia_mw',
        rotulo: 'Potência da bateria',
        de: '50 MW',
        para: '100 MW',
        delta_vpl_por_unidade_reais: -466_000,
        delta_energia_por_unidade_mwh: 68,
        delta_vpl_reais: null,
        campos_que_mudaram: ['bateria.potencia_mw'],
        condicao: 'capacidade fixa em 100 MWh',
      },
    ],
    fronteiras: {
      menor_alavanca_com_payback_no_horizonte: null,
      maior_fracao_recuperada: null,
      tir_passa_taxa: null,
    },
    variou: [
      { campo: 'bateria.potencia_mw', rotulo: 'Potência da bateria', valores: ['50 MW', '100 MW'] },
    ],
    ficou_parado: [{ campo: 'bateria.subestacao', rotulo: 'Ponto de conexão', valor: 'Açu III' }],
    premissas_expostas: [
      {
        id: 'preco_energia',
        descricao: 'Preço da energia',
        valor: '300',
        unidade: 'R$/MWh',
        faixa: [150, 450],
        fonte: 'exemplo',
        status: 'nao_verificada',
        de_metodo: false,
      },
    ],
  },
  por_revisao: [
    {
      revisao_id: 101,
      posicao: 1,
      criada_em: '2026-09-20T10:05:00-03:00',
      procedencia: 'por_pessoa',
      modalidade: 'bateria',
      alavanca: '50 MW · 100 MWh · Açu III',
      cenario: 'referencia',
      energia_recuperada_mwh: 21_500,
      fracao_recuperada: 0.064,
      vpl_reais: -48_200_000,
      tir_aa: 0.041,
      payback_simples_anos: 14.2,
      payback_descontado_anos: null,
      custo_por_mwh_reais: 612,
      avisos: 2,
      url: '/simulacoes/101',
    },
    {
      revisao_id: 102,
      posicao: 2,
      criada_em: '2026-09-20T10:40:00-03:00',
      procedencia: 'por_pessoa',
      modalidade: 'bateria',
      alavanca: '100 MW · 100 MWh · Açu III',
      cenario: 'referencia',
      energia_recuperada_mwh: 24_900,
      fracao_recuperada: 0.075,
      vpl_reais: -71_500_000,
      tir_aa: 0.022,
      payback_simples_anos: 18.9,
      payback_descontado_anos: null,
      custo_por_mwh_reais: 845,
      avisos: 2,
      url: '/simulacoes/102',
    },
    {
      revisao_id: 103,
      posicao: 3,
      criada_em: '2026-09-20T11:15:00-03:00',
      procedencia: 'por_pessoa',
      modalidade: 'bateria',
      alavanca: '100 MW · 200 MWh · Açu III',
      cenario: 'referencia',
      energia_recuperada_mwh: 41_300,
      fracao_recuperada: 0.124,
      vpl_reais: -23_800_000,
      tir_aa: 0.083,
      payback_simples_anos: 10.6,
      payback_descontado_anos: 21.4,
      custo_por_mwh_reais: 540,
      avisos: 2,
      url: '/simulacoes/103',
    },
  ],
  nao_afirma: [
    {
      titulo: 'Sensibilidade calculada',
      texto: 'Aqui só entra a sensibilidade observada entre revisões que existem.',
    },
    { titulo: 'Vencedor', texto: 'Nenhuma seção chama uma revisão de melhor.' },
  ],
}

export function reportFixture(state: ReportState = 'pronto'): Report {
  if (state === 'gerando') {
    return {
      ...BASE,
      estado: 'gerando',
      gerado_em: null,
      modelo: null,
      revisoes_novas: [],
      verificacao: { ...BASE.verificacao, resultado: null, numeros_na_prosa: 0, encontrados: 0 },
      cabecalho: null,
      trilha: [],
      prosa: null,
      derivados: null,
      por_revisao: [],
    }
  }
  if (state === 'barrado') {
    return {
      ...BASE,
      estado: 'barrado',
      prosa: null,
      verificacao: {
        ...BASE.verificacao,
        resultado: 'falhou',
        encontrados: 11,
        falhas: [
          {
            secao: 'sensibilidade',
            numero: 'R$ 512 mil',
            motivo: 'sem_origem',
            trecho: 'cada MWh de capacidade moveu o VPL em R$ 512 mil',
          },
        ],
      },
    }
  }
  if (state === 'falhou') {
    return { ...reportFixture('gerando'), estado: 'falhou', erro: 'O modelo não respondeu.' }
  }
  return BASE
}
