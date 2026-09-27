"""Uma rodada do explorador: o lote de variações, conferido, anunciado e rodado em paralelo.

As regras não dependem do agente obedecer
([regras do explorador](../../../docs/features/agentes/17-regras-do-explorador.md)). Antes de
chamar a rota, o lote confere o que dá para conferir aqui — tamanho, faixa permitida da tarefa,
repetição dentro do próprio lote, teto — e recusa com o motivo, sem gastar cálculo. O resto a
rota de variação confere: revisão repetida na simulação (409), teto no instante de salvar (409),
linha contingenciada e teto da capacidade (422). Nada aqui monta configuração nem faz conta: a
rota monta pelo motor.

A ordem dos eventos é a do contrato da tela
(`docs/features/agentes/17-ver-processamento-contrato.md`):
`rodada_decidida`, com o `variacao_id` de cada variação que vai rodar, antes de qualquer uma
começar; depois as recusas feitas aqui, sem `variacao_id`; depois as variações, que a rota
grava. O `decidindo_rodada` é de quem chama o modelo, antes dele (task 17.14).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from arco_agentes import resumos
from arco_agentes.api import ClienteDaApi, ErroDaApi

LOTE_MAXIMO = 10
"""Variações por rodada, regra 5 do explorador."""

CAMPO_DA_FAIXA = {
    "bateria.potencia_mw": "potencia_mw",
    "bateria.duracao_horas": "duracao_horas",
    "bateria.subestacao": "subestacoes",
    "equipamento.ganho_limite_mw": "ganho_limite_mw",
}


class VariacaoPedida(BaseModel):
    """Uma alavanca e o valor. Campo a mais — uma segunda alavanca, um preço — é recusa, e não
    campo ignorado: ignorar deixaria o agente achar que pediu o que não pediu."""

    model_config = ConfigDict(extra="forbid")

    alavanca: str = Field(
        description="Uma de `bateria.potencia_mw` (MW), `bateria.duracao_horas` (horas de "
        "potência), `bateria.subestacao` (nome do cadastro) ou `equipamento.ganho_limite_mw` "
        "(MW). Uma alavanca por variação."
    )
    valor: float | str


class Desfecho(BaseModel):
    variacao_id: str | None
    alavanca: str
    valor: float | str
    estado: str = Field(description="`pronta` ou `recusada`.")
    motivo: str | None = None
    revisao: dict[str, Any] | None = Field(
        default=None, description="A revisão salva, resumida, com os diagnósticos."
    )


def _fora_da_faixa(variacao: VariacaoPedida, faixa: dict[str, Any]) -> str | None:
    """O motivo da recusa pela faixa confirmada, ou `None`. A mesma faixa que a rota aplica:
    conferir aqui só poupa a chamada."""
    campo = CAMPO_DA_FAIXA.get(variacao.alavanca)
    if campo is None:
        return (
            f"alavanca {variacao.alavanca} não existe; as alavancas são {', '.join(CAMPO_DA_FAIXA)}"
        )
    limite = faixa.get(campo)
    if limite is None:
        return f"esta exploração não varia {variacao.alavanca}"
    if campo == "subestacoes":
        if str(variacao.valor) not in limite:
            permitidas = ", ".join(limite)
            return f"{variacao.valor} não é subestação permitida; as permitidas são {permitidas}"
        return None
    try:
        valor = float(variacao.valor)
    except TypeError, ValueError:
        return f"{variacao.alavanca} pede número, veio {variacao.valor!r}"
    if not limite["minimo"] <= valor <= limite["maximo"]:
        return (
            f"{variacao.alavanca} = {resumos.numero_br(valor)} fora da faixa permitida, de "
            f"{resumos.numero_br(limite['minimo'])} a {resumos.numero_br(limite['maximo'])}"
        )
    return None


async def disparar(
    api: ClienteDaApi,
    tarefa_id: int,
    revisao_partida_id: int,
    variacoes: list[VariacaoPedida],
    porque: str,
) -> dict[str, Any]:
    """Confere, anuncia, roda em paralelo e devolve cada desfecho e a tarefa depois do lote."""
    tarefa = await api.ver_tarefa(tarefa_id)
    if tarefa["estado"] != "em_andamento":
        raise ErroDaApi(409, f"a exploração {tarefa_id} já terminou: {tarefa['estado']}")
    simulacao_id = tarefa["simulacao_id"]
    rodada = tarefa["contagem"]["rodadas"] + 1
    restante = tarefa["teto"] - tarefa["contagem"]["prontas"]

    aceitas: list[tuple[str, VariacaoPedida]] = []
    recusadas: list[Desfecho] = []
    vistas: set[tuple[str, str]] = set()
    for i, variacao in enumerate(variacoes, start=1):
        chave = (variacao.alavanca, str(variacao.valor))
        motivo = (
            f"o lote passa de {LOTE_MAXIMO} variações"
            if i > LOTE_MAXIMO
            else _fora_da_faixa(variacao, tarefa["faixa"])
            or ("repetida dentro do lote" if chave in vistas else None)
            or (
                f"teto de {tarefa['teto']} revisões: cabem {max(restante, 0)} neste lote"
                if len(aceitas) >= restante
                else None
            )
        )
        vistas.add(chave)
        if motivo:
            recusadas.append(
                Desfecho(
                    variacao_id=None,
                    alavanca=variacao.alavanca,
                    valor=variacao.valor,
                    estado="recusada",
                    motivo=motivo,
                )
            )
        else:
            aceitas.append((f"r{rodada}-v{i}", variacao))

    await api.registrar_evento(
        tarefa_id,
        {
            "tipo": "rodada_decidida",
            "rodada": rodada,
            "revisao_partida_id": revisao_partida_id,
            "porque": porque,
            "variacoes": [
                {"alavanca": v.alavanca, "valor": v.valor, "variacao_id": vid} for vid, v in aceitas
            ],
        },
    )
    for desfecho in recusadas:
        await api.registrar_evento(
            tarefa_id,
            {
                "tipo": "variacao_recusada",
                "alavanca": desfecho.alavanca if desfecho.alavanca in CAMPO_DA_FAIXA else None,
                "valor": desfecho.valor,
                "motivo": desfecho.motivo,
            },
        )

    async def rodar(variacao_id: str, variacao: VariacaoPedida) -> Desfecho:
        try:
            salva = await api.salvar_variacao(
                simulacao_id,
                {
                    "tarefa_id": tarefa_id,
                    "revisao_base_id": revisao_partida_id,
                    "alavanca": variacao.alavanca,
                    "valor": variacao.valor,
                    "nota": porque,
                    "variacao_id": variacao_id,
                    "rodada": rodada,
                },
            )
            _, revisao = resumos.revisao(await api.ver_revisao(salva["id"]))
        except ErroDaApi as erro:
            return Desfecho(
                variacao_id=variacao_id,
                alavanca=variacao.alavanca,
                valor=variacao.valor,
                estado="recusada",
                motivo=f"{erro.status}: {erro.mensagem}",
            )
        return Desfecho(
            variacao_id=variacao_id,
            alavanca=variacao.alavanca,
            valor=variacao.valor,
            estado="pronta",
            revisao=revisao,
        )

    feitas = await asyncio.gather(*(rodar(vid, v) for vid, v in aceitas))
    # Os cruzamentos lidos dentro de cada variação não viam as irmãs que terminaram depois:
    # lidos de novo, com o lote inteiro salvo.
    prontas = [d.revisao for d in feitas if d.revisao]
    cruzamentos = (
        (await api.ver_revisao(prontas[-1]["revisao_id"])).get("cruzamentos") if prontas else None
    )
    depois = await api.ver_tarefa(tarefa_id)
    return {
        "rodada": rodada,
        "desfechos": [d.model_dump() for d in [*feitas, *recusadas]],
        "cruzamentos": cruzamentos,
        "tarefa": depois,
    }


def texto(lote: dict[str, Any]) -> str:
    linhas = [f"Rodada {lote['rodada']}:"]
    for d in lote["desfechos"]:
        cabeca = f"- {d['alavanca']} = {d['valor']}"
        if d["estado"] == "pronta":
            r = d["revisao"]
            linhas.append(
                f"{cabeca}: revisão {r['revisao_id']} (rev {r['posicao']}). "
                + resumos.texto_do_resultado(r["resultado"])
                + (
                    " " + resumos.texto_dos_diagnosticos(r["diagnosticos"])
                    if r["diagnosticos"]
                    else ""
                )
            )
        else:
            linhas.append(f"{cabeca}: recusada — {d['motivo']}")
    contagem = lote["tarefa"]["contagem"]
    linhas.append(
        f"A exploração tem {contagem['prontas']} de {lote['tarefa']['teto']} revisões prontas."
    )
    if lote["cruzamentos"]:
        linhas.append(resumos.texto_dos_cruzamentos(lote["cruzamentos"]))
    return "\n".join(linhas)
