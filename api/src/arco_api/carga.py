"""Carga dos artefatos da feature 02, semeadura e aprovação de vínculo. ADR 0005.

O que é derivado do snapshot é recarregável: a carga apaga as linhas daquele snapshot e
reescreve, então rodar duas vezes dá o mesmo banco. O que é curadoria não: um vínculo
`validado` nunca é sobrescrito pelo parser, e um `rejeitado` não volta a `proposto`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from arco_api.banco import sessao
from arco_api.modelos import (
    PROPOSTO,
    REJEITADO,
    VALIDADO,
    Equipamento,
    Restricao,
    RestricaoSnapshot,
    SerieRestricao,
    Snapshot,
    Subestacao,
    VinculoRestricaoEquipamento,
)

CAPACIDADES = (
    "val_capacoperlongasemlimit",
    "val_capacoperlongacomlimit",
    "val_capacopercurtasemlimit",
    "val_capacopercurtacomlimit",
    "val_capacidadeoperveraodialonga",
    "val_capacidadeoperveraonoitelonga",
    "val_capacoperinvernodialonga",
    "val_capacoperinvernonoitelonga",
    "val_capacoperveradiacurta",
    "val_capacoperveraonoitecurta",
    "val_capacoperinvernodiacurta",
    "val_capacoperinvernonoitecurta",
)

COLUNAS_SEMENTE = (
    "restricao_id",
    "cod_equipamento",
    "papel",
    "status",
    "validado_por",
    "validado_em",
    "observacao",
)


@dataclass(frozen=True)
class RestricaoSumida:
    """Restrição que o snapshot anterior media e este não mede mais.

    Não é erro: pode ter deixado de cortar, ou o ONS pode ter reescrito o texto e ela ter virado
    outra. O que não pode é acontecer em silêncio, que era o caso antes da [ADR 0009].
    """

    restricao_id: str
    texto: str
    tinha_vinculo: bool
    parecidas: list[tuple[str, str, float]]
    """As restrições novas mais parecidas, por sobreposição de palavras: `(id, texto, 0 a 1)`.

    É pista para quem confere, nunca religamento. Religar é a task 13.4, e depende de extração.
    """


@dataclass(frozen=True)
class ResumoCarga:
    snapshot_id: str
    restricoes: int
    equipamentos: int
    subestacoes: int
    intervalos: int
    vinculos_novos: int
    vinculos_atualizados: int
    vinculos_preservados: int
    restricoes_novas: list[str]
    restricoes_sumidas: list[RestricaoSumida]


def _semelhanca(a: str, b: str) -> float:
    """Sobreposição de palavras entre dois textos, de 0 a 1 (Jaccard).

    Grosseira de propósito: serve para ordenar candidatos num relatório que uma pessoa lê, não
    para decidir nada. Um número que decide precisaria de conferência contra o cadastro.
    """
    x, y = set(a.upper().split()), set(b.upper().split())
    return len(x & y) / len(x | y) if x | y else 0.0


def _numero(valor: Any) -> float | None:
    """Parquet devolve Decimal em coluna numérica, e Decimal não vira JSON. Vira float aqui."""
    return None if valor is None else float(valor)


def _ler(artefatos: Path, arquivo: str) -> list[dict[str, Any]]:
    con = duckdb.connect()
    resultado = con.execute(f"SELECT * FROM read_parquet('{artefatos / arquivo}')")
    colunas = [d[0] for d in resultado.description or []]
    return [dict(zip(colunas, linha, strict=True)) for linha in resultado.fetchall()]


def carregar(artefatos: Path, database_url: str | None = None, ativar: bool = True) -> ResumoCarga:
    """Leva os artefatos de um snapshot para o banco, de forma idempotente."""
    restricoes = _ler(artefatos, "restricoes.parquet")
    equipamentos = _ler(artefatos, "equipamentos.parquet")
    subestacoes = _ler(artefatos, "subestacoes.parquet")
    serie = _ler(artefatos, "serie.parquet")
    propostas = _ler(artefatos, "propostas_vinculo.parquet")
    snapshot_id = str(restricoes[0]["snapshot_id"]) if restricoes else artefatos.name
    inicio = restricoes[0].get("periodo_inicio") if restricoes else None
    fim = restricoes[0].get("periodo_fim") if restricoes else None

    with sessao(database_url) as s:
        alvo = s.get(Snapshot, snapshot_id)
        if alvo is None:
            alvo = Snapshot(id=snapshot_id, ativo=ativar)
            s.add(alvo)
        elif ativar:
            alvo.ativo = True
        alvo.periodo_inicio = inicio
        alvo.periodo_fim = fim
        if ativar:
            for outro in s.scalars(select(Snapshot).where(Snapshot.id != snapshot_id)):
                outro.ativo = False
        s.flush()

        # O que o snapshot anterior media, para dizer no fim o que entrou e o que saiu. É lido
        # antes de apagar a medição deste snapshot, senão uma recarga do mesmo snapshot se
        # compararia consigo mesma e não acusaria nada.
        anterior_id = s.scalar(
            select(RestricaoSnapshot.snapshot_id)
            .where(RestricaoSnapshot.snapshot_id != snapshot_id)
            .join(Snapshot, Snapshot.id == RestricaoSnapshot.snapshot_id)
            .order_by(Snapshot.carregado_em.desc())
            .limit(1)
        )
        media_antes: dict[str, str] = {}
        if anterior_id is not None:
            media_antes = {
                m.restricao_id: m.texto
                for m in s.scalars(
                    select(RestricaoSnapshot).where(RestricaoSnapshot.snapshot_id == anterior_id)
                )
            }

        # A identidade da restrição não entra aqui: ela nunca é apagada, senão vínculo, aviso,
        # obra e simulação salva ficariam apontando para o nada ([ADR 0009]).
        for modelo in (RestricaoSnapshot, Equipamento, Subestacao, SerieRestricao):
            s.execute(delete(modelo).where(modelo.snapshot_id == snapshot_id))

        ja_conhecidas = set(s.scalars(select(Restricao.id)))
        conhecidas = set(ja_conhecidas)
        identidades = {r.id: r for r in s.scalars(select(Restricao))}
        for linha in restricoes:
            existente = identidades.get(linha["restricao_id"])
            if existente is None:
                conhecidas.add(linha["restricao_id"])
                s.add(
                    Restricao(
                        id=linha["restricao_id"],
                        texto=linha["texto"],
                        origem=linha["origem"],
                        razao=linha["razao"],
                        nome_curto=linha.get("nome_curto"),
                        contingencia=linha.get("contingencia"),
                        instrucao_operacao=linha.get("instrucao_operacao"),
                        vista_primeiro_em=snapshot_id,
                    )
                )
                continue
            # Identidade não se reescreve, mas preencher o que está nulo é melhora sem perda:
            # uma regra de extração melhor nomeia o que a anterior não nomeava.
            for campo in ("nome_curto", "contingencia", "instrucao_operacao"):
                if getattr(existente, campo) is None and linha.get(campo) is not None:
                    setattr(existente, campo, linha[campo])
        s.flush()

        s.add_all(
            RestricaoSnapshot(
                restricao_id=linha["restricao_id"],
                snapshot_id=snapshot_id,
                texto=linha["texto"],
                energia_mwh=float(linha["energia_mwh"] or 0.0),
            )
            for linha in restricoes
        )
        s.add_all(
            Equipamento(
                cod_equipamento=linha["cod_equipamento"],
                snapshot_id=snapshot_id,
                tensao_kv=linha["tensao_kv"],
                subestacao_de=linha["subestacao_de"],
                subestacao_para=linha["subestacao_para"],
                num_barra_de=linha["num_barra_de"],
                num_barra_para=linha["num_barra_para"],
                nome=linha["nome"],
                proprietario=linha["proprietario"],
                comprimento_km=_numero(linha["comprimento_km"]),
                capacidades={c: _numero(linha.get(c)) for c in CAPACIDADES},
            )
            for linha in equipamentos
        )
        vistas: set[str] = set()
        for linha in subestacoes:
            nome = linha["nome"]
            if nome in vistas:
                continue
            vistas.add(nome)
            s.add(
                Subestacao(
                    nome=nome,
                    snapshot_id=snapshot_id,
                    latitude=_numero(linha["val_latitude"]),
                    longitude=_numero(linha["val_longitude"]),
                )
            )
        s.add_all(
            SerieRestricao(
                restricao_id=linha["restricao_id"],
                snapshot_id=snapshot_id,
                fonte=linha["fonte"],
                instante=linha["instante"],
                corte_mw=float(linha["corte_mw"] or 0.0),
                minutos_cnf=linha["minutos_cnf"],
            )
            for linha in serie
        )

        novos = atualizados = preservados = 0
        for linha in propostas:
            chave = (linha["restricao_id"], linha["cod_equipamento"], linha["papel"])
            existente = s.scalar(
                select(VinculoRestricaoEquipamento).where(
                    VinculoRestricaoEquipamento.restricao_id == chave[0],
                    VinculoRestricaoEquipamento.cod_equipamento == chave[1],
                    VinculoRestricaoEquipamento.papel == chave[2],
                )
            )
            if existente is None:
                s.add(
                    VinculoRestricaoEquipamento(
                        restricao_id=chave[0],
                        cod_equipamento=chave[1],
                        papel=chave[2],
                        alternativo=bool(linha["alternativo"]),
                        situacao=linha["situacao"],
                        citacao=linha["citacao"],
                        candidatos=linha["candidatos"],
                        status=PROPOSTO,
                        origem="parser",
                    )
                )
                novos += 1
            elif existente.status in (VALIDADO, REJEITADO):
                # A assinatura do engenheiro vale mais que o parser. Não se toca.
                preservados += 1
            else:
                existente.situacao = linha["situacao"]
                existente.citacao = linha["citacao"]
                existente.candidatos = linha["candidatos"]
                existente.alternativo = bool(linha["alternativo"])
                atualizados += 1
        agora = {str(linha["restricao_id"]): str(linha["texto"]) for linha in restricoes}
        # Nova é identidade que não existia antes desta carga. Medir por ausência no
        # snapshot anterior diria que tudo é novo ao recarregar o mesmo snapshot.
        novas = sorted(agora.keys() - ja_conhecidas)
        com_vinculo = {
            v for (v,) in s.execute(select(VinculoRestricaoEquipamento.restricao_id).distinct())
        }
        sumidas = [
            RestricaoSumida(
                restricao_id=rid,
                texto=texto,
                tinha_vinculo=rid in com_vinculo,
                parecidas=sorted(
                    (
                        (nova, agora[nova], _semelhanca(texto, agora[nova]))
                        for nova in novas
                        if _semelhanca(texto, agora[nova]) > 0.0
                    ),
                    key=lambda p: -p[2],
                )[:3],
            )
            for rid, texto in sorted(media_antes.items())
            if rid not in agora
        ]

        s.commit()

    return ResumoCarga(
        snapshot_id=snapshot_id,
        restricoes=len(restricoes),
        equipamentos=len(equipamentos),
        subestacoes=len(vistas),
        intervalos=len(serie),
        vinculos_novos=novos,
        vinculos_atualizados=atualizados,
        vinculos_preservados=preservados,
        restricoes_novas=novas,
        restricoes_sumidas=sumidas,
    )


def semear(csv_path: Path, database_url: str | None = None) -> int:
    """Aplica os vínculos validados do CSV versionado. É o que torna o banco descartável."""
    if not csv_path.exists():
        return 0
    aplicados = 0
    with sessao(database_url) as s, csv_path.open(encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha.get("status") != VALIDADO:
                continue
            alvo = s.scalar(
                select(VinculoRestricaoEquipamento).where(
                    VinculoRestricaoEquipamento.restricao_id == linha["restricao_id"],
                    VinculoRestricaoEquipamento.cod_equipamento == linha["cod_equipamento"],
                    VinculoRestricaoEquipamento.papel == linha["papel"],
                )
            )
            if alvo is None:
                alvo = VinculoRestricaoEquipamento(
                    restricao_id=linha["restricao_id"],
                    cod_equipamento=linha["cod_equipamento"],
                    papel=linha["papel"],
                    origem="humano",
                )
                s.add(alvo)
            alvo.status = VALIDADO
            alvo.validado_por = linha.get("validado_por") or None
            alvo.validado_em = (
                date.fromisoformat(linha["validado_em"]) if linha.get("validado_em") else None
            )
            alvo.observacao = linha.get("observacao") or None
            aplicados += 1
        s.commit()
    return aplicados


def exportar(csv_path: Path, database_url: str | None = None) -> int:
    """Grava os validados no CSV versionado, que entra por PR e vira semente."""
    with sessao(database_url) as s:
        validados = list(
            s.scalars(
                select(VinculoRestricaoEquipamento)
                .where(VinculoRestricaoEquipamento.status == VALIDADO)
                .order_by(
                    VinculoRestricaoEquipamento.restricao_id,
                    VinculoRestricaoEquipamento.cod_equipamento,
                )
            )
        )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(COLUNAS_SEMENTE))
        escritor.writeheader()
        for v in validados:
            escritor.writerow(
                {
                    "restricao_id": v.restricao_id,
                    "cod_equipamento": v.cod_equipamento or "",
                    "papel": v.papel,
                    "status": v.status,
                    "validado_por": v.validado_por or "",
                    "validado_em": v.validado_em.isoformat() if v.validado_em else "",
                    "observacao": v.observacao or "",
                }
            )
    return len(validados)


def decidir(
    vinculo_id: int,
    status: str,
    validado_por: str,
    observacao: str | None = None,
    quando: date | None = None,
    database_url: str | None = None,
    cod_equipamento: str | None = None,
) -> VinculoRestricaoEquipamento:
    """Aprova ou rejeita um vínculo. Exige nome: assinatura sem autor não é assinatura.

    Aprovar uma proposta ambígua exige escolher entre os candidatos. Sem isso o vínculo ficaria
    `validado` com `cod_equipamento` nulo — e a rota descarta código nulo, então a assinatura
    existiria no banco e a restrição continuaria fora do produto, sem ninguém ser avisado.
    Rejeitar não precisa de escolha: rejeita-se a proposta inteira.
    """
    if status not in (VALIDADO, REJEITADO):
        raise ValueError(f"status inválido: {status}")
    if not validado_por.strip():
        raise ValueError("aprovar exige o nome de quem validou")
    with sessao(database_url) as s:
        alvo = s.get(VinculoRestricaoEquipamento, vinculo_id)
        if alvo is None:
            raise LookupError(f"vínculo {vinculo_id} não existe")

        if status == VALIDADO:
            escolhido = cod_equipamento or alvo.cod_equipamento
            if escolhido is None:
                candidatos = alvo.candidatos or ""
                opcoes = " ou ".join(candidatos.split("|")) if candidatos else "nenhum"
                raise ValueError(
                    f"vínculo {vinculo_id} está {alvo.situacao} e não tem equipamento: aprovar "
                    f"exige escolher um dos candidatos ({opcoes})"
                )
            _confere_escolha(s, alvo, escolhido, cod_equipamento is not None)
            alvo.cod_equipamento = escolhido

        alvo.status = status
        alvo.validado_por = validado_por.strip()
        alvo.validado_em = quando or date.today()
        alvo.observacao = observacao
        s.commit()
        return alvo


def _confere_escolha(
    s: Session, alvo: VinculoRestricaoEquipamento, escolhido: str, foi_escolhido: bool
) -> None:
    """O código escolhido tem de estar entre os candidatos e não pode duplicar outro vínculo."""
    candidatos = (alvo.candidatos or "").split("|") if alvo.candidatos else []
    if foi_escolhido and candidatos and escolhido not in candidatos:
        raise ValueError(
            f"{escolhido} não está entre os candidatos do vínculo {alvo.id}: "
            f"{' ou '.join(candidatos)}"
        )
    irmao = s.scalar(
        select(VinculoRestricaoEquipamento).where(
            VinculoRestricaoEquipamento.restricao_id == alvo.restricao_id,
            VinculoRestricaoEquipamento.cod_equipamento == escolhido,
            VinculoRestricaoEquipamento.papel == alvo.papel,
            VinculoRestricaoEquipamento.id != alvo.id,
        )
    )
    if irmao is not None:
        raise ValueError(
            f"{escolhido} já é vínculo {irmao.id} nesta restrição com o papel {alvo.papel}"
        )
