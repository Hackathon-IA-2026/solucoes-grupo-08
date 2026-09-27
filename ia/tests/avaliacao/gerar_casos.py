"""Gera os casos de ouro do conjunto de avaliação do analista (feature 17, task 17.5).

`uv run python ia/tests/avaliacao/gerar_casos.py` reescreve `casos/*.json`. Rodar de novo só
quando o formato da parte calculada mudar: o arquivo gravado é o que fixa o caso, e é contra ele
que modelos diferentes são comparados.

**Os números são do motor sobre uma série sintética, não do ONS, e os custos são inventados.**
A série tem um ano de cortes noturnos com amplitude que varia por estação e por semana,
determinística. Investimento de R$ 1,2 milhão por MW e R$ 0,9 milhão por MWh de bateria, R$ 250
milhões por circuito e custo fixo de 2% ao ano não vêm de premissa nenhuma: servem só para a
conta ter ordem de grandeza plausível. As subestações seguem o layout (`Relatorio.dc.html`) para
o modelo ler um caso com cara de caso real, e tudo que poderia passar por dado real diz que é
sintético: nome da simulação, nome e texto da restrição, snapshot.

O formato é o da parte calculada da API (`api/src/arco_api/relatorio.py`, `ParteCalculada`), e
um teste da API valida cada caso contra ele, porque `ia` não importa `api`.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from arco_motor.ocorrencias import agrupar
from arco_motor.premissas import PREMISSAS_PADRAO
from arco_motor.relatorio import RevisaoCoberta, alavanca, derivar, escrever, folhas
from arco_motor.simular import simular
from arco_motor.tipos import (
    Cenario,
    ConfigBateria,
    ConfigEquipamento,
    ConfigFinanceira,
    Configuracao,
    Intervalo,
    Modalidade,
    SerieRestricao,
    TipoIntervencao,
)

CASOS = Path(__file__).with_name("casos")
INICIO = datetime(2025, 9, 1)
FIM = datetime(2026, 9, 1)
SUBESTACAO = "AÇU III"
LINHA = "LT-SINTETICA-ACU-MIL-C1"
AVISO_OCORRENCIAS = (
    "A contagem é sensível a artefato de apuração: uma meia hora titulada por outra razão parte "
    "em duas uma noite que fisicamente foi uma. Serve para auditoria, não como número de "
    "vitrine. O par a ler é ocorrência mais fatia de energia."
)
ROTULOS = {
    "modalidade": "Modalidade",
    "bateria.potencia_mw": "Potência da bateria",
    "bateria.capacidade_mwh": "Capacidade da bateria",
    "equipamento.ganho_limite_mw": "Ganho de limite",
    "equipamento.cod_equipamento": "Linha que recebe o circuito",
    "financeira.cenario": "Cenário",
    "financeira.taxa_desconto_aa": "Taxa de desconto",
    "financeira.capex_reais": "Investimento inicial",
    "financeira.opex_fixo_reais_ano": "Custo fixo de operação",
    "financeira.preco_energia_reais_mwh": "Preço da energia",
}
"""Os rótulos que a API usa (`mudancas.ROTULOS`), para os campos que os casos variam."""


def serie() -> SerieRestricao:
    """Um ano de cortes das 20h às 5h. Amplitude de 60 a 260 MW, por estação e por semana."""
    intervalos = []
    passo = timedelta(minutes=30)
    instante = INICIO
    while instante < FIM:
        noite = instante.hour >= 20 or instante.hour < 5
        dia = (instante - INICIO).days
        if noite:
            corte = 160 + 70 * math.sin(2 * math.pi * dia / 365) + 30 * math.sin(dia)
            intervalos.append(
                Intervalo(instante=instante, corte_mw=round(corte, 1), minutos_cnf=20)
            )
        instante += passo
    return SerieRestricao(
        restricao_id="sintetica",
        snapshot_id="sintetico",
        intervalos=intervalos,
        periodo_inicio=INICIO,
        periodo_fim=FIM,
    )


def financeira(
    capex: float,
    cenario: Cenario = Cenario.REFERENCIA,
    taxa: float = 0.08,
    preco: float | None = None,
) -> ConfigFinanceira:
    return ConfigFinanceira(
        cenario=cenario,
        taxa_desconto_aa=taxa,
        horizonte_anos=15,
        capex_reais=capex,
        opex_fixo_reais_ano=round(0.02 * capex),
        preco_energia_reais_mwh=preco,
    )


def bateria(potencia: float, capacidade: float, **fin: Any) -> Configuracao:
    return Configuracao(
        modalidade=Modalidade.BATERIA,
        bateria=ConfigBateria(
            potencia_mw=potencia, capacidade_mwh=capacidade, subestacao=SUBESTACAO
        ),
        financeira=financeira(potencia * 1.2e6 + capacidade * 0.9e6, **fin),
    )


def equipamento(ganho: float) -> Configuracao:
    return Configuracao(
        modalidade=Modalidade.EQUIPAMENTO,
        equipamento=ConfigEquipamento(
            tipo=TipoIntervencao.ADICAO_CIRCUITO, cod_equipamento=LINHA, ganho_limite_mw=ganho
        ),
        financeira=financeira(250e6),
    )


def combinada(ganho: float, potencia: float, capacidade: float) -> Configuracao:
    return Configuracao(
        modalidade=Modalidade.COMBINADA,
        equipamento=ConfigEquipamento(
            tipo=TipoIntervencao.ADICAO_CIRCUITO, cod_equipamento=LINHA, ganho_limite_mw=ganho
        ),
        bateria=ConfigBateria(
            potencia_mw=potencia, capacidade_mwh=capacidade, subestacao=SUBESTACAO
        ),
        financeira=financeira(250e6 + potencia * 1.2e6 + capacidade * 0.9e6),
    )


def o_que_mudou(config: Configuracao, anterior: Configuracao | None, posicao: int) -> str:
    """Na forma de `mudancas.descrever`, da API: "Rótulo: de → para; ..."."""
    if anterior is None:
        return "Original, primeira revisão desta simulação."
    antes, depois = folhas(anterior), folhas(config)
    mudancas = [
        f"{ROTULOS.get(c, c)}: {escrever(antes.get(c), c)} → {escrever(depois.get(c), c)}"
        for c in dict.fromkeys([*antes, *depois])
        if antes.get(c) != depois.get(c)
    ]
    return "; ".join(mudancas) + "." if mudancas else f"Mesmos parâmetros da rev {posicao - 1}."


def resumo(config: Configuracao) -> str:
    cenario = {"referencia": "de referência"}.get(
        config.financeira.cenario, config.financeira.cenario
    )
    return f"{alavanca(config)}, cenário {cenario}"


class DoAgente:
    """Uma revisão salva por agente numa exploração: de qual posição nasceu e o porquê."""

    def __init__(self, config: Configuracao, origem: int, nota: str) -> None:
        self.config, self.origem, self.nota = config, origem, nota


def parte_calculada(
    nome: str, pergunta: str, configs: list[Configuracao | DoAgente]
) -> dict[str, Any]:
    """Revisões em cadeia, cada uma nascida da anterior, a menos que venha como `DoAgente`, que
    diz a posição de onde nasceu (a simulação tem ramos, ADR 0014) e traz a nota."""
    s = serie()
    criada = datetime(2026, 9, 22, 9, 0)
    cobertas = []
    notas: dict[int, str] = {}
    for posicao, item in enumerate(configs, start=1):
        config = item.config if isinstance(item, DoAgente) else item
        origem = item.origem if isinstance(item, DoAgente) else posicao - 1
        if isinstance(item, DoAgente):
            notas[100 + posicao] = item.nota
        anterior = configs[origem - 1] if origem >= 1 else None
        cobertas.append(
            RevisaoCoberta(
                revisao_id=100 + posicao,
                posicao=posicao,
                criada_em=criada + timedelta(minutes=5 * posicao),
                configuracao=config,
                resultado=simular(s, config, PREMISSAS_PADRAO),
                o_que_mudou=o_que_mudou(
                    config,
                    anterior.config if isinstance(anterior, DoAgente) else anterior,
                    origem + 1,
                ),
                revisao_anterior_id=100 + origem if origem >= 1 else None,
            )
        )
    ocorrencias = sorted(agrupar(s, PREMISSAS_PADRAO), key=lambda o: o.energia_mwh, reverse=True)
    cabecalho = {
        "restricao_id": "sintetica",
        "nome_curto": "LT 500 kV Açu III / Milagres II · C1 (sintética)",
        "texto": "CONTROLE DE CARREGAMENTO DA LT 500 KV AÇU III / MILAGRES II – C1 (série "
        "sintética para avaliação)",
        "instrucao_operacao": None,
        "contingencia": None,
        "subestacoes": ["AÇU III", "MILAGRES II"],
        "presente_no_snapshot": True,
        "snapshot_id": s.snapshot_id,
        "periodo_inicio": INICIO.isoformat(),
        "periodo_fim": FIM.isoformat(),
        "energia_cortada_mwh": s.energia_cortada_mwh,
        "fonte": "eolica",
        "fatia_por_fonte": [{"fonte": "eolica", "fatia": 0.25}],
        "ocorrencias": {
            "total": len(ocorrencias),
            "energia_mwh": sum(o.energia_mwh for o in ocorrencias),
            "maiores": [
                {
                    "inicio": o.inicio.isoformat(),
                    "fim": o.fim.isoformat(),
                    "intervalos": o.intervalos,
                    "duracao_horas": o.duracao_horas,
                    "energia_mwh": o.energia_mwh,
                    "corte_medio_maximo_mw": o.corte_medio_maximo_mw,
                }
                for o in ocorrencias[:3]
            ],
            "aviso": AVISO_OCORRENCIAS,
        },
        "equipamentos": [
            {
                "cod_equipamento": LINHA,
                "papel": "monitorado",
                "procedencia": "automatica",
                "tensao_kv": 500,
                "subestacao_de": "AÇU III",
                "subestacao_para": "MILAGRES II",
            }
        ],
        "avisos": [],
    }
    por_revisao = [
        {
            "revisao_id": c.revisao_id,
            "posicao": c.posicao,
            "criada_em": c.criada_em.isoformat(),
            "procedencia": "por_agente" if c.revisao_id in notas else "por_pessoa",
            "modalidade": c.configuracao.modalidade.value,
            "alavanca": alavanca(c.configuracao),
            "cenario": c.configuracao.financeira.cenario.value,
            "energia_recuperada_mwh": c.resultado.tecnico.energia_recuperada_mwh,
            "fracao_recuperada": c.resultado.tecnico.fracao_recuperada,
            "vpl_reais": c.resultado.financeiro.vpl_reais,
            "tir_aa": c.resultado.financeiro.tir_aa,
            "payback_simples_anos": c.resultado.financeiro.payback_simples_anos,
            "payback_descontado_anos": c.resultado.financeiro.payback_descontado_anos,
            "custo_por_mwh_reais": c.resultado.financeiro.custo_por_mwh_reais,
            "avisos": len(c.resultado.avisos),
            "url": f"/simulacoes/{c.revisao_id}",
        }
        for c in cobertas
    ]
    trilha = [
        {
            "revisao_id": c.revisao_id,
            "posicao": c.posicao,
            "criada_em": c.criada_em.isoformat(),
            "procedencia": "por_agente" if c.revisao_id in notas else "por_pessoa",
            "texto": notas.get(c.revisao_id) or resumo(c.configuracao),
            "origem_do_texto": "nota_do_agente"
            if c.revisao_id in notas
            else "resumo_da_configuracao",
        }
        for c in cobertas
    ]
    return {
        "simulacao": {"nome": nome, "pergunta": pergunta},
        "cabecalho": cabecalho,
        "trilha": trilha,
        "derivados": derivar(cobertas, ROTULOS).model_dump(mode="json"),
        "por_revisao": por_revisao,
        "nao_afirma": NAO_AFIRMA,
    }


NAO_AFIRMA = [
    {
        "titulo": "Sensibilidade calculada",
        "texto": "O relatório só fala de sensibilidade observada entre revisões que existem. "
        "Saber o VPL com outro preço exige recalcular, e recalcular é revisão nova.",
    },
    {
        "titulo": "Série por mês ou por hora do dia",
        "texto": "O resultado guarda a série por intervalo sem o instante, e não há como "
        "agregá-la por período até a rota devolvê-lo.",
    },
    {
        "titulo": "Ordem não é indicação",
        "texto": "O relatório ordena as revisões por critério declarado e não indica nenhuma "
        "delas: ordenar é evidência, e a decisão fica com quem lê.",
    },
    {
        "titulo": "O resultado é contrafactual",
        "texto": "Diz o que teria acontecido sob as hipóteses informadas se o passado se "
        "repetisse com a intervenção disponível. Não é previsão.",
    },
    {
        "titulo": "Associação não é causalidade",
        "texto": "A associação histórica entre o texto da restrição e um equipamento não prova, "
        "sozinha, causalidade física nem sensibilidade unitária. A conversão entre "
        "reforço e corte recuperável é premissa visível e editável.",
    },
    {
        "titulo": "O histórico pode não representar o futuro",
        "texto": "Rede, geração, carga, preços e regulação mudam. Vários gargalos têm obras "
        "previstas.",
    },
    {
        "titulo": "Energia recuperável não é receita capturável",
        "texto": "O valor atribuído à energia é premissa, não contrato.",
    },
    {
        "titulo": "A simulação apoia a decisão, não a substitui",
        "texto": "Não substitui estudo elétrico, regulatório nem de engenharia.",
    },
]
"""Cópia do texto fixo da API (`arco_api.relatorio.NAO_AFIRMA`), que o analista recebe junto. A
avaliação tem de testar o texto que vai para produção: um teste da API exige que os dois sejam
iguais."""


GRADE = (
    "Rodada 1: a grade de tamanhos a partir da revisão de partida, na mesma duração, mostra "
    "onde a fração recuperada deixa de subir."
)
DURACAO = (
    "Rodada 2: a partir do tamanho em que a curva achatou, testar duração mais curta e mais longa."
)
"""Notas como o explorador as escreve: o porquê da rodada, sem número de resultado."""


def casos() -> dict[str, dict[str, Any]]:
    pergunta = (
        "Se uma bateria em Açu III existisse nos últimos 12 meses, quanto corte teria evitado, e "
        "isso se paga?"
    )
    return {
        "uma_revisao": parte_calculada(
            "Circuito novo em Açu III (série sintética)",
            "Um circuito novo na linha monitorada se paga?",
            [equipamento(200.0)],
        ),
        "bateria_sete_revisoes": parte_calculada(
            "Bateria em Açu III, cenário de referência (série sintética)",
            pergunta,
            [
                bateria(50.0, 100.0),
                bateria(100.0, 100.0),
                bateria(100.0, 200.0),
                bateria(100.0, 200.0, cenario=Cenario.CONSERVADOR, taxa=0.10),
                combinada(100.0, 100.0, 200.0),
                bateria(100.0, 200.0, preco=300.0),
                bateria(150.0, 300.0),
            ],
        ),
        "exploracao_com_ramos": parte_calculada(
            "Bateria em Açu III, exploração por rodadas (série sintética)",
            "Até onde vale aumentar a bateria em Açu III?",
            [
                bateria(50.0, 200.0),
                DoAgente(bateria(100.0, 400.0), 1, GRADE),
                DoAgente(bateria(150.0, 600.0), 1, GRADE),
                DoAgente(bateria(200.0, 800.0), 1, GRADE),
                DoAgente(bateria(150.0, 300.0), 3, DURACAO),
                DoAgente(bateria(150.0, 900.0), 3, DURACAO),
            ],
        ),
        "combinada": parte_calculada(
            "Circuito e bateria em Açu III (série sintética)",
            "Somar bateria a um circuito novo muda a conta?",
            [
                combinada(50.0, 50.0, 200.0),
                combinada(100.0, 50.0, 200.0),
                combinada(200.0, 50.0, 200.0),
            ],
        ),
    }


if __name__ == "__main__":
    CASOS.mkdir(exist_ok=True)
    for nome, caso in casos().items():
        destino = CASOS / f"{nome}.json"
        destino.write_text(json.dumps(caso, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(destino)
