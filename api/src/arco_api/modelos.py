"""Esquema da base derivada e das simulações. Feature 03, conforme a ADR 0005.

Duas naturezas convivem aqui, e a diferença é o que faz o banco ser descartável:

- **Derivado do snapshot** — restrição, equipamento, subestação e série. Carrega `snapshot_id`
  em toda linha e é recomputável com `preparar` mais `carregar`. Pode ser jogado fora.
- **Curadoria da equipe** — o vínculo entre restrição e equipamento, com quem validou e
  quando, e os avisos. **Não tem `snapshot_id`**: atravessa snapshots, porque a assinatura de
  um engenheiro não envelhece quando o ONS republica um Parquet. É semeado do CSV versionado
  em `dados/vinculos/` e exportado de volta para lá.

O que o usuário cria — simulação e revisão — é a terceira natureza, e nunca se apaga.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from arco_dados.texto import AMBIGUO, CASADO, PROVAVEL, SEM_CANDIDATO, SITUACAO_VINCULO

Json = JSON().with_variant(JSONB(), "postgresql")
"""JSONB no Postgres, que é onde o produto roda; JSON genérico no resto.

A variante existe para a suíte rodar sem container: os testes sobem o esquema em SQLite na
memória. O que vai para produção é sempre JSONB.
"""

PROPOSTO = "proposto"
VALIDADO = "validado"
REJEITADO = "rejeitado"
STATUS_VINCULO = (PROPOSTO, VALIDADO, REJEITADO)
"""O que uma **pessoa** disse sobre o vínculo. Não diz como ele foi produzido."""

ORIGEM_PARSER = "parser"
ORIGEM_HUMANO = "humano"
ORIGEM_MODELO = "modelo"
ORIGEM_VINCULO = (ORIGEM_PARSER, ORIGEM_HUMANO, ORIGEM_MODELO)
"""Quem produziu a proposta. Junto com `status`, é o que dá a procedência."""

AUTOMATICA = "automatica"
POR_MODELO = "por_modelo"
POR_PESSOA = "por_pessoa"
PROCEDENCIA_VINCULO = (AUTOMATICA, POR_MODELO, POR_PESSOA)
"""O que sustenta o vínculo, para a tela dizer ao usuário de onde veio aquele equipamento.

