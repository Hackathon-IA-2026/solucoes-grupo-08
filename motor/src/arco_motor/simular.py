"""Orquestra uma simulação: equipamento, depois bateria sobre o residual, depois a conta.

Invariantes que a implementação mantém, testados em tests/test_invariantes.py:
- em todo intervalo, evitado_equipamento + absorvido_bateria <= cortado;
- a mesma energia nunca é creditada às duas intervenções;
- estado de carga sempre entre soc_min e soc_max da capacidade;
- mais ganho de limite nunca recupera menos;
- o resultado carimba metodo_versao, snapshot_id, restricao_id e premissas_usadas.
"""

from __future__ import annotations

from arco_motor import bateria as _bateria
from arco_motor import diagnosticos as _diagnosticos
from arco_motor import economia as _economia
from arco_motor import equipamento as _equipamento
from arco_motor.premissas import PREMISSAS_PADRAO, Premissa, Premissas, StatusPremissa
from arco_motor.tipos import (
    PASSO_HORAS,
    Aviso,
    Configuracao,
    Modalidade,
    Resultado,
    ResultadoTecnico,
    SerieRestricao,
)
from arco_motor.versao import METODO_VERSAO

DIAS_NO_MES = 365.25 / 12.0


def meses_da_serie(serie: SerieRestricao) -> float:
    """Extensão da janela analisada, em meses. Sem relógio: sai do que a série declara.

    Contar linhas daria errado, porque a série é esparsa: um ano de histórico com três mil
    meias horas de corte pareceria dois meses, e a anualização inflaria tudo por cinco.
    """
    return serie.horas_no_periodo / 24.0 / DIAS_NO_MES


def _premissas_usadas(config: Configuracao, premissas: Premissas) -> dict[str, Premissa]:
    # `fonte_geracao` entra sempre, e o motor não a lê: quem filtra a série pela fonte é quem a
    # monta, antes daqui. Ela é carimbada porque é entrada do cálculo — duas execuções com a
    # mesma configuração e fontes diferentes dão números diferentes, e sem o carimbo nada explica.
    ids = ["fonte_geracao", "correcao_minutos", "preco_energia", "anualizacao"]
    if config.equipamento is not None:
        ids.append("sensibilidade_equipamento")
    if config.bateria is not None:
        ids += ["despacho_bateria", "bateria_carrega_so_do_corte"]
    if config.modalidade is Modalidade.COMBINADA:
        ids.append("ordem_combinada")
    # A sensibilidade é a premissa mais exposta do produto: aparece sempre, para auditoria.
    if "sensibilidade_equipamento" not in ids:
        ids.append("sensibilidade_equipamento")
    return {id: premissas.obter(id) for id in ids}


def _avisos(
    serie: SerieRestricao, config: Configuracao, premissas: Premissas, usadas: dict[str, Premissa]
) -> list[Aviso]:
    avisos: list[Aviso] = []
    sensibilidade = usadas["sensibilidade_equipamento"]
    if config.equipamento is not None and sensibilidade.status is not StatusPremissa.VALIDADA:
        avisos.append(
            Aviso(
                codigo="sensibilidade_nao_validada",
                mensagem="1 MW a mais no limite evita até 1 MW de corte. A sensibilidade real "
                "depende da rede e não foi estimada; no eixo onde está quase toda a energia do "
                "escopo o limite é de tensão, e a validação com engenheiro está pendente.",
                premissa_id="sensibilidade_equipamento",
            )
        )
    if bool(premissas.valor("correcao_minutos")) and all(
        intervalo.minutos_cnf is None for intervalo in serie.intervalos
    ):
        avisos.append(
            Aviso(
                codigo="correcao_minutos_sem_dado",
                mensagem="A correção pela duração está ligada, mas nenhum intervalo trouxe "
                "minutos_cnf. O cálculo usou a média da meia hora, o que superestima as duas "
                "alavancas quando o corte durou menos de 30 minutos.",
                premissa_id="correcao_minutos",
            )
        )
    if config.bateria is not None and config.bateria.degradacao_por_ano > 0:
        avisos.append(
            Aviso(
                codigo="degradacao_por_ano_fora_da_replica",
                mensagem="A degradação por calendário não entra na réplica do histórico, que "
                "refaz um período só. Ela pertence à conta do horizonte.",
            )
        )
    return avisos


def simular(
    serie: SerieRestricao,
    config: Configuracao,
    premissas: Premissas = PREMISSAS_PADRAO,
) -> Resultado:
    """Calcula uma simulação sobre o histórico observado, sob a configuração informada."""
    cortado_mw = [intervalo.corte_mw for intervalo in serie.intervalos]

    if config.equipamento is not None:
        evitado_mw, residual_apos_equipamento = _equipamento.aplicar(
            serie, config.equipamento, premissas
        )
    else:
        evitado_mw = [0.0] * len(cortado_mw)
        residual_apos_equipamento = list(cortado_mw)

    if config.bateria is not None:
        absorvido_mw, devolvido_mw, soc_mwh = _bateria.simular(
            residual_apos_equipamento, config.bateria, premissas, serie.intervalos
        )
    else:
        absorvido_mw = [0.0] * len(cortado_mw)
        devolvido_mw = [0.0] * len(cortado_mw)
        soc_mwh = [0.0] * len(cortado_mw)

    residual_mw = [
        residual - absorvido
        for residual, absorvido in zip(residual_apos_equipamento, absorvido_mw, strict=True)
    ]

    energia_cortada = sum(cortado_mw) * PASSO_HORAS
    energia_evitada = sum(evitado_mw) * PASSO_HORAS
    energia_absorvida = sum(absorvido_mw) * PASSO_HORAS
    energia_recuperada = energia_evitada + energia_absorvida
    fracao = energia_recuperada / energia_cortada if energia_cortada > 0 else 0.0

    tecnico = ResultadoTecnico(
        cortado_mw=cortado_mw,
        evitado_equipamento_mw=evitado_mw,
        absorvido_bateria_mw=absorvido_mw,
        devolvido_bateria_mw=devolvido_mw,
        residual_mw=residual_mw,
        soc_mwh=soc_mwh,
        energia_cortada_mwh=energia_cortada,
        energia_evitada_equipamento_mwh=energia_evitada,
        energia_absorvida_bateria_mwh=energia_absorvida,
        energia_devolvida_bateria_mwh=sum(devolvido_mw) * PASSO_HORAS,
        energia_recuperada_mwh=energia_recuperada,
        fracao_recuperada=min(max(fracao, 0.0), 1.0),
    )

    financeiro = _economia.calcular(tecnico, config.financeira, meses_da_serie(serie), premissas)
    usadas = _premissas_usadas(config, premissas)
    diagnosticos = _diagnosticos.diagnosticar(serie, config, tecnico)

    return Resultado(
        metodo_versao=METODO_VERSAO,
        snapshot_id=serie.snapshot_id,
        restricao_id=serie.restricao_id,
        tecnico=tecnico,
        financeiro=financeiro,
        premissas_usadas=usadas,
        avisos=_avisos(serie, config, premissas, usadas),
        diagnosticos=diagnosticos,
    )
