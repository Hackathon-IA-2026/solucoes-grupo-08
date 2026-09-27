"""Preparo: snapshot → artefatos derivados em arquivo (restrições, equipamentos, séries, propostas).

Feature 02. Regras decididas (docs/invariantes.md, docs/premissas.md e ADR 0005):
- lê um snapshot identificado; toda saída carrega snapshot_id;
- só cortes CNF de origem LOC; energia = val_geracaonaorealizadaapurada x 0,5;
- normaliza dsc_restricao antes de usá-lo como chave: o texto cru tem espaço no fim que
  parte a maior restrição do escopo em duas;
- extrai tensão, par de subestações e circuito do texto e casa contra o cadastro, emitindo
  propostas de vínculo; nunca por heurística escondida. O casamento em que tensão, circuito
  e os dois terminais concordam autoriza o vínculo sozinho; o duvidoso espera (ADR 0008);
- série de uma restrição = soma dos conjuntos, por meia hora, com a fonte na linha;
- DuckDB lê os Parquet (union_by_name, TRY_CAST) e grava artefato em arquivo.
  Este pacote não abre conexão com banco: a carga é da api (ADR 0005).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import duckdb

from arco_dados.texto import (
    AMBIGUO,
    CASADO,
    INDETERMINADO,
    LINHA,
    PROVAVEL,
    SEM_CANDIDATO,
    EquipamentoCitado,
    chave_subestacao,
    contingencia,
    escopo,
    extrair,
    instrucao_de_operacao,
    nome_curto,
    tokens,
)

__all__ = ["AMBIGUO", "CASADO", "INDETERMINADO", "LINHA", "PROVAVEL", "SEM_CANDIDATO"]

_TEXTO_NORMALIZADO = "regexp_replace(trim(dsc_restricao), '\\s+', ' ', 'g')"


@dataclass(frozen=True)
class Linha:
    """Uma linha de transmissão ativa do cadastro, na forma em que o casamento compara."""

    cod_equipamento: str
    tensao_kv: int
    de: str
    para: str
    codigo_circuito: str

    @property
    def par(self) -> frozenset[str]:
        return frozenset({self.de, self.para})

    @property
    def par_por_tokens(self) -> frozenset[frozenset[str]]:
        return frozenset({tokens(self.de), tokens(self.para)})

    def encosta_em(self, citado: EquipamentoCitado) -> bool:
        """Cada terminal citado tem token em comum com um terminal do cadastro, sem repetir."""
        do_cadastro = [tokens(self.de), tokens(self.para)]
        for nome in (citado.de, citado.para):
            do_texto = tokens(nome)
            achou = next((c for c in do_cadastro if do_texto & c), None)
            if achou is None:
                return False
            do_cadastro.remove(achou)
        return True


@dataclass(frozen=True)
class Resumo:
    """O que o preparo produziu, para o comando imprimir e o teste conferir."""

    periodo_inicio: str
    periodo_fim: str
    restricoes: int
    """Restrições distintas, já com os textos do mesmo gargalo juntados."""
    textos: int
    """Textos distintos que o ONS escreveu **e que entraram**. Maior que `restricoes` quando ele
    escreve o mesmo gargalo de mais de um jeito no mesmo snapshot."""
    fora_do_escopo: dict[str, int]
    """Quantos textos ficaram de fora, por motivo: transformação, fluxo, sistêmica. Os
    invariantes mandam não ingerir nenhum deles."""
    indeterminados: list[str]
    """Textos que o classificador não soube ler. Saem listados de propósito: linha de verdade
    que a regra não reconhece sumiria calada, e é o único jeito de descobrir."""
    equipamentos_no_cadastro: int
    propostas: int
    casadas: int
    sem_casamento: int
    intervalos: int


def _ler_texto(texto: str) -> tuple[str | None, str | None, str | None]:
    """Nome curto, contingência e Instrução de Operação, extraídos uma vez por texto."""
    citados = extrair(texto)
    return nome_curto(citados), contingencia(citados), instrucao_de_operacao(texto)


def _canonicos(lidos: dict[str, tuple[str | None, str | None, str | None]]) -> dict[str, str]:
    """Qual texto representa cada texto, quando mais de um descreve a mesma restrição.

    O ONS escreve o mesmo gargalo de várias formas **dentro do mesmo snapshot**: em 2026-09-21,
    `LT 500 kV Jaguaruana II / Pacatuba · C1` aparecia em cinco textos, e o produto mostrava
    como cinco gargalos o que fisicamente é um.

    Junta quando **tudo que se extrai é igual** — mesmo equipamento monitorado, mesma
    contingência, mesma Instrução de Operação — e só a redação difere. Não junta quando algum
    deles difere, mesmo com o mesmo equipamento: dois códigos de Instrução diferentes podem ser
    regimes operativos distintos, e fundir inequações diferentes soma a energia das duas, o que é
    pior que deixá-las separadas. Texto sem nome extraído nunca entra em grupo: representa a si
    mesmo.

    O representante é o menor texto do grupo, para o identificador não depender da ordem de
    leitura. Se uma variante nova e menor aparecer depois, o identificador do grupo muda — e é
    por isso que a identidade nunca se apaga ([ADR 0009]): nada fica órfão quando isso acontece.
    """
    grupos: dict[tuple[str, str | None, str | None], list[str]] = {}
    for texto, (nome, cont, io) in lidos.items():
        if nome is None:
            continue
        grupos.setdefault((nome, cont, io), []).append(texto)
    representante = {t: t for t in lidos}
    for textos in grupos.values():
        menor = min(textos)
        for texto in textos:
            representante[texto] = menor
    return representante


def restricao_id(texto_normalizado: str) -> str:
    """Identificador estável da restrição: depende do texto, não do snapshot."""
    return hashlib.sha1(texto_normalizado.encode("utf-8")).hexdigest()[:12]


def _glob(snapshot: Path, pasta: str) -> str:
    return str(snapshot / f"{pasta}__*.parquet")


def ler_cadastro(con: duckdb.DuckDBPyConnection, snapshot: Path) -> list[Linha]:
    """Linhas ativas do cadastro, com o código de circuito tirado do nome.

    O cadastro guarda o circuito dentro de `nom_linhadetransmissao`, como `C V7`, e é esse
    código que o texto da restrição repete entre parênteses. Nomes de subestação vêm com
    espaço sobrando e sem acento, então os dois lados passam pela mesma normalização.
    """
    consulta = f"""
        SELECT TRIM(cod_equipamento) AS cod_equipamento,
               CAST(val_niveltensao_kv AS INTEGER) AS tensao_kv,
               TRIM(nom_subestacao_de) AS de,
               TRIM(nom_subestacao_para) AS para,
               regexp_extract(TRIM(nom_linhadetransmissao),
                              '\\sC\\s+([A-Z0-9]{{1,4}})\\s', 1) AS circuito
        FROM read_parquet('{_glob(snapshot, "linha_transmissao")}', union_by_name=true)
        WHERE (dat_desativacao IS NULL
               OR TRIM(CAST(dat_desativacao AS VARCHAR)) IN ('', '9999-12-31'))
          AND TRIM(nom_subestacao_para) <> ''
    """
    return [
        Linha(
            cod_equipamento=cod,
            tensao_kv=int(kv),
            de=chave_subestacao(de),
            para=chave_subestacao(para),
            codigo_circuito=circuito,
        )
        for cod, kv, de, para, circuito in con.execute(consulta).fetchall()
        if circuito
    ]


def casar(citado: EquipamentoCitado, cadastro: list[Linha]) -> tuple[str, list[str]]:
    """Casa um equipamento citado contra o cadastro, em dois níveis de confiança.

    A chave forte é tensão mais código de circuito: o `(V7)` do texto é o mesmo `C V7` que o
    cadastro guarda no nome da linha. O par de subestações confirma, e é onde mora a
    dificuldade, porque o cadastro abrevia: "MORRO DO CHAPÉU II" vira "MORRO CHAPEU II" e
    "CEARÁ MIRIM II" vira "CEARA MIRIM 2".

    **Chave que o texto não dá não filtra.** Antes, tensão e circuito eram exigidos sempre, e
    citação sem circuito — `LT 230 KV ITABIRA 4 / ITABIRA 5`, 114,5 GWh — nascia com a lista de
    candidatos vazia e virava `sem_candidato`. Agora cada chave só restringe quando existe, e o
    par de subestações decide o resto. Quando só há um candidato, o circuito não distinguiria
    nada mesmo.

    - `casado`: os dois terminais batem token a token, e o candidato é único.
    - `provavel`: cada terminal tem token em comum com um terminal do cadastro. **Precisa de
      olho humano**, e é por isso que sai marcado em vez de virar vínculo.
    - `ambiguo` e `sem_candidato`: saem com o que se sabe junto, nunca uma escolha
      silenciosa.
    """
    mesmo_circuito = [
        linha
        for linha in cadastro
        if (citado.tensao_kv is None or linha.tensao_kv == citado.tensao_kv)
        and (citado.codigo_circuito is None or linha.codigo_circuito == citado.codigo_circuito)
    ]
    citado_por_tokens = frozenset({tokens(citado.de), tokens(citado.para)})

    exatos = [linha for linha in mesmo_circuito if linha.par_por_tokens == citado_por_tokens]
    if len(exatos) == 1:
        return CASADO, [exatos[0].cod_equipamento]
    if len(exatos) > 1:
        return AMBIGUO, sorted(linha.cod_equipamento for linha in exatos)

    provaveis = [linha for linha in mesmo_circuito if linha.encosta_em(citado)]
    if len(provaveis) == 1:
        return PROVAVEL, [provaveis[0].cod_equipamento]
    if len(provaveis) > 1:
        return AMBIGUO, sorted(linha.cod_equipamento for linha in provaveis)
    return SEM_CANDIDATO, []


def _corte_bruto(snapshot: Path) -> str:
    """Corte local por confiabilidade, eólico e solar, com o texto já normalizado."""
    partes = []
    for fonte, pasta in (
        ("eolica", "restricao_coff_eolica_tm"),
        ("solar", "restricao_coff_fotovoltaica_tm"),
    ):
        partes.append(f"""
            SELECT {_TEXTO_NORMALIZADO} AS texto,
                   '{fonte}' AS fonte,
                   din_instante,
                   TRY_CAST(val_geracaonaorealizadaapurada AS DOUBLE) AS mw,
                   TRY_CAST(num_minutos_cnf AS DOUBLE) AS minutos
            FROM read_parquet('{_glob(snapshot, pasta)}', union_by_name=true)
            WHERE cod_origemrestricao = 'LOC'
              AND cod_razaorestricao = 'CNF'
              AND dsc_restricao IS NOT NULL
              AND TRIM(dsc_restricao) <> ''
        """)
    return " UNION ALL ".join(partes)


def janela(con: duckdb.DuckDBPyConnection, tabela: str = "corte_bruto") -> tuple[str, str]:
    """Os últimos 12 meses **completos** do dado, como manda o invariante do período.

    O mês corrente é parcial e fica de fora: incluí-lo faria a janela ter 12,4 meses, e a
    anualização compararia um ano com um pouco mais que um ano.
    """
    linha = con.execute(
        "SELECT date_trunc('month', MAX(din_instante)) AS fim,"
        f" date_trunc('month', MAX(din_instante)) - INTERVAL 12 MONTH AS inicio FROM {tabela}"
    ).fetchone()
    if linha is None or linha[0] is None:
        raise ValueError("snapshot sem corte de origem local por confiabilidade")
    return str(linha[1]), str(linha[0])


Extrator = Callable[[str], list[EquipamentoCitado]]
"""Lê um texto e devolve os equipamentos citados. É por aqui que o modelo entra, injetado.

