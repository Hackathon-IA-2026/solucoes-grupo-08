"""Valores iniciais por cenário: o que a tela preenche antes de existir cálculo.

Isto **não é entrada do motor**. `simular` não lê este módulo: as premissas que o cálculo aplica
são as de `PREMISSAS_PADRAO`, e os números da configuração chegam pelo pedido. O que mora aqui é
o catálogo com que a tela abre o formulário preenchido, e é por isso que mexer nele não sobe
`METODO_VERSAO`.

Cada valor traz a premissa inteira — unidade, fonte e status —, porque a regra de ouro manda
mostrar valor e status lado a lado, e porque número solto na tela é número sem fonte. O registro
humano equivalente é `docs/premissas.md`, e um teste garante que os ids batem.

`PREMISSAS_POR_CENARIO` só leva premissa que preenche um campo de `Configuracao` 1 para 1. O
custo unitário mora ao lado, em `CUSTOS_POR_CENARIO`: dele não sai um campo, sai o investimento
inicial, por custo unitário vezes quantidade, e quem faz essa conta com a trilha à vista é
`montar.py` (feature 17, marco 1).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from arco_motor.premissas import Premissa, Premissas, StatusPremissa
from arco_motor.tipos import Cenario, Modalidade


class ValorInicial(BaseModel):
    """Uma premissa com fonte e o campo da configuração que ela preenche."""

    campo: str = Field(
        description="Caminho do campo em `Configuracao`, como `bateria.disponibilidade`."
    )
    premissa: Premissa = Field(description="Valor, unidade, fonte e status da premissa.")


_CATALOGO: list[tuple[str, str, str, str, str, StatusPremissa, tuple[float, float, float]]] = [
    (
        "bateria.eficiencia_ida_volta",
        "bateria_eficiencia_ida_volta",
        "Fração da energia absorvida que volta para a rede.",
        "fração",
        "NREL 2025 e piso do leilão de reserva de capacidade (0,85); PNNL 2022 medido no "
        "transformador (0,82) e projetado para 2030 (0,88)",
        StatusPremissa.PROPOSTA,
        (0.82, 0.85, 0.88),
    ),
    (
        "bateria.disponibilidade",
        "bateria_disponibilidade",
        "Fração do tempo em que a bateria está disponível para operar.",
        "fração",
        "CAISO 2024 e Lazard LCOE+ 2025. Medem disponibilidade de mercado na ponta, não técnica "
        "anual",
        StatusPremissa.PROPOSTA,
        (0.95, 0.959, 0.98),
    ),
    (
        "bateria.degradacao_por_ciclo",
        "bateria_degradacao_por_ciclo",
        "Fração da capacidade perdida a cada ciclo acumulado.",
        "fração por ciclo a 80 % de profundidade",
        "PNNL 2022: 2.400 ciclos até 80 % da energia (conferido); 2.640 e 4.550 ciclos (lido)",
        StatusPremissa.PROPOSTA,
        (0.000083, 0.000076, 0.000044),
    ),
    (
        "bateria.degradacao_por_ano",
        "bateria_degradacao_por_ano",
        "Fração da capacidade perdida por ano, fora o uso.",
        "fração por ano",
        "Nenhuma fonte deu valor. Zero por decisão de 2026-09-17: é neutro e evita que número sem "
        "fonte carregue o resultado",
        StatusPremissa.NAO_VERIFICADA,
        (0.0, 0.0, 0.0),
    ),
    (
        "bateria.vida_util_anos",
        "bateria_vida_util_anos",
        "Vida útil da bateria, em anos.",
        "anos",
        "20 da EPE PDE 2035 (conferido); 15 do NREL 2025 (conferido); 25 do PNNL 2022 com "
        "reposições (lido)",
        StatusPremissa.PROPOSTA,
        (15, 20, 25),
    ),
    (
        "financeira.taxa_desconto_aa",
        "taxa_desconto",
        "Taxa real de desconto do fluxo de caixa.",
        "fração ao ano",
        "8 % a.a. real por metodologia de WACC, EPE Caderno do PDE 2035 (conferido); 12 % a.a. "
        "como custo do capital próprio, EPE Caderno do PDE 2034 (lido). O otimista repete a "
        "referência porque nenhuma fonte consultada dá taxa menor",
        StatusPremissa.PROPOSTA,
        (0.12, 0.08, 0.08),
    ),
    (
        "financeira.horizonte_anos",
        "transmissao_horizonte_anos",
        "Anos do fluxo de caixa.",
        "anos",
        "25 de vida econômica da EPE (lido); 30 de prazo de concessão (lido); 35 a 37 de vida útil "
        "regulatória, REN ANEEL 474/2012, vigência atual não verificada. O otimista usa 35, o piso "
        "da faixa",
        StatusPremissa.PROPOSTA,
        (25, 30, 35),
    ),
]

_ORDEM = (Cenario.CONSERVADOR, Cenario.REFERENCIA, Cenario.OTIMISTA)

HORIZONTE = "financeira.horizonte_anos"
VIDA_UTIL_DA_BATERIA = "bateria.vida_util_anos"

PREMISSAS_POR_CENARIO: dict[Cenario, list[ValorInicial]] = {
    cenario: [
        ValorInicial(
            campo=campo,
            premissa=Premissa(
                id=id,
                descricao=descricao,
                valor=valores[posicao],
                unidade=unidade,
                # A faixa são os próprios cenários: o que não está validado não sai como número
                # seco. Sai de graça, porque as três colunas já estão aqui.
                faixa=(min(valores), max(valores)),
                fonte=fonte,
                status=status,
            ),
        )
        for campo, id, descricao, unidade, fonte, status, valores in _CATALOGO
    ]
    for posicao, cenario in enumerate(_ORDEM)
}
"""Valor inicial de cada campo, por cenário, sem olhar a modalidade. Todos editáveis."""


def valores_iniciais(cenario: Cenario, modalidade: Modalidade | None = None) -> list[ValorInicial]:
    """Os valores do cenário, ajustados à modalidade.

    **Na modalidade bateria o horizonte é a vida útil da bateria, não o da linha.** O horizonte de
    transmissão passa da vida útil da bateria nos três cenários — 25 contra 15, 30 contra 20, 35
    contra 25 —, e o fluxo credita energia recuperada em todo ano do horizonte: abrir a tela com
    ele somaria cerca de dez anos de benefício de um ativo que este mesmo catálogo diz ter morrido.

    Em equipamento e combinada o horizonte continua o da linha, que é o ativo longo. Na combinada,
    repor a bateria dentro do horizonte é digitado pelo usuário em `reposicoes`: quem devia criar
    essa reposição é a pergunta 11 da spec dos campos, e ninguém a responde chutando aqui.
    """
    valores = PREMISSAS_POR_CENARIO[cenario]
    if modalidade is not Modalidade.BATERIA:
        return valores
    vida = next(valor for valor in valores if valor.campo == VIDA_UTIL_DA_BATERIA)
    horizonte = ValorInicial(
        campo=HORIZONTE,
        premissa=vida.premissa.model_copy(
            update={
                "descricao": "Anos do fluxo de caixa. Sem linha nova no escopo, é a vida útil da "
                "bateria: horizonte maior creditaria recuperação de um ativo já morto."
            }
        ),
    )
    return [horizonte if valor.campo == HORIZONTE else valor for valor in valores]


IDS_POR_CENARIO = {id for _, id, *_ in _CATALOGO}
"""Ids do catálogo por cenário."""


BPR = (
    "Banco de Preços de Referência da ANEEL, Ref. 01/2026, atualizado pela EPE, colunas do "
    "Nordeste; coluna Leilão, que é preço de obra nova, em todos os cenários: a diferença entre "
    "as colunas do BPR é tipo de obra, não incerteza. O valor por km exclui entrada de linha, "
    "interligação de barras, reatores, infraestrutura de subestação e PIS/COFINS, e a leitura "
    "como R$/km é inferência sustentada pelo relatório EPE-DEE-RE-014/2026"
)

_CUSTOS: list[tuple[str, str, str, str, StatusPremissa, tuple[float, float, float], bool]] = [
    (
        "bateria_capex_kwh",
        "Investimento da bateria por kWh de capacidade.",
        "R$/kWh",
        "EPE, Caderno de Parâmetros de Custos do PDE 2035, reais de dezembro de 2024: CAPEX por "
        "kW de bateria de 4 horas (faixa de 5.000 a 9.000 R$/kW), dividido por 4 horas. Só este, "
        "e não R$/kW também: a fonte dá um número só, e usar os dois conta a bateria duas vezes",
        StatusPremissa.PROPOSTA,
        (2250.0, 1375.0, 1250.0),
        True,
    ),
    (
        "linha_500kv_simples_km",
        "Investimento de linha de 500 kV em circuito simples, por km.",
        "R$/km",
        BPR,
        StatusPremissa.PROPOSTA,
        (2471843.0, 2471843.0, 2471843.0),
        False,
    ),
    (
        "linha_230kv_simples_km",
        "Investimento de linha de 230 kV em circuito simples, por km.",
        "R$/km",
        BPR,
        StatusPremissa.PROPOSTA,
        (1334768.0, 1334768.0, 1334768.0),
        False,
    ),
]
"""O último campo diz se a faixa é a dos cenários. Nas linhas não é: as três colunas do BPR são
obras diferentes (substituição, leilão, instalação), e a de leilão vale nos três cenários."""

CUSTOS_POR_CENARIO: dict[Cenario, Premissas] = {
    cenario: Premissas(
        itens={
            id: Premissa(
                id=id,
                descricao=descricao,
                valor=valores[posicao],
                unidade=unidade,
                faixa=(min(valores), max(valores)) if faixa_dos_cenarios else None,
                fonte=fonte,
                status=status,
            )
            for id, descricao, unidade, fonte, status, valores, faixa_dos_cenarios in _CUSTOS
        }
    )
    for posicao, cenario in enumerate(_ORDEM)
}
"""Custo unitário por cenário. Não preenche campo: multiplica quantidade em `montar.py`."""

IDS_DE_CUSTO = {id for id, *_ in _CUSTOS}
