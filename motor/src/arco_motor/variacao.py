"""Variação de uma revisão: uma alavanca muda, o resto fica. Feature 17, marco 1.

O explorador não manda configuração pronta. Manda **a alavanca e o valor** — potência, duração
ou subestação da bateria, ou ganho de limite do circuito —, e a configuração sai daqui, copiada
da revisão de partida. Assim as condições da comparação (preço da energia, taxa de desconto,
cenário e custo unitário) não precisam ser conferidas depois: não há por onde mudarem
([regras do explorador](../../../docs/features/agentes/17-regras-do-explorador.md), seção 2).

O investimento acompanha o tamanho pelo mesmo custo unitário, pela fórmula decidida em
2026-09-22: capex da partida mais a diferença de capacidade em kWh vezes `bateria_capex_kwh` do
cenário da partida, lido aqui do catálogo pelo cenário da partida, e não escolhido por quem chama.
Subestação e ganho de limite não mudam o capex — o circuito custa por km, não por MW de ganho.
Custo fixo de operação acompanha o capex na mesma proporção que tinha na partida. Reposição
acompanha **a parte da bateria**: na combinada o capex inclui a linha, e a reposição é de
módulo de bateria; escalar pelo total barateava justamente a bateria grande.

A faixa permitida (regra 7) entra por parâmetro: ela é da **exploração**, calculada uma vez
sobre a revisão de onde a exploração parte e mostrada à pessoa antes do disparo, e não de cada
rodada. Medida sobre cada rodada, ela andaria oito vezes por rodada, e o que a pessoa confirmou
deixaria de valer.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field

from arco_motor.cenarios import CUSTOS_POR_CENARIO
from arco_motor.montar import KWH_POR_MWH, LinhaDoCadastro, aviso_de_duracao
from arco_motor.premissas import Premissas
from arco_motor.relatorio import numero_br
from arco_motor.tipos import Aviso, Cenario, Configuracao, Modalidade

FATOR_MINIMO_DA_POTENCIA = 0.5
FATOR_MAXIMO_DA_POTENCIA = 8.0
"""A faixa da potência na regra 7, "da metade até 8 vezes a da partida". O 8 é o maior degrau da
grade da árvore de referência (regra 6); o teto do cadastro, se menor, vence."""


class AlavancaFisica(StrEnum):
    """O que o explorador pode variar. Nada financeiro entra aqui, e é essa a trava."""

    POTENCIA = "bateria.potencia_mw"
    DURACAO = "bateria.duracao_horas"
    SUBESTACAO = "bateria.subestacao"
    GANHO = "equipamento.ganho_limite_mw"


class Variacao(BaseModel):
    """Uma alavanca e o valor novo. Potência em MW, duração em horas, ganho em MW."""

    alavanca: AlavancaFisica
    valor: float | str = Field(
        description="Número para potência, duração e ganho; nome do cadastro para subestação."
    )


class Limites(BaseModel):
    minimo: float
    maximo: float

    def contem(self, valor: float) -> bool:
        return self.minimo <= valor <= self.maximo


class FaixaPermitida(BaseModel):
    """O que o explorador pode escolher, alavanca a alavanca. `null` é alavanca fora da
    modalidade, que não varia."""

    potencia_mw: Limites | None = None
    duracao_horas: Limites | None = None
    subestacoes: list[str] | None = None
    ganho_limite_mw: Limites | None = None
    avisos: list[Aviso] = Field(default_factory=list)


class VariacaoMontada(BaseModel):
    configuracao: Configuracao
    avisos: list[Aviso] = Field(
        description="A conta do investimento, quando ele mudou, e a duração fora da faixa."
    )


def teto_do_cadastro_mw(cadastro: list[LinhaDoCadastro], premissas: Premissas) -> float | None:
    """`teto_alavanca_capacidade` vezes a maior capacidade de longa duração das linhas da
    restrição, lida como MW. `None` quando o cadastro não traz capacidade nenhuma: sem número,
    não há teto a aplicar, e quem confere avisa."""
    capacidades = [x.capacidade_longa_mva for x in cadastro if x.capacidade_longa_mva]
    if not capacidades:
        return None
    return float(premissas.valor("teto_alavanca_capacidade")) * max(capacidades)


def faixa_permitida(
    partida: Configuracao, cadastro: list[LinhaDoCadastro], premissas: Premissas
) -> FaixaPermitida:
    """A faixa da regra 7, sobre a revisão de onde a exploração parte.

    - potência: da metade a 8 vezes a da partida, sem passar do teto do cadastro;
    - duração: a faixa de `bateria_duracao_horas`, fora da qual o custo por kWh não foi
      calibrado;
    - subestação: os terminais das linhas autorizadas da restrição, contingenciada inclusive:
      a bateria se prende à restrição, não a um equipamento;
    - ganho de limite: da partida até a capacidade de longa duração da linha que recebe o
      circuito. Sem capacidade no cadastro, o ganho não varia: faixa de um ponto, com aviso.
    """
    faixa = FaixaPermitida()
    teto = teto_do_cadastro_mw(cadastro, premissas)
    if partida.bateria is not None:
        potencia = partida.bateria.potencia_mw
        minimo = potencia * FATOR_MINIMO_DA_POTENCIA
        maximo = potencia * FATOR_MAXIMO_DA_POTENCIA
        if teto is not None:
            maximo = min(maximo, teto)
        if maximo >= minimo:
            faixa.potencia_mw = Limites(minimo=minimo, maximo=maximo)
        else:
            faixa.avisos.append(
                Aviso(
                    codigo="potencia_da_partida_acima_do_teto",
                    mensagem=f"A partida tem {numero_br(potencia)} MW, e o teto pela capacidade "
                    f"da linha é {numero_br(maximo)} MW, abaixo da metade dela: a potência não "
                    "varia nesta exploração.",
                    premissa_id="teto_alavanca_capacidade",
                )
            )
        duracao = premissas.obter("bateria_duracao_horas")
        assert duracao.faixa is not None
        faixa.duracao_horas = Limites(minimo=duracao.faixa[0], maximo=duracao.faixa[1])
        terminais = {x.subestacao_de for x in cadastro} | {x.subestacao_para for x in cadastro}
        faixa.subestacoes = sorted(nome for nome in terminais if nome)
    if partida.equipamento is not None:
        ganho = partida.equipamento.ganho_limite_mw
        linha = next(
            (x for x in cadastro if x.cod_equipamento == partida.equipamento.cod_equipamento),
            None,
        )
        capacidade = linha.capacidade_longa_mva if linha else None
        if not capacidade:
            faixa.ganho_limite_mw = Limites(minimo=ganho, maximo=ganho)
            faixa.avisos.append(
                Aviso(
                    codigo="ganho_sem_capacidade_no_cadastro",
                    mensagem="O cadastro não traz a capacidade de longa duração da linha que "
                    "recebe o circuito, então o ganho de limite fica o da partida: sem ela não "
                    "há teto com que variar.",
                )
            )
        else:
            teto_da_linha = float(premissas.valor("teto_alavanca_capacidade")) * capacidade
            faixa.ganho_limite_mw = Limites(minimo=ganho, maximo=max(ganho, teto_da_linha))
    return faixa


_CAMPO_DA_FAIXA = {
    AlavancaFisica.POTENCIA: "potencia_mw",
    AlavancaFisica.DURACAO: "duracao_horas",
    AlavancaFisica.SUBESTACAO: "subestacoes",
    AlavancaFisica.GANHO: "ganho_limite_mw",
}


def estreitar(faixa: FaixaPermitida, alavancas: list[AlavancaFisica]) -> FaixaPermitida:
    """A faixa com só as alavancas pedidas: "varia só a potência". Estreitar pode; alargar, não
    — alavanca que a faixa não tem, porque a modalidade não a usa, é erro."""
    fora = [a for a in alavancas if getattr(faixa, _CAMPO_DA_FAIXA[a]) is None]
    if fora:
        raise ValueError(
            f"a revisão de partida não tem {', '.join(fora)}: a modalidade dela não usa "
            "essa alavanca"
        )
    return faixa.model_copy(
        update={
            campo: None for alavanca, campo in _CAMPO_DA_FAIXA.items() if alavanca not in alavancas
        }
    )


def montar_variacao(
    partida: Configuracao,
    variacao: Variacao,
    premissas: Premissas,
    faixa: FaixaPermitida,
    custos: Mapping[Cenario, Premissas] = CUSTOS_POR_CENARIO,
) -> VariacaoMontada:
    """A configuração da partida com uma alavanca trocada e o custo que a acompanha.

    `premissas` são as de método (`PREMISSAS_PADRAO`); o custo unitário sai de `custos` no
    cenário **da partida**. Levanta `ValueError` com o limite na mensagem quando a alavanca não
    existe na modalidade ou na exploração, o valor está fora da faixa ou o investimento não se
    sustenta; o texto vai direto para quem pediu.
    """
    alavanca = variacao.alavanca
    if alavanca is AlavancaFisica.GANHO and partida.equipamento is None:
        raise ValueError(f"{alavanca}: a modalidade {partida.modalidade} não tem circuito")
    if alavanca is not AlavancaFisica.GANHO and partida.bateria is None:
        raise ValueError(f"{alavanca}: a modalidade {partida.modalidade} não tem bateria")
    limite = getattr(faixa, _CAMPO_DA_FAIXA[alavanca])
    if limite is None:
        variaveis = [a.value for a, campo in _CAMPO_DA_FAIXA.items() if getattr(faixa, campo)]
        raise ValueError(
            f"{alavanca}: esta exploração não varia essa alavanca; varia "
            f"{', '.join(variaveis) or 'nenhuma'}"
        )

    config = partida.model_copy(deep=True)
    if alavanca is AlavancaFisica.GANHO:
        assert config.equipamento is not None
        ganho = _numero(variacao)
        _dentro(alavanca, ganho, limite, "MW")
        config.equipamento.ganho_limite_mw = ganho
        return VariacaoMontada(
            configuracao=Configuracao.model_validate(config.model_dump()), avisos=[]
        )

    assert config.bateria is not None and partida.bateria is not None
    if alavanca is AlavancaFisica.SUBESTACAO:
        subestacao = str(variacao.valor)
        if subestacao not in limite:
            raise ValueError(
                f"{alavanca}: {subestacao} não é terminal de linha autorizada da restrição; "
                f"as permitidas são {', '.join(limite) or 'nenhuma'}"
            )
        config.bateria.subestacao = subestacao
        return VariacaoMontada(
            configuracao=Configuracao.model_validate(config.model_dump()), avisos=[]
        )

    potencia = partida.bateria.potencia_mw
    duracao = partida.bateria.capacidade_mwh / potencia
    if alavanca is AlavancaFisica.POTENCIA:
        potencia = _numero(variacao)
        _dentro(alavanca, potencia, limite, "MW")
    else:
        duracao = _numero(variacao)
        _dentro(alavanca, duracao, limite, "h")
    capacidade = potencia * duracao
    config.bateria.potencia_mw = potencia
    config.bateria.capacidade_mwh = capacidade
    conta = _reajusta_o_custo(config, partida, capacidade, custos[partida.financeira.cenario])
    return VariacaoMontada(
        configuracao=Configuracao.model_validate(config.model_dump()),
        avisos=[conta, *aviso_de_duracao(capacidade, potencia, premissas)],
    )


def _reajusta_o_custo(
    config: Configuracao, partida: Configuracao, capacidade_mwh: float, custos: Premissas
) -> Aviso:
    """Capex, custo fixo e reposições da variação de tamanho. Devolve o aviso com a conta, que
    a revisão salva guarda: ela grava só o total, e sem isto ninguém refaria a soma."""
    assert partida.bateria is not None
    financeira = partida.financeira
    if financeira.capex_reais <= 0:
        raise ValueError(
            "a revisão de partida tem investimento zero: não há custo que acompanhe o tamanho, "
            "e variar uma bateria de graça daria ganho falso. Informe o investimento na partida."
        )
    custo = custos.obter("bateria_capex_kwh")
    por_kwh = float(custo.valor)
    kwh_partida = partida.bateria.capacidade_mwh * KWH_POR_MWH
    delta_kwh = capacidade_mwh * KWH_POR_MWH - kwh_partida
    capex = financeira.capex_reais + delta_kwh * por_kwh
    # A parte do capex que é bateria: o capex inteiro na modalidade bateria; na combinada, o
    # custo unitário vezes a capacidade da partida, que o capex (com a linha) limita.
    parte = (
        financeira.capex_reais
        if partida.modalidade is Modalidade.BATERIA
        else min(financeira.capex_reais, kwh_partida * por_kwh)
    )
    if capex <= 0 or parte + delta_kwh * por_kwh <= 0:
        raise ValueError(
            f"o investimento ficaria em {numero_br(capex, 0)} reais: reduzir a capacidade tira "
            "pelo custo unitário mais do que a partida tem de bateria "
            f"({numero_br(parte, 0)} reais). Reduza menos, ou parta de outra revisão."
        )
    proporcao = capex / financeira.capex_reais
    proporcao_da_bateria = (parte + delta_kwh * por_kwh) / parte
    config.financeira.capex_reais = capex
    config.financeira.opex_fixo_reais_ano = financeira.opex_fixo_reais_ano * proporcao
    for reposicao, original in zip(
        config.financeira.reposicoes, financeira.reposicoes, strict=True
    ):
        reposicao.valor_reais = original.valor_reais * proporcao_da_bateria
    sinal = "mais" if delta_kwh >= 0 else "menos"
    return Aviso(
        codigo="investimento_por_custo_unitario",
        mensagem="Investimento montado pelo custo unitário: "
        f"{numero_br(financeira.capex_reais, 0)} reais da partida, {sinal} "
        f"{numero_br(abs(delta_kwh), 0)} kWh vezes "
        f"{numero_br(por_kwh)} R$/kWh do cenário {financeira.cenario}, dá "
        f"{numero_br(capex, 0)} reais. Custo fixo de operação acompanhou o investimento, e "
        "reposições, a parte da bateria.",
        premissa_id=custo.id,
    )


def _numero(variacao: Variacao) -> float:
    if isinstance(variacao.valor, str):
        try:
            return float(variacao.valor)
        except ValueError as erro:
            raise ValueError(
                f"{variacao.alavanca}: esperava número, veio {variacao.valor!r}"
            ) from erro
    return float(variacao.valor)


def _dentro(alavanca: AlavancaFisica, valor: float, faixa: Limites, unidade: str) -> None:
    if not faixa.contem(valor):
        raise ValueError(
            f"{alavanca}: {numero_br(valor)} {unidade} está fora da faixa permitida, de "
            f"{numero_br(faixa.minimo)} a {numero_br(faixa.maximo)} {unidade}"
        )
