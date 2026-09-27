"""A árvore de referência: o explorador sem modelo, com tudo predefinido (regra 6).

É a régua do conjunto de avaliação: o agente só se justifica se, com o mesmo teto de revisões,
responder o pedido melhor que ela
([regras do explorador](../../../docs/features/agentes/17-regras-do-explorador.md), seção 6).
Decide pelo mesmo laço e pelas mesmas ferramentas do explorador (`explorador.Explorador`), e
nenhuma escolha dela depende de modelo:

1. **Grade de tamanhos**, a partir da revisão de partida: 1,5, 2, 3, 4, 6 e 8 vezes a alavanca,
   dentro da faixa permitida, mais a conexão da bateria em cada outra subestação permitida, com
   o tamanho de partida. Na combinada, primeiro o ganho de limite e depois a bateria, na ordem
   em que o motor calcula: uma rodada para cada.
2. **Ponto de apoio**, por código: o maior tamanho da grade de potência em que a fração
   recuperada ainda sobe pelo menos 5 pontos percentuais em relação ao degrau anterior.
3. **Duração** a partir do ponto de apoio: 2 e 6 horas de potência.
4. Encerra, e o encerramento pede o relatório.
"""

from __future__ import annotations

import itertools

from arco_agentes.explorador import Decisao, Situacao, VariacaoDecidida

MULTIPLOS = (1.5, 2.0, 3.0, 4.0, 6.0, 8.0)
"""Os degraus da grade, regra 6. O 8 é também o topo da faixa de potência (regra 7)."""

DEGRAU_MINIMO = 0.05
"""Quanto a fração recuperada tem de subir de um degrau para o seguinte, em fração de 0 a 1,
para o degrau ainda contar como apoio: os 5 pontos percentuais da regra 6."""

DURACOES_HORAS = (2.0, 6.0)
"""As durações testadas a partir do ponto de apoio, regra 6: as pontas da faixa permitida."""

LOTE_MAXIMO = 10

POTENCIA = "bateria.potencia_mw"
GANHO = "equipamento.ganho_limite_mw"


