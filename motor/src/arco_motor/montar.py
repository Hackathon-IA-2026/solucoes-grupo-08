"""A configuração inteira de uma simulação nova, a partir da alavanca. Feature 17, marco 1.

Quem monta uma simulação escolhe o que instalar — a alavanca: potência, capacidade e subestação
da bateria, ou a linha e o ganho de limite do circuito novo — e o cenário. O resto sai daqui, e
cada valor sai com a premissa, a fonte e o status: os valores iniciais do cenário
(`cenarios.valores_iniciais`), os padrões do tipo (`tipos.py`) e o investimento inicial por
custo unitário vezes quantidade, com a conta à vista. É o cartão que o chat mostra antes de
salvar, e a resposta à pergunta 4 da feature 04: de que custo e de que quantidade o investimento
saiu.

**Fórmula do investimento, decidida em 2026-09-22 na jornada da feature 17.** Bateria é
`bateria_capex_kwh` vezes a capacidade em kWh, e não R$/kW vezes potência também: a fonte dá um
número só, para bateria de 4 horas, e o R$/kWh do catálogo é ele dividido por 4. Fora de
`bateria_duracao_horas` o custo unitário não foi calibrado, e sai aviso. Linha é
`linha_<tensao>_simples_km`, coluna de leilão, vezes o comprimento do cadastro.

Não calcula nada da simulação e não lê cadastro: a linha escolhida chega por parâmetro, como a
rota a leu. Puro, como o resto do motor.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from arco_motor.cenarios import CUSTOS_POR_CENARIO, valores_iniciais
from arco_motor.premissas import Premissa, Premissas, StatusPremissa
from arco_motor.relatorio import numero_br
from arco_motor.tipos import (
    Aviso,
    Cenario,
    ConfigBateria,
    ConfigEquipamento,
    ConfigFinanceira,
    Configuracao,
    Modalidade,
    Reposicao,
    TipoIntervencao,
)

KWH_POR_MWH = 1000.0

PADRAO_DO_TIPO = (
    "padrão do tipo em motor/src/arco_motor/tipos.py, sem fonte e sem validação. Custo zero não "
    "é neutro: favorece o VPL"
)


class LinhaDoCadastro(BaseModel):
    """Uma linha da restrição como o cadastro do ONS a descreve, no snapshot do cálculo."""

    cod_equipamento: str
    papel: str = Field(description="`monitorado` ou `contingenciado`, do texto da restrição.")
    tensao_kv: int | None = None
    comprimento_km: float | None = None
    capacidade_longa_mva: float | None = Field(
        default=None, description="Capacidade de longa duração sem limitação, em MVA."
    )
    subestacao_de: str | None = None
    subestacao_para: str | None = None


class EscolhaDaBateria(BaseModel):
    potencia_mw: float = Field(gt=0)
    capacidade_mwh: float = Field(gt=0)
    subestacao: str = Field(min_length=1)


class EscolhaDoCircuito(BaseModel):
    cod_equipamento: str = Field(min_length=1)
    ganho_limite_mw: float = Field(ge=0)


class Alavanca(BaseModel):
    """O que se instala. O bloco que a modalidade pede é obrigatório, e o outro, proibido — a
    mesma regra de `Configuracao`, conferida em `montar_configuracao`."""

    bateria: EscolhaDaBateria | None = None
    circuito: EscolhaDoCircuito | None = None


class OrigemDoCampo(StrEnum):
    ESCOLHA = "escolha"
    """Quem monta escolheu: modalidade, cenário e a alavanca. Não é premissa."""
    CENARIO = "cenario"
    CUSTO_UNITARIO = "custo_unitario"
    METODO = "metodo"
    PADRAO_DO_TIPO = "padrao_do_tipo"


class CampoMontado(BaseModel):
    """Um campo da configuração com o que o sustenta."""

    campo: str = Field(description="Caminho em `Configuracao`, como `bateria.disponibilidade`.")
    valor: float | int | str | list[Reposicao] | None
    origem: OrigemDoCampo
    premissa_id: str | None = Field(
        description="A premissa que deu o valor. `null` na escolha e no padrão do tipo."
    )
    unidade: str | None = None
    fonte: str | None = Field(description="`null` só na escolha, que não é premissa.")
    status: StatusPremissa | None = Field(description="`null` só na escolha.")


class ParcelaDoInvestimento(BaseModel):
    """Custo unitário vezes quantidade, uma parcela por intervenção."""

    intervencao: str = Field(description="`bateria` ou `circuito`.")
    custo_unitario: Premissa | None = Field(
        description="`null` quando não há custo unitário para o caso, e aí a parcela é zero."
    )
    quantidade: float | None = Field(description="kWh da bateria ou km da linha.")
    unidade_da_quantidade: str
    valor_reais: float = Field(description="Zero quando a parcela não pôde ser estimada.")
    faixa_reais: tuple[float, float] | None = Field(
        description="A faixa do custo unitário vezes a quantidade, quando o custo tem faixa."
    )
    estimada: bool = Field(description="Falso quando faltou custo unitário ou quantidade.")


class ConfiguracaoMontada(BaseModel):
    configuracao: Configuracao
    campos: list[CampoMontado] = Field(description="Toda folha da configuração, em ordem.")
    investimento: list[ParcelaDoInvestimento] = Field(
        description="As parcelas que somam `financeira.capex_reais`."
    )
    avisos: list[Aviso]


def custo_da_linha(tensao_kv: int | None) -> str:
    return f"linha_{tensao_kv}kv_simples_km"


def montar_configuracao(
    modalidade: Modalidade,
    cenario: Cenario,
    alavanca: Alavanca,
    premissas: Premissas,
    cadastro: list[LinhaDoCadastro],
    custos: Mapping[Cenario, Premissas] = CUSTOS_POR_CENARIO,
) -> ConfiguracaoMontada:
    """A configuração inteira de uma simulação nova, com cada valor e o que o sustenta.

    `premissas` são as de método (`PREMISSAS_PADRAO`); o custo unitário é o de `custos` **no
    cenário pedido**, lido aqui e não escolhido por quem chama, para cenário e custo não se
    desencontrarem. `cadastro` são as linhas autorizadas da restrição; a do circuito tem de
    estar entre elas. Conferir se ela é a monitorada é da rota, que tem o papel de cada uma.
    """
    precisa_bateria = modalidade in (Modalidade.BATERIA, Modalidade.COMBINADA)
    precisa_circuito = modalidade in (Modalidade.EQUIPAMENTO, Modalidade.COMBINADA)
    if precisa_bateria != (alavanca.bateria is not None):
        raise ValueError(
            f"modalidade {modalidade} {'exige' if precisa_bateria else 'não aceita'} bateria"
        )
    if precisa_circuito != (alavanca.circuito is not None):
        raise ValueError(
            f"modalidade {modalidade} {'exige' if precisa_circuito else 'não aceita'} circuito"
        )
    iniciais = {v.campo: v.premissa for v in valores_iniciais(cenario, modalidade)}
    campos: list[CampoMontado] = []
    avisos: list[Aviso] = []
    parcelas: list[ParcelaDoInvestimento] = []

    def escolha(campo: str, valor: Any) -> Any:
        campos.append(
            CampoMontado(
                campo=campo,
                valor=valor,
                origem=OrigemDoCampo.ESCOLHA,
                premissa_id=None,
                fonte=None,
                status=None,
            )
        )
        return valor

    def do_cenario(campo: str) -> Any:
        premissa = iniciais[campo]
        campos.append(_de_premissa(campo, premissa, OrigemDoCampo.CENARIO))
        return premissa.valor

    def do_tipo(campo: str, valor: Any) -> Any:
        campos.append(
            CampoMontado(
                campo=campo,
                valor=valor,
                origem=OrigemDoCampo.PADRAO_DO_TIPO,
                premissa_id=None,
                fonte=PADRAO_DO_TIPO,
                status=StatusPremissa.NAO_VERIFICADA,
            )
        )
        return valor

    escolha("modalidade", modalidade.value)

    bateria: ConfigBateria | None = None
    if alavanca.bateria is not None:
        b = alavanca.bateria
        padrao = ConfigBateria(potencia_mw=1, capacidade_mwh=1, subestacao="-")
        bateria = ConfigBateria(
            potencia_mw=escolha("bateria.potencia_mw", b.potencia_mw),
            capacidade_mwh=escolha("bateria.capacidade_mwh", b.capacidade_mwh),
            subestacao=escolha("bateria.subestacao", b.subestacao),
            soc_inicial=do_tipo("bateria.soc_inicial", padrao.soc_inicial),
            soc_min=do_tipo("bateria.soc_min", padrao.soc_min),
            soc_max=do_tipo("bateria.soc_max", padrao.soc_max),
            eficiencia_ida_volta=do_cenario("bateria.eficiencia_ida_volta"),
            disponibilidade=do_cenario("bateria.disponibilidade"),
            degradacao_por_ciclo=do_cenario("bateria.degradacao_por_ciclo"),
            degradacao_por_ano=do_cenario("bateria.degradacao_por_ano"),
            vida_util_anos=int(do_cenario("bateria.vida_util_anos")),
        )
        parcela, aviso = _parcela_da_bateria(b, custos[cenario], premissas)
        parcelas.append(parcela)
        avisos += aviso

    equipamento: ConfigEquipamento | None = None
    if alavanca.circuito is not None:
        c = alavanca.circuito
        linha = next((x for x in cadastro if x.cod_equipamento == c.cod_equipamento), None)
        if linha is None:
            raise ValueError(f"linha {c.cod_equipamento} fora do cadastro da restrição")
        padrao_eq = ConfigEquipamento(
            tipo=TipoIntervencao.ADICAO_CIRCUITO, cod_equipamento="-", ganho_limite_mw=0
        )
        equipamento = ConfigEquipamento(
            tipo=TipoIntervencao(
                escolha("equipamento.tipo", TipoIntervencao.ADICAO_CIRCUITO.value)
            ),
            cod_equipamento=escolha("equipamento.cod_equipamento", c.cod_equipamento),
            capacidade_depois_mva=do_tipo(
                "equipamento.capacidade_depois_mva", padrao_eq.capacidade_depois_mva
            ),
            ganho_limite_mw=escolha("equipamento.ganho_limite_mw", c.ganho_limite_mw),
            disponibilidade=do_tipo("equipamento.disponibilidade", padrao_eq.disponibilidade),
            vida_util_anos=do_tipo("equipamento.vida_util_anos", padrao_eq.vida_util_anos),
        )
        parcela, aviso = _parcela_da_linha(linha, custos[cenario])
        parcelas.append(parcela)
        avisos += aviso

    capex = sum(p.valor_reais for p in parcelas)
    padrao_fin = ConfigFinanceira(
        cenario=cenario, taxa_desconto_aa=0, horizonte_anos=1, capex_reais=0
    )
    preco = premissas.obter("preco_energia")
    financeira = ConfigFinanceira(
        cenario=Cenario(escolha("financeira.cenario", cenario.value)),
        taxa_desconto_aa=do_cenario("financeira.taxa_desconto_aa"),
        horizonte_anos=int(do_cenario("financeira.horizonte_anos")),
        capex_reais=capex,
        opex_fixo_reais_ano=do_tipo(
            "financeira.opex_fixo_reais_ano", padrao_fin.opex_fixo_reais_ano
        ),
        opex_variavel_reais_mwh=do_tipo(
            "financeira.opex_variavel_reais_mwh", padrao_fin.opex_variavel_reais_mwh
        ),
        reposicoes=do_tipo("financeira.reposicoes", list(padrao_fin.reposicoes)),
        valor_residual_reais=do_tipo(
            "financeira.valor_residual_reais", padrao_fin.valor_residual_reais
        ),
        # Vazio de propósito: o cálculo cai na premissa `preco_energia`, e é ela que o campo
        # mostra. Preencher com o número a transformaria em valor digitado, que vence a premissa
        # e sai do carimbo com o status dela.
        preco_energia_reais_mwh=None,
        receitas_adicionais_reais_ano=do_tipo(
            "financeira.receitas_adicionais_reais_ano", padrao_fin.receitas_adicionais_reais_ano
        ),
    )
    campos.append(_capex(capex, parcelas))
    campos.append(
        CampoMontado(
            campo="financeira.preco_energia_reais_mwh",
            valor=None,
            origem=OrigemDoCampo.METODO,
            premissa_id=preco.id,
            unidade=preco.unidade,
            fonte=preco.fonte,
            status=preco.status,
        )
    )
    configuracao = Configuracao(
        modalidade=modalidade, bateria=bateria, equipamento=equipamento, financeira=financeira
    )
    avisos.append(
        Aviso(
            codigo="custos_de_operacao_zerados",
            mensagem="Custo fixo de operação, reposições e valor residual entraram no padrão do "
            "tipo, zero e sem fonte, e custo zero favorece o VPL. O registro de premissas tem "
            "custo de operação e de reposição com fonte (bateria_om_kw_ano, "
            "bateria_reposicao_pct_capex_kwh, transmissao_custo_anual_pct_investimento), que a "
            "montagem ainda não aplica: informe-os antes de ler o VPL.",
        )
    )
    return ConfiguracaoMontada(
        configuracao=configuracao, campos=campos, investimento=parcelas, avisos=avisos
    )


def _de_premissa(campo: str, premissa: Premissa, origem: OrigemDoCampo) -> CampoMontado:
    return CampoMontado(
        campo=campo,
        valor=premissa.valor,
        origem=origem,
        premissa_id=premissa.id,
        unidade=premissa.unidade,
        fonte=premissa.fonte,
        status=premissa.status,
    )


def _capex(capex: float, parcelas: list[ParcelaDoInvestimento]) -> CampoMontado:
    """O investimento aponta para os custos unitários de que saiu; a conta está em
    `investimento`. O status é o pior entre as parcelas, e parcela não estimada rebaixa a
    `nao_verificada`: um total com pedaço faltando não é proposta de ninguém."""
    ordem = [StatusPremissa.NAO_VERIFICADA, StatusPremissa.PROPOSTA, StatusPremissa.VALIDADA]
    status = [
        p.custo_unitario.status
        if p.estimada and p.custo_unitario
        else StatusPremissa.NAO_VERIFICADA
        for p in parcelas
    ]
    ids = [p.custo_unitario.id for p in parcelas if p.custo_unitario is not None]
    return CampoMontado(
        campo="financeira.capex_reais",
        valor=capex,
        origem=OrigemDoCampo.CUSTO_UNITARIO,
        premissa_id=" + ".join(ids) or None,
        unidade="R$",
        fonte="custo unitário vezes quantidade; a conta de cada parcela está em `investimento`",
        status=min(status, key=ordem.index) if status else StatusPremissa.NAO_VERIFICADA,
    )


def aviso_de_duracao(
    capacidade_mwh: float, potencia_mw: float, premissas: Premissas
) -> list[Aviso]:
    """Aviso quando a duração sai da faixa de `bateria_duracao_horas`: o custo por kWh é o da EPE
    para 4 horas, e a faixa do investimento, a dos cenários, não inclui o erro da duração."""
    duracao = premissas.obter("bateria_duracao_horas")
    horas = capacidade_mwh / potencia_mw
    if duracao.faixa is None or duracao.faixa[0] <= horas <= duracao.faixa[1]:
        return []
    minimo, maximo = duracao.faixa
    lado = (
        f"abaixo de {numero_br(minimo)} h" if horas < minimo else f"acima de {numero_br(maximo)} h"
    )
    return [
        Aviso(
            codigo="duracao_fora_da_calibracao",
            mensagem=f"O custo por kWh vem da EPE para bateria de {duracao.valor} horas, e esta "
            f"tem {numero_br(horas, 2)} h, {lado}: fora da faixa de {numero_br(minimo)} a "
            f"{numero_br(maximo)} h, adotada sem fonte, o investimento vale como ordem de "
            "grandeza. A faixa mostrada é a dos cenários do custo e não inclui o erro da "
            "duração.",
            premissa_id=duracao.id,
        )
    ]


def _parcela_da_bateria(
    bateria: EscolhaDaBateria, custos: Premissas, premissas: Premissas
) -> tuple[ParcelaDoInvestimento, list[Aviso]]:
    custo = custos.obter("bateria_capex_kwh")
    kwh = bateria.capacidade_mwh * KWH_POR_MWH
    por_kwh = float(custo.valor)
    avisos = aviso_de_duracao(bateria.capacidade_mwh, bateria.potencia_mw, premissas)
    return (
        ParcelaDoInvestimento(
            intervencao="bateria",
            custo_unitario=custo,
            quantidade=kwh,
            unidade_da_quantidade="kWh",
            valor_reais=kwh * por_kwh,
            faixa_reais=(kwh * custo.faixa[0], kwh * custo.faixa[1]) if custo.faixa else None,
            estimada=True,
        ),
        avisos,
    )


def _parcela_da_linha(
    linha: LinhaDoCadastro, custos: Premissas
) -> tuple[ParcelaDoInvestimento, list[Aviso]]:
    """Sem custo unitário para a tensão, ou sem comprimento no cadastro, a parcela é zero e sai
    aviso: número sem fonte não entra no investimento, e quem monta digita o valor. Com os
    dois, a parcela sai com o aviso do que o custo por km não cobre."""
    id = custo_da_linha(linha.tensao_kv)
    custo = custos.itens.get(id)
    km = linha.comprimento_km
    falta: str | None = None
    if custo is None:
        falta = f"não há custo unitário registrado para linha de {linha.tensao_kv} kV ({id})"
    elif km is None or km <= 0:
        falta = f"o cadastro não traz o comprimento de {linha.cod_equipamento}"
    if falta is not None:
        return (
            ParcelaDoInvestimento(
                intervencao="circuito",
                custo_unitario=custo,
                quantidade=km,
                unidade_da_quantidade="km",
                valor_reais=0.0,
                faixa_reais=None,
                estimada=False,
            ),
            [
                Aviso(
                    codigo="investimento_do_circuito_nao_estimado",
                    mensagem=f"O investimento do circuito novo não foi estimado: {falta}. A "
                    "parcela entrou como zero; informe o investimento antes de ler o VPL.",
                    premissa_id=id if custo is not None else None,
                )
            ],
        )
    assert custo is not None and km is not None
    por_km = float(custo.valor)
    return (
        ParcelaDoInvestimento(
            intervencao="circuito",
            custo_unitario=custo,
            quantidade=km,
            unidade_da_quantidade="km",
            valor_reais=km * por_km,
            faixa_reais=(km * custo.faixa[0], km * custo.faixa[1]) if custo.faixa else None,
            estimada=True,
        ),
        [
            Aviso(
                codigo="investimento_do_circuito_parcial",
                mensagem="O custo por km do BPR exclui entrada de linha, interligação de barras, "
                "reatores, infraestrutura de subestação e PIS/COFINS, e o comprimento do circuito "
                f"novo foi suposto igual ao da linha existente, {numero_br(km)} km: o "
                "investimento do circuito está subestimado.",
                premissa_id=id,
            )
        ],
    )
