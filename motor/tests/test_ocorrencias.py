"""Agrupamento de intervalos em ocorrências.

A armadilha que estes testes guardam: a série do ONS é esparsa, e agrupar por vizinhança de
linha juntaria o corte de segunda com o de sexta num episódio só.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from arco_motor.equipamento import fator_pico
from arco_motor.ocorrencias import agrupar
from arco_motor.premissas import PREMISSAS_PADRAO
from arco_motor.tipos import Intervalo, SerieRestricao

INICIO = datetime(2026, 1, 1)


def serie(*, corte_por_instante: dict[datetime, float]) -> SerieRestricao:
    return SerieRestricao(
        restricao_id="teste",
        snapshot_id="teste",
        intervalos=[
            Intervalo(instante=i, corte_mw=mw) for i, mw in sorted(corte_por_instante.items())
        ],
    )


def esparsa(*offsets_em_meias_horas: int, corte_mw: float = 100.0) -> SerieRestricao:
    """Série sem as meias horas de folga, que é a forma em que o ONS entrega."""
    return serie(
        corte_por_instante={
            INICIO + timedelta(minutes=30 * k): corte_mw for k in offsets_em_meias_horas
        }
    )


def test_caso_de_ouro_dois_dias(serie_dois_dias: SerieRestricao) -> None:
    """Corte de 100 MW das 20h às 5h, dois dias, série densa começando em 01/01 00:00.

    À mão, com a noite atravessando a meia-noite:

    - 01/01 00:00 a 04:30, 10 meias horas -> 5 h x 100 MW = 500 MWh
    - 01/01 20:00 a 02/01 04:30, 18 meias horas -> 9 h x 100 MW = 900 MWh
    - 02/01 20:00 a 23:30, 8 meias horas -> 4 h x 100 MW = 400 MWh

    Três ocorrências, 1.800 MWh, que é a energia da série inteira. A do meio prova que a
    virada do dia não parte o episódio.
    """
    ocorrencias = agrupar(serie_dois_dias, PREMISSAS_PADRAO)

    assert [o.intervalos for o in ocorrencias] == [10, 18, 8]
    assert [o.energia_mwh for o in ocorrencias] == [500.0, 900.0, 400.0]
    assert [o.duracao_horas for o in ocorrencias] == [5.0, 9.0, 4.0]
    assert ocorrencias[1].inicio == datetime(2026, 1, 1, 20, 0)
    assert ocorrencias[1].fim == datetime(2026, 1, 2, 5, 0)
    assert sum(o.energia_mwh for o in ocorrencias) == serie_dois_dias.energia_cortada_mwh


def test_folga_de_uma_meia_hora_parte_a_ocorrencia() -> None:
    """Folga zero é o padrão do invariante: 30 minutos sem corte já são dois episódios."""
    ocorrencias = agrupar(esparsa(0, 1, 3, 4), PREMISSAS_PADRAO)

    assert [o.intervalos for o in ocorrencias] == [2, 2]
    assert ocorrencias[0].fim == INICIO + timedelta(hours=1)
    assert ocorrencias[1].inicio == INICIO + timedelta(hours=1, minutes=30)


def test_tolerancia_de_um_intervalo_mantem_inteira() -> None:
    """A mesma série, com a premissa em 1, é um episódio só — e a folga conta na duração."""
    premissas = PREMISSAS_PADRAO.com(regra_ocorrencia_intervalos_tolerados=1)

    ocorrencias = agrupar(esparsa(0, 1, 3, 4), premissas)

    assert len(ocorrencias) == 1
    assert ocorrencias[0].intervalos == 4
    assert ocorrencias[0].duracao_horas == 2.5


def test_serie_esparsa_nao_junta_por_vizinhanca_de_linha() -> None:
    """Segunda e sexta são vizinhas na lista e não podem virar o mesmo episódio."""
    segunda = INICIO
    sexta = INICIO + timedelta(days=4)
    ocorrencias = agrupar(serie(corte_por_instante={segunda: 80.0, sexta: 90.0}), PREMISSAS_PADRAO)

    assert len(ocorrencias) == 2
    assert [o.corte_medio_maximo_mw for o in ocorrencias] == [80.0, 90.0]


def test_intervalo_sem_corte_nao_abre_ocorrencia() -> None:
    """Série densa: a meia hora de corte zero separa, e não entra na contagem.

    Não é caso só de teste: o dado do ONS traz meia hora com corte zero. No snapshot de
    2026-09-21, eólica, são 303 delas — uma na própria LT 500 kV Açu III / Jaguaruana II, em
    04/09/2025 18:30. Esparsa não quer dizer que toda linha tenha corte.
    """
    densa = serie(
        corte_por_instante={
            INICIO: 10.0,
            INICIO + timedelta(minutes=30): 0.0,
            INICIO + timedelta(hours=1): 10.0,
        }
    )

    assert [o.intervalos for o in agrupar(densa, PREMISSAS_PADRAO)] == [1, 1]


def test_serie_vazia() -> None:
    assert agrupar(serie(corte_por_instante={}), PREMISSAS_PADRAO) == []


@given(
    offsets=st.lists(st.integers(min_value=0, max_value=200), min_size=1, max_size=60, unique=True)
)
def test_invariante_a_energia_se_conserva(offsets: list[int]) -> None:
    """Agrupar não cria nem destrói energia: a soma das ocorrências é a soma da série."""
    s = esparsa(*sorted(offsets))

    ocorrencias = agrupar(s, PREMISSAS_PADRAO)

    assert sum(o.energia_mwh for o in ocorrencias) == s.energia_cortada_mwh
    assert sum(o.intervalos for o in ocorrencias) == len(s.intervalos)


def test_corte_medio_maximo_nao_e_o_pico() -> None:
    """O nome do campo tem de doer: a série do ONS é média da meia hora, não pico.

    Cem MW médios com 10 minutos de corte são 300 MW de pico, pela conta do próprio motor
    (`fator_pico` = 30 / minutos_cnf, com `correcao_minutos` ligada, que é o padrão). A
    ocorrência mostra 120, que é a maior **média**, e é contra os 300 que a simulação
    dimensiona a alavanca. Quem audita o episódio precisa saber que os dois números medem
    coisas diferentes.
    """
    serie_com_minutos = SerieRestricao(
        restricao_id="teste",
        snapshot_id="teste",
        intervalos=[
            Intervalo(instante=INICIO, corte_mw=100.0, minutos_cnf=10),
            Intervalo(instante=INICIO + timedelta(minutes=30), corte_mw=120.0, minutos_cnf=30),
        ],
    )

    unica = agrupar(serie_com_minutos, PREMISSAS_PADRAO)[0]

    assert unica.corte_medio_maximo_mw == 120.0
    picos = [i.corte_mw * fator_pico(i, corrigir=True) for i in serie_com_minutos.intervalos]
    assert picos == [300.0, 120.0]
    assert max(picos) > unica.corte_medio_maximo_mw