class ArvoreDeReferencia:
    """Um decisor por exploração: guarda em que passo da árvore está."""

    def __init__(self) -> None:
        self._passos: list[str] | None = None
        self._grade_de_potencia: list[tuple[float, int]] = []
        """(potência, revisão) das revisões prontas da grade de potência."""

    async def decidir(self, situacao: Situacao) -> Decisao:
        partida = next(r for r in situacao.revisoes if r.revisao_id == situacao.revisao_partida_id)
        if self._passos is None:
            self._passos = self._planejar(situacao, partida.configuracao)
        self._anotar_grade(situacao)
        while self._passos:
            passo = self._passos.pop(0)
            decisao = self._decidir(passo, situacao)
            if decisao is not None:
                return decisao
        return Decisao(
            acao="encerrar",
            porque="Árvore de referência completa: grade de tamanhos, ponto de apoio e durações "
            "(regra 6).",
        )

    def _planejar(self, situacao: Situacao, configuracao: dict) -> list[str]:  # type: ignore[type-arg]
        faixa = situacao.faixa
        passos: list[str] = []
        if configuracao.get("equipamento") and faixa.get("ganho_limite_mw"):
            passos.append("grade_ganho")
        if configuracao.get("bateria"):
            if faixa.get("potencia_mw") or faixa.get("subestacoes"):
                passos.append("grade_potencia")
            if faixa.get("duracao_horas"):
                passos.append("duracao")
        return passos

    def _decidir(self, passo: str, situacao: Situacao) -> Decisao | None:
        partida = next(r for r in situacao.revisoes if r.revisao_id == situacao.revisao_partida_id)
        configuracao = partida.configuracao
        if passo == "grade_ganho":
            variacoes = _grade(GANHO, configuracao["equipamento"]["ganho_limite_mw"], situacao)
            porque = "Árvore de referência, grade do ganho de limite a partir da partida (regra 6)."
            return _lote(situacao.revisao_partida_id, variacoes, porque)
        if passo == "grade_potencia":
            bateria = configuracao["bateria"]
            variacoes = _grade(POTENCIA, bateria["potencia_mw"], situacao)
            variacoes += [
                VariacaoDecidida(alavanca="bateria.subestacao", valor=nome)
                for nome in situacao.faixa.get("subestacoes") or []
                if nome != bateria["subestacao"]
            ]
            porque = (
                "Árvore de referência, grade de tamanhos da potência na mesma duração e as outras "
                "subestações, a partir da partida (regra 6)."
            )
            return _lote(situacao.revisao_partida_id, variacoes, porque)
        if passo == "duracao":
            apoio = self._ponto_de_apoio(situacao)
            origem = next(r for r in situacao.revisoes if r.revisao_id == apoio)
            bateria = origem.configuracao["bateria"]
            duracao_atual = bateria["capacidade_mwh"] / bateria["potencia_mw"]
            limites = situacao.faixa.get("duracao_horas") or {}
            variacoes = [
                VariacaoDecidida(alavanca="bateria.duracao_horas", valor=horas)
                for horas in DURACOES_HORAS
                if abs(horas - duracao_atual) > 1e-9
                and limites.get("minimo", horas) <= horas <= limites.get("maximo", horas)
            ]
            porque = (
                "Árvore de referência, duração a partir do ponto de apoio, a rev "
                f"{origem.posicao}: o maior tamanho em que a fração ainda subia o bastante "
                "(regra 6)."
            )
            return _lote(apoio, variacoes, porque)
        return None

    def _anotar_grade(self, situacao: Situacao) -> None:
        """As revisões prontas da grade de potência, lidas do último lote: é por elas que o
        ponto de apoio se escolhe."""
        lote = situacao.ultimo_lote
        if not lote:
            return
        por_id = {r.revisao_id: r for r in situacao.revisoes}
        for desfecho in lote["desfechos"]:
            revisao = por_id.get(desfecho.get("revisao_id") or -1)
            if desfecho["alavanca"] == POTENCIA and desfecho["estado"] == "pronta" and revisao:
                potencia = float(revisao.configuracao["bateria"]["potencia_mw"])
                self._grade_de_potencia.append((potencia, revisao.revisao_id))

    def _ponto_de_apoio(self, situacao: Situacao) -> int:
        """O maior tamanho em que a fração sobe pelo menos `DEGRAU_MINIMO` em relação ao degrau
        anterior, com a partida como primeiro degrau. Nenhum subiu tanto: a própria partida."""
        por_id = {r.revisao_id: r for r in situacao.revisoes}
        partida = por_id[situacao.revisao_partida_id]
        degraus = [(float(partida.configuracao["bateria"]["potencia_mw"]), partida.revisao_id)]
        degraus += sorted(self._grade_de_potencia)
        apoio = partida.revisao_id
        for (_, anterior), (_, atual) in itertools.pairwise(degraus):
            subida = (
                por_id[atual].resultado["fracao_recuperada"]
                - por_id[anterior].resultado["fracao_recuperada"]
            )
            if subida >= DEGRAU_MINIMO:
                apoio = atual
        return apoio


def _grade(alavanca: str, base: float, situacao: Situacao) -> list[VariacaoDecidida]:
    campo = "ganho_limite_mw" if alavanca == GANHO else "potencia_mw"
    limites = situacao.faixa.get(campo)
    if not limites or base <= 0:
        return []
    return [
        VariacaoDecidida(alavanca=alavanca, valor=base * multiplo)  # type: ignore[arg-type]
        for multiplo in MULTIPLOS
        if limites["minimo"] <= base * multiplo <= limites["maximo"]
    ]


def _lote(partida: int, variacoes: list[VariacaoDecidida], porque: str) -> Decisao | None:
    if not variacoes:
        return None
    return Decisao(
        acao="disparar",
        revisao_partida_id=partida,
        variacoes=variacoes[:LOTE_MAXIMO],
        porque=porque,
    )