`dados` não importa `ia`: o extrator chega de fora, então o preparo roda igual com ou sem
modelo, e o teste não precisa de chave nem de rede."""


def preparar(
    snapshot: Path, destino: Path | None = None, extrator: Extrator | None = None
) -> Resumo:
    """Lê o snapshot, monta os artefatos e grava em Parquet. Sem banco, sem rede."""
    snapshot = snapshot.resolve()
    destino = destino or snapshot.parent.parent / "derivado" / snapshot.name
    destino.mkdir(parents=True, exist_ok=True)
    snapshot_id = snapshot.name

    con = duckdb.connect()
    con.execute(f"CREATE VIEW corte_bruto AS {_corte_bruto(snapshot)}")
    inicio, fim = janela(con)
    con.execute(
        "CREATE VIEW corte AS SELECT * FROM corte_bruto"
        f" WHERE din_instante >= TIMESTAMP '{inicio}' AND din_instante < TIMESTAMP '{fim}'"
    )

    # Restrições: uma linha por texto normalizado. O agrupamento final é por identidade, logo
    # abaixo, porque o mesmo gargalo aparece escrito de mais de um jeito no mesmo snapshot.
    con.execute("""
        CREATE VIEW restricao AS
        SELECT texto, SUM(mw) * 0.5 AS energia_mwh, COUNT(*) AS registros
        FROM corte GROUP BY texto
    """)
    todos_os_textos = [texto for (texto,) in con.execute("SELECT texto FROM restricao").fetchall()]

    # Escopo: só inequação que vigia **linha de transmissão** entra (docs/invariantes.md,
    # Abrangência). Transformação, fluxo e sistêmica ficam de fora e não são ingeridas — até
    # 2026-09-21 eram, e somavam 4,9% do denominador de toda fatia que o produto mostra.
    escopos = {texto: escopo(texto) for texto in todos_os_textos}
    textos = [texto for texto in todos_os_textos if escopos[texto] == LINHA]
    fora: dict[str, int] = {}
    for texto in todos_os_textos:
        if escopos[texto] != LINHA:
            fora[escopos[texto]] = fora.get(escopos[texto], 0) + 1
    indeterminados = [t for t in todos_os_textos if escopos[t] == INDETERMINADO]

    # Nome curto, contingência e Instrução de Operação saem do mesmo texto, por regra. O que a
    # regra não reconhecer sai nulo, e a tela cai no texto do ONS: nunca se inventa nome.
    lidos = {texto: _ler_texto(texto) for texto in textos}
    canonico = _canonicos(lidos)
    ids = {texto: restricao_id(canonico[texto]) for texto in textos}

    con.execute(
        "CREATE TABLE id_restricao (texto VARCHAR, restricao_id VARCHAR,"
        " nome_curto VARCHAR, contingencia VARCHAR, instrucao_operacao VARCHAR)"
    )
    con.executemany(
        "INSERT INTO id_restricao VALUES (?, ?, ?, ?, ?)",
        [[texto, ids[texto], *lidos[canonico[texto]]] for texto in textos],
    )

    con.execute(f"""
        COPY (
            SELECT r.restricao_id,
                   MIN(x.texto) AS texto, 'LOC' AS origem, 'CNF' AS razao,
                   ANY_VALUE(r.nome_curto) AS nome_curto,
                   ANY_VALUE(r.contingencia) AS contingencia,
                   ANY_VALUE(r.instrucao_operacao) AS instrucao_operacao,
                   SUM(x.energia_mwh) AS energia_mwh, SUM(x.registros) AS registros,
                   COUNT(*) AS variantes_de_texto,
                   TIMESTAMP '{inicio}' AS periodo_inicio, TIMESTAMP '{fim}' AS periodo_fim,
                   '{snapshot_id}' AS snapshot_id
            FROM restricao x JOIN id_restricao r USING (texto)
            GROUP BY r.restricao_id
            ORDER BY SUM(x.energia_mwh) DESC
        ) TO '{destino / "restricoes.parquet"}' (FORMAT PARQUET)
    """)

    # Série: soma dos conjuntos por meia hora, com a fonte na linha e os minutos ponderados
    # pela potência (premissa `agregacao_minutos`).
    con.execute(f"""
        COPY (
            SELECT r.restricao_id, c.fonte, c.din_instante AS instante,
                   SUM(c.mw) AS corte_mw,
                   CASE WHEN SUM(c.mw) > 0
                        THEN CAST(ROUND(SUM(c.mw * c.minutos) / SUM(c.mw)) AS INTEGER)
                        ELSE NULL END AS minutos_cnf,
                   '{snapshot_id}' AS snapshot_id
            FROM corte c JOIN id_restricao r USING (texto)
            GROUP BY r.restricao_id, c.fonte, c.din_instante
            ORDER BY r.restricao_id, c.fonte, instante
        ) TO '{destino / "serie.parquet"}' (FORMAT PARQUET)
    """)
    (intervalos,) = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{destino / 'serie.parquet'}')"
    ).fetchone() or (0,)

    # Cadastro: equipamentos e subestações saem do snapshot, sem curadoria.
    con.execute(f"""
        COPY (
            SELECT TRIM(cod_equipamento) AS cod_equipamento,
                   CAST(val_niveltensao_kv AS INTEGER) AS tensao_kv,
                   TRIM(nom_subestacao_de) AS subestacao_de,
                   TRIM(nom_subestacao_para) AS subestacao_para,
                   num_barra_de, num_barra_para,
                   TRIM(nom_linhadetransmissao) AS nome,
                   TRIM(nom_agenteproprietario) AS proprietario,
                   val_comprimento AS comprimento_km,
                   val_capacoperlongasemlimit, val_capacoperlongacomlimit,
                   val_capacopercurtasemlimit, val_capacopercurtacomlimit,
                   val_capacidadeoperveraodialonga, val_capacidadeoperveraonoitelonga,
                   val_capacoperinvernodialonga, val_capacoperinvernonoitelonga,
                   val_capacoperveradiacurta, val_capacoperveraonoitecurta,
                   val_capacoperinvernodiacurta, val_capacoperinvernonoitecurta,
                   '{snapshot_id}' AS snapshot_id
            FROM read_parquet('{_glob(snapshot, "linha_transmissao")}', union_by_name=true)
            WHERE (dat_desativacao IS NULL
                   OR TRIM(CAST(dat_desativacao AS VARCHAR)) IN ('', '9999-12-31'))
              AND TRIM(nom_subestacao_para) <> ''
        ) TO '{destino / "equipamentos.parquet"}' (FORMAT PARQUET)
    """)
    con.execute(f"""
        COPY (
            SELECT DISTINCT TRIM(nom_subestacao) AS nome, val_latitude, val_longitude,
                   num_barra, val_niveltensao, '{snapshot_id}' AS snapshot_id
            FROM read_parquet('{_glob(snapshot, "subestacao")}', union_by_name=true)
        ) TO '{destino / "subestacoes.parquet"}' (FORMAT PARQUET)
    """)

    # Propostas de vínculo. O que a regra casou contra o cadastro entra sozinho; o resto espera
    # (ADR 0008). Onde a regra não leu nada, o `extrator` — quando existe — lê, e a proposta
    # dele passa **pelo mesmo `casar()`**: é a conferência que autoriza, não quem leu.
    cadastro = ler_cadastro(con, snapshot)
    propostas: list[list[object]] = []
    for texto in textos:
        citados = extrair(texto)
        origem = "parser"
        if not citados and extrator is not None:
            citados = extrator(texto)
            origem = "modelo"
        for citado in citados:
            situacao, codigos = casar(citado, cadastro)
            propostas.append(
                [
                    ids[texto],
                    codigos[0] if situacao in (CASADO, PROVAVEL) else None,
                    "|".join(codigos) if situacao == AMBIGUO else None,
                    citado.papel,
                    citado.alternativo,
                    situacao,
                    f"{citado.tensao_kv} kV {citado.de} / {citado.para} C{citado.ordem_circuito}"
                    f"({citado.codigo_circuito})",
                    "proposto",
                    origem,
                    snapshot_id,
                ]
            )

    con.execute("""
        CREATE TABLE proposta (
            restricao_id VARCHAR, cod_equipamento VARCHAR, candidatos VARCHAR,
            papel VARCHAR, alternativo BOOLEAN, situacao VARCHAR, citacao VARCHAR,
            status VARCHAR, origem VARCHAR, snapshot_id VARCHAR
        )
    """)
    if propostas:
        con.executemany("INSERT INTO proposta VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", propostas)
    con.execute(
        "COPY (SELECT * FROM proposta) TO "
        f"'{destino / 'propostas_vinculo.parquet'}' (FORMAT PARQUET)"
    )

    casadas = sum(1 for p in propostas if p[5] in (CASADO, PROVAVEL))
    return Resumo(
        periodo_inicio=inicio,
        periodo_fim=fim,
        restricoes=len(set(ids.values())),
        textos=len(textos),
        fora_do_escopo=fora,
        indeterminados=indeterminados,
        equipamentos_no_cadastro=len(cadastro),
        propostas=len(propostas),
        casadas=casadas,
        sem_casamento=len(propostas) - casadas,
        intervalos=int(intervalos),
    )