Não é `status` e não é `origem`: é a leitura das duas juntas, na pergunta que interessa a quem
olha o número — quanto este vínculo está apoiado. Derivada, nunca gravada, para não divergir da
regra que a [ADR 0008] escreveu."""

__all__ = ["AMBIGUO", "CASADO", "PROVAVEL", "SEM_CANDIDATO", "SITUACAO_VINCULO"]
"""`situacao` vem de `dados` e diz quanta evidência o casamento reuniu. Desde a ADR 0008 é ela
que decide a entrada no produto, então é vocabulário de primeira classe aqui também."""


class Base(DeclarativeBase):
    pass


class Snapshot(Base):
    """Uma cópia datada do dado do ONS. Nunca se apaga enquanto houver revisão apontando."""

    __tablename__ = "snapshot"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    carregado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    periodo_inicio: Mapped[datetime | None] = mapped_column(DateTime)
    periodo_fim: Mapped[datetime | None] = mapped_column(DateTime)
    """A janela analisada, de 12 meses completos.

    Fica aqui, e não sai da contagem de linhas da série, porque a série é esparsa: só a meia
    hora com corte existe. Um ano com três mil meias horas de corte pareceria dois meses."""


class Subestacao(Base):
    __tablename__ = "subestacao"

    nome: Mapped[str] = mapped_column(String(120), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshot.id", ondelete="RESTRICT"), primary_key=True
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)


class Equipamento(Base):
    """Uma linha de transmissão do cadastro. `tipo` é fixo: o ARCO só simula linha."""

    __tablename__ = "equipamento"

    cod_equipamento: Mapped[str] = mapped_column(String(40), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshot.id", ondelete="RESTRICT"), primary_key=True
    )
    tipo: Mapped[str] = mapped_column(String(20), default="linha")
    tensao_kv: Mapped[int | None] = mapped_column(Integer)
    subestacao_de: Mapped[str | None] = mapped_column(String(120))
    subestacao_para: Mapped[str | None] = mapped_column(String(120))
    num_barra_de: Mapped[int | None] = mapped_column(Integer)
    num_barra_para: Mapped[int | None] = mapped_column(Integer)
    nome: Mapped[str | None] = mapped_column(Text)
    proprietario: Mapped[str | None] = mapped_column(Text)
    comprimento_km: Mapped[float | None] = mapped_column(Float)
    capacidades: Mapped[dict[str, Any] | None] = mapped_column(Json)
    """As doze colunas de capacidade do cadastro, guardadas inteiras.

    A tela exibe só a genérica, mas gravar uma coluna só obrigaria a reingerir quando a
    decisão sobre sazonalidade voltar. Guardar as doze custa nada.
    """


class Restricao(Base):
    """A inequação nomeada pelo ONS, como **identidade**. Atravessa snapshots e nunca se apaga.

    Sem `snapshot_id` de propósito ([ADR 0009]). É aqui que vínculo, aviso, obra e simulação se
    penduram, e é por isso que a restrição some de um snapshot sem levar ninguém junto.

    O `id` continua sendo `sha1(texto normalizado)[:12]`, calculado sobre o **primeiro** texto
    visto. Se o ONS reescrever o texto depois, o `id` da identidade não muda — muda o texto da
    medição, que mora em `RestricaoSnapshot`.
    """

    __tablename__ = "restricao"

    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    texto: Mapped[str] = mapped_column(Text)
    """O primeiro texto visto, que é de onde o `id` saiu. Serve de rótulo quando a restrição não
    está no snapshot ativo; o texto do dia mora na medição."""
    origem: Mapped[str] = mapped_column(String(3), default="LOC")
    razao: Mapped[str] = mapped_column(String(3), default="CNF")
    nome_curto: Mapped[str | None] = mapped_column(String(200))
    """`LT 230 kV Açu III / Mossoró II · C1`, composto por regra do texto (feature 10). Nulo
    quando o texto não cita equipamento reconhecível, e aí a tela cai no texto do ONS."""
    contingencia: Mapped[str | None] = mapped_column(String(200))
    """O equipamento que se supõe perder, no mesmo formato. É ele que distingue duas restrições
    sobre a mesma linha monitorada."""
    instrucao_operacao: Mapped[str | None] = mapped_column(String(40))
    """`IO-ON.NE.5NE`. É o identificador que o próprio operador usa para achar a regra."""
    vista_primeiro_em: Mapped[str] = mapped_column(String(64))
    """Snapshot em que a restrição apareceu pela primeira vez. Não é FK: o snapshot pode sair e a
    identidade fica."""


class RestricaoSnapshot(Base):
    """A restrição **naquele snapshot**: o texto daquele dia e a energia daquele dia.

    É a parte recomputável, e a única que a carga apaga e refaz. Some com o snapshot; a
    identidade não.
    """

    __tablename__ = "restricao_snapshot"

    restricao_id: Mapped[str] = mapped_column(
        ForeignKey("restricao.id", ondelete="RESTRICT"), primary_key=True
    )
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshot.id", ondelete="RESTRICT"), primary_key=True
    )
    texto: Mapped[str] = mapped_column(Text)
    energia_mwh: Mapped[float] = mapped_column(Float, default=0.0)


class VinculoRestricaoEquipamento(Base):
    """Curadoria: o que liga o texto ao cadastro, e quem assinou embaixo.

    Sem `snapshot_id` de propósito. O parser propõe, a pessoa aprova, e só `validado`
    alimenta série, ranking e simulação.
    """

    __tablename__ = "vinculo_restricao_equipamento"
    __table_args__ = (
        UniqueConstraint("restricao_id", "cod_equipamento", "papel", name="uq_vinculo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    restricao_id: Mapped[str] = mapped_column(String(12), index=True)
    cod_equipamento: Mapped[str | None] = mapped_column(String(40), index=True)
    papel: Mapped[str] = mapped_column(String(20), default="monitorado")
    alternativo: Mapped[bool] = mapped_column(Boolean, default=False)
    situacao: Mapped[str] = mapped_column(String(20), default="casado")
    citacao: Mapped[str | None] = mapped_column(Text)
    candidatos: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default=PROPOSTO, index=True)
    origem: Mapped[str] = mapped_column(String(12), default="parser")
    validado_por: Mapped[str | None] = mapped_column(String(120))
    validado_em: Mapped[date | None] = mapped_column(Date)
    observacao: Mapped[str | None] = mapped_column(Text)


def procedencia(vinculo: VinculoRestricaoEquipamento) -> str:
    """De onde vem a confiança neste vínculo.

    Quem uma pessoa validou sai como `por_pessoa`, mesmo tendo nascido de parser ou de modelo:
    a assinatura é o apoio mais forte que existe, e é ela que o usuário quer ver. Sem
    assinatura, vale quem produziu — modelo conferido contra o cadastro, ou o casamento
    determinístico, que é o caso da maioria.
    """
    if vinculo.status == VALIDADO:
        return POR_PESSOA
    if vinculo.origem == ORIGEM_MODELO:
        return POR_MODELO
    return AUTOMATICA


class SerieRestricao(Base):
    """Corte em MW médios da meia hora, por restrição, fonte e instante."""

    __tablename__ = "serie_restricao"

    restricao_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("snapshot.id", ondelete="RESTRICT"), primary_key=True
    )
    fonte: Mapped[str] = mapped_column(String(10), primary_key=True)
    instante: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    corte_mw: Mapped[float] = mapped_column(Float)
    minutos_cnf: Mapped[int | None] = mapped_column(Integer)


class AvisoRestricao(Base):
    """Aviso curado, que aparece ao lado do resultado. Feature 09 preenche."""

    __tablename__ = "aviso_restricao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    restricao_id: Mapped[str] = mapped_column(String(12), index=True)
    codigo: Mapped[str] = mapped_column(String(60))
    mensagem: Mapped[str] = mapped_column(Text)
    fonte: Mapped[str | None] = mapped_column(Text)


class ObraPrevista(Base):
    """Obra que muda a rede dentro ou depois da janela do histórico. Feature 09 preenche."""

    __tablename__ = "obra_prevista"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    restricao_id: Mapped[str] = mapped_column(String(12), index=True)
    descricao: Mapped[str] = mapped_column(Text)
    situacao: Mapped[str | None] = mapped_column(String(60))
    previsao: Mapped[str | None] = mapped_column(String(60))
    fonte: Mapped[str | None] = mapped_column(Text)


class Simulacao(Base):
    """Objeto nomeado que o usuário cria. Nada se apaga; alterar cria revisão."""

    __tablename__ = "simulacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(200))
    pergunta: Mapped[str | None] = mapped_column(Text)
    restricao_id: Mapped[str] = mapped_column(String(12), index=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


POR_AGENTE = "por_agente"
PROCEDENCIA_REVISAO = (POR_PESSOA, POR_AGENTE)
"""Como a revisão nasceu ([ADR 0011]). Não é autor e não vale como aprovação: a [ADR 0006]
continua valendo. `por_pessoa` é o padrão, inclusive para o que existia antes da coluna."""


class SimulacaoRevisao(Base):
    """Cada cálculo salvo. Guarda o que usou, para o resultado ser reproduzível.

    É histórico e tentativa ([ADR 0011]): uma simulação com dez revisões pode ser uma exploração,
    e não só dez recálculos. Por isso pode ter ramos ([ADR 0014]): a árvore se lê por
    `revisao_anterior_id`, e a posição continua sendo a ordem de gravação.
    """

    __tablename__ = "simulacao_revisao"
    __table_args__ = (
        ForeignKeyConstraint(["simulacao_id"], ["simulacao.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["revisao_anterior_id"], ["simulacao_revisao.id"], ondelete="RESTRICT"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulacao_id: Mapped[int] = mapped_column(Integer, index=True)
    revisao_anterior_id: Mapped[int | None] = mapped_column(Integer)
    """A revisão de onde esta nasceu, que não é necessariamente a gravada antes ([ADR 0014])."""
    procedencia: Mapped[str] = mapped_column(
        String(12), default=POR_PESSOA, server_default=POR_PESSOA
    )
    nota: Mapped[str | None] = mapped_column(Text)
    """O porquê desta configuração. Texto, nunca número de cálculo."""
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("snapshot.id", ondelete="RESTRICT"))
    metodo_versao: Mapped[str] = mapped_column(String(20))
    configuracao: Mapped[dict[str, Any]] = mapped_column(Json)
    premissas_usadas: Mapped[dict[str, Any]] = mapped_column(Json)
    resultado: Mapped[dict[str, Any]] = mapped_column(Json)
    avisos: Mapped[list[Any]] = mapped_column(Json, default=list)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


GERANDO = "gerando"
PRONTO = "pronto"
BARRADO = "barrado"
FALHOU = "falhou"
ESTADOS_RELATORIO = (GERANDO, PRONTO, BARRADO, FALHOU)
"""`barrado` é o verificador recusando a prosa; `falhou` é a geração que não chegou ao fim —
sem chave, rede fora, processo reiniciado no meio. Os dois dizem por quê, e nenhum grava prosa
como aprovada."""


class Relatorio(Base):
    """O relatório de uma simulação sobre as revisões que existiam quando foi pedido.

    Objeto salvo, como a revisão: pedir de novo cria outro, nada se sobrescreve (ADR 0012). Só a
    tarefa de fundo que o gerou muda a linha, uma vez, de `gerando` para o estado final.
    """

    __tablename__ = "relatorio"
    __table_args__ = (
        # Um `gerando` por simulação, garantido pelo banco e não só pela rota: dois pedidos
        # simultâneos passariam os dois pela conferência antes de qualquer um gravar.
        Index(
            "uq_relatorio_gerando",
            "simulacao_id",
            unique=True,
            postgresql_where=text("estado = 'gerando'"),
            sqlite_where=text("estado = 'gerando'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulacao_id: Mapped[int] = mapped_column(
        ForeignKey("simulacao.id", ondelete="RESTRICT"), index=True
    )
    estado: Mapped[str] = mapped_column(String(10), default=GERANDO)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    gerado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_id: Mapped[str] = mapped_column(String(64))
    metodo_versao: Mapped[str] = mapped_column(String(20))
    """Da revisão mais nova coberta, como o contrato pede: é o dado e o método que a leitura
    descreve."""
    modelo: Mapped[str | None] = mapped_column(String(60))
    versao_prompt: Mapped[str | None] = mapped_column(String(20))
    revisoes_cobertas: Mapped[list[int]] = mapped_column(Json)
    """Os `id` das revisões, na ordem. A posição sai deles na leitura."""
    parte_calculada: Mapped[dict[str, Any] | None] = mapped_column(Json)
    prosa: Mapped[dict[str, Any] | None] = mapped_column(Json)
    verificacao: Mapped[dict[str, Any] | None] = mapped_column(Json)
    prosa_barrada: Mapped[dict[str, Any] | None] = mapped_column(Json)
    """A prosa que o verificador recusou, guardada para inspeção. Nunca volta como prosa."""
    erro: Mapped[str | None] = mapped_column(Text)


EM_ANDAMENTO = "em_andamento"
CONCLUIDA = "concluida"
ESTADOS_TAREFA = (EM_ANDAMENTO, CONCLUIDA, FALHOU)
"""`falhou` é a exploração que não terminou — modelo fora, API fora, processo de `agentes`
reiniciado — e o mesmo estado do relatório perdido. Nada se perde: as revisões já salvas
ficam, e continuar é disparar de novo na mesma simulação."""


class Tarefa(Base):
    """Uma exploração de variações sobre uma simulação, pedida no chat e acompanhada ao vivo.

    Objeto gravado, como a revisão e o relatório: a trilha do que o agente decidiu fica nos
    eventos, e a contagem sai deles, por código. Uma em andamento por simulação, garantido pelo
    banco: duas explorações disputariam as mesmas revisões de partida e o mesmo teto.
    """

    __tablename__ = "tarefa"
    __table_args__ = (
        Index(
            "uq_tarefa_em_andamento",
            "simulacao_id",
            unique=True,
            postgresql_where=text("estado = 'em_andamento'"),
            sqlite_where=text("estado = 'em_andamento'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulacao_id: Mapped[int] = mapped_column(
        ForeignKey("simulacao.id", ondelete="RESTRICT"), index=True
    )
    estado: Mapped[str] = mapped_column(String(12), default=EM_ANDAMENTO)
    teto: Mapped[int] = mapped_column(Integer)
    """Revisões que a exploração pode salvar. Revisão só conta quando é salva."""
    pedido: Mapped[str] = mapped_column(Text)
    revisao_partida_id: Mapped[int] = mapped_column(
        ForeignKey("simulacao_revisao.id", ondelete="RESTRICT")
    )
    """De onde a exploração parte. A faixa permitida é medida sobre ela, uma vez, e não sobre a
    revisão de partida de cada rodada."""
    faixa: Mapped[dict[str, Any]] = mapped_column(Json)
    """A faixa permitida que a pessoa confirmou (`arco_motor.variacao.FaixaPermitida`)."""
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    terminada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro: Mapped[str | None] = mapped_column(Text)
    relatorio_id: Mapped[int | None] = mapped_column(
        ForeignKey("relatorio.id", ondelete="RESTRICT")
    )


class Evento(Base):
    """Uma linha da trilha de uma tarefa. Só se acrescenta; nada se altera."""

    __tablename__ = "evento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tarefa_id: Mapped[int] = mapped_column(ForeignKey("tarefa.id", ondelete="RESTRICT"), index=True)
    instante: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tipo: Mapped[str] = mapped_column(String(30))
    dados: Mapped[dict[str, Any]] = mapped_column(Json)
