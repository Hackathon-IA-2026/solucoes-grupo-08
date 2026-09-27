"""Rotas de domínio: restrições, série, simular e simulações salvas.

Só vínculo **autorizado** alimenta ranking, série e simulação, e o que autoriza é conferência
por código contra o cadastro, não assinatura ([ADR 0008]). Casamento em que tensão, código de
circuito e os dois terminais concordaram, com candidato único, entra sozinho. O que ficou
duvidoso existe no banco e **não aparece**: falha de extração sai como falha, nunca como número
que ninguém conferiu.

A resposta de uma restrição lista a capacidade de **cada** equipamento, sem soma, média ou
número de conjunto — o cadastro não tem esse número e o produto não inventa.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import or_, select

from arco_api.banco import sessao
from arco_api.leitura import (
    Agregacao,
    Fonte,
    agregar,
    energia_por_restricao,
    fontes_com_serie,
    meias_horas,
)
from arco_api.modelos import (
    CASADO,
    POR_AGENTE,
    POR_PESSOA,
    REJEITADO,
    VALIDADO,
    AvisoRestricao,
    Equipamento,
    Restricao,
    RestricaoSnapshot,
    SerieRestricao,
    Simulacao,
    SimulacaoRevisao,
    Snapshot,
    VinculoRestricaoEquipamento,
    procedencia,
)
from arco_api.mudancas import descrever
from arco_dados.texto import MONITORADO
from arco_motor.cenarios import ValorInicial, valores_iniciais
from arco_motor.diagnosticos import Cruzamentos, cruzamentos, diagnosticar
from arco_motor.montar import (
    Alavanca,
    ConfiguracaoMontada,
    LinhaDoCadastro,
    montar_configuracao,
)
from arco_motor.ocorrencias import agrupar
from arco_motor.premissas import PREMISSAS_PADRAO, Premissa, Premissas
from arco_motor.relatorio import RevisaoCoberta, numero_br
from arco_motor.simular import simular as calcular
from arco_motor.tipos import Aviso, Cenario, Configuracao, Intervalo, Modalidade, Resultado
from arco_motor.tipos import SerieRestricao as SerieDoMotor
from arco_motor.variacao import teto_do_cadastro_mw
from arco_motor.versao import METODO_VERSAO

rotas = APIRouter()

AVISO_OCORRENCIAS = (
    "A contagem é sensível a artefato de apuração: uma meia hora titulada por outra razão parte "
    "em duas uma noite que fisicamente foi uma. Serve para auditoria, não como número de "
    "vitrine. O par a ler é ocorrência mais fatia de energia."
)


NOME_CURTO = (
    "Nome legível da restrição, composto por regra do texto do ONS: "
    "`LT 230 kV Açu III / Mossoró II · C1`, do equipamento **monitorado**, que é de quem a "
    "restrição trata. Forma fixa, sempre os mesmos campos na mesma ordem. `null` quando o texto "
    "não cita equipamento reconhecível — aí a tela cai em `texto`, que nunca é nulo."
)
CONTINGENCIA = (
    "O equipamento que a restrição supõe perder, no mesmo formato do nome. É contexto, não "
    "identidade, por isso fica fora de `nome_curto`: duas restrições sobre a mesma linha "
    "monitorada têm o mesmo nome e se distinguem por aqui. `null` quando o texto não cita um."
)
INSTRUCAO_OPERACAO = (
    "Código da Instrução de Operação do ONS, como `IO-ON.NE.5NE`. É por ele que quem opera acha "
    "a regra. `null` quando o texto não traz o código."
)

NOTA_MAXIMO = 1000
"""Caracteres da nota. É o porquê de uma configuração, não um relatório."""

REVISAO_ANTERIOR = (
    "A revisão de onde esta nasceu: a pedida em `revisao_base_id` ou, sem ela, a mais nova da "
    "simulação no momento de salvar. Não é necessariamente a gravada antes: duas revisões com a "
    "mesma origem são irmãs, e a simulação pode ter ramos ([ADR 0014]). `null` na primeira."
)
PROCEDENCIA_DA_REVISAO = (
    "Como a revisão nasceu: `por_pessoa`, salva por alguém na tela ou no chat, ou `por_agente`, "
    "criada por um agente numa exploração. Não é autor nem aprovação ([ADR 0011]). Revisão "
    "gravada antes do campo sai `por_pessoa`."
)
NOTA = (
    "O porquê desta configuração, escrito por quem a salvou. Sempre presente em `por_agente`; "
    "opcional em `por_pessoa`. É texto, nunca número de cálculo: o que mudou sai da comparação "
    "entre configurações, em `o_que_mudou`, e não daqui."
)


class ProcedenciaDaRevisao(StrEnum):
    """Como a revisão nasceu. Os valores são os de `modelos.PROCEDENCIA_REVISAO`."""

    POR_PESSOA = POR_PESSOA
    POR_AGENTE = POR_AGENTE


class SnapshotAtivo(BaseModel):
    """O snapshot do dado do ONS que alimenta todas as rotas de leitura."""

    id: str = Field(description="Identificador do snapshot, a data dele em `AAAA-MM-DD`.")
    carregado_em: datetime = Field(description="Quando a base derivada foi carregada no banco.")
    periodo_inicio: datetime | None = Field(
        description="Início da janela analisada, inclusivo. `null` se o snapshot não a declara."
    )
    periodo_fim: datetime | None = Field(
        description="Fim da janela analisada, exclusivo. `null` se o snapshot não a declara."
    )
    meias_horas_no_periodo: int | None = Field(
        description="Meias horas que o cálculo percorre: o tamanho da janela, e não a contagem "
        "de linhas da série, que é esparsa. `null` sem janela declarada."
    )


class EquipamentoNaTela(BaseModel):
    cod_equipamento: str = Field(description="Código do equipamento no cadastro do ONS.")
    papel: str = Field(
        description="Papel dentro da restrição: `monitorado` ou `contingenciado`. Vem do texto."
    )
    procedencia: str = Field(
        description="O que sustenta este vínculo, para a tela dizer de onde veio o equipamento. "
        "`automatica`: o casamento contra o cadastro do ONS bateu tensão, código de circuito e os "
        "dois terminais, com candidato único, e ninguém precisou decidir nada. `por_modelo`: um "
        "modelo leu o texto e a resposta passou pela mesma conferência contra o cadastro. "
        "`por_pessoa`: alguém validou e assinou. Não é estado de aprovação — é o apoio que o "
        "número tem."
    )
    nome: str | None = Field(default=None, description="Nome da linha no cadastro do ONS.")
    tensao_kv: int | None = Field(default=None, description="Tensão nominal, em kV.")
    subestacao_de: str | None = Field(default=None, description="Subestação de um terminal.")
    subestacao_para: str | None = Field(default=None, description="Subestação do outro terminal.")
    comprimento_km: float | None = Field(default=None, description="Comprimento da linha, em km.")
    proprietario: str | None = Field(default=None, description="Agente proprietário, no cadastro.")
    capacidade_longa_mva: float | None = Field(
        default=None,
        description="Capacidade de longa duração sem limitação, em MVA. Contexto de tela, não "
        "base de cálculo. É uma por equipamento: não existe soma nem média do conjunto.",
    )


class RestricaoNaLista(BaseModel):
    posicao: int = Field(description="Posição no ranking por energia cortada, a partir de 1.")
    id: str = Field(description="Identificador da restrição: hash do texto normalizado.")
    texto: str = Field(description="Texto original do ONS, campo `dsc_restricao`, inteiro.")
    nome_curto: str | None = Field(default=None, description=NOME_CURTO)
    contingencia: str | None = Field(default=None, description=CONTINGENCIA)
    instrucao_operacao: str | None = Field(default=None, description=INSTRUCAO_OPERACAO)
    energia_mwh: float = Field(description="Energia cortada na janela, em MWh, na fonte pedida.")
    fatia_do_total: float = Field(
        description="Fração de 0 a 1 da energia de `resumo.energia_mwh`. Soma 1 no ranking "
        "inteiro, e não só nos itens devolvidos por `limite`."
    )
    equipamentos: int = Field(description="Quantas linhas de transmissão a restrição tem.")
    subestacoes: list[str] = Field(
        description="Subestações onde as linhas da restrição terminam, sem repetição, em ordem "
        "alfabética."
    )
    ocorrencias: int | None = Field(
        default=None,
        description="Episódios de corte no período: intervalos com corte seguidos no tempo, "
        "pela regra do motor. É número de auditoria, não de vitrine — sensível a artefato de "
        "apuração, porque uma meia hora titulada por outra razão parte em duas uma noite que "
        "fisicamente foi uma. O par a ler é ocorrência mais fatia de energia. Detalhe em "
        "`GET /restricoes/{restricao_id}/ocorrencias`.",
    )
    snapshot_id: str = Field(description="Snapshot de onde o número saiu.")


class ResumoDasRestricoes(BaseModel):
    """Totais do ranking inteiro, independentes de `limite`."""

    fonte: Fonte = Field(description="Fonte de geração a que os números se referem.")
    snapshot_id: str = Field(description="Snapshot de onde os números saíram.")
    restricoes: int = Field(description="Quantas restrições estão no ranking.")
    energia_mwh: float = Field(
        description="Energia cortada somada das restrições do ranking, em MWh. É o denominador "
        "de `fatia_do_total`. Restrição sem vínculo autorizado não entra."
    )
    aviso_ocorrencias: str = Field(
        description="Limite da contagem de `ocorrencias` de cada item, para aparecer junto dela "
        "na interface. O invariante manda aviso visível, e a premissa que governa o número está "
        "com status `proposta`: número assim não sai seco."
    )


class ListaDeRestricoes(BaseModel):
    resumo: ResumoDasRestricoes
    itens: list[RestricaoNaLista] = Field(description="Em ordem decrescente de energia cortada.")


class AvisoDaRestricao(BaseModel):
    codigo: str = Field(description="Código estável do aviso.")
    mensagem: str = Field(description="Texto do aviso, pronto para a tela.")
    fonte: str | None = Field(default=None, description="De onde o aviso saiu, quando há.")


class RestricaoDetalhada(BaseModel):
    id: str = Field(description="Identificador da restrição: hash do texto normalizado.")
    texto: str = Field(description="Texto original do ONS, campo `dsc_restricao`, inteiro.")
    nome_curto: str | None = Field(default=None, description=NOME_CURTO)
    contingencia: str | None = Field(default=None, description=CONTINGENCIA)
    instrucao_operacao: str | None = Field(default=None, description=INSTRUCAO_OPERACAO)
    origem: str = Field(description="`cod_origemrestricao` do ONS. No escopo, sempre `LOC`.")
    razao: str = Field(description="`cod_razaorestricao` do ONS. No escopo, sempre `CNF`.")
    fonte: Fonte = Field(description="Fonte a que `energia_mwh` e `fatia_do_total` se referem.")
    fontes: list[str] = Field(
        description="Fontes de geração com corte registrado nesta restrição: `eolica`, `solar`."
    )
    energia_mwh: float = Field(description="Energia cortada na janela, em MWh, na fonte pedida.")
    fatia_do_total: float = Field(
        description="Fração de 0 a 1 da energia do ranking inteiro na mesma fonte. Zero quando "
        "o ranking não tem energia."
    )
    subestacoes: list[str] = Field(
        description="Subestações onde as linhas da restrição terminam, sem repetição."
    )
    avisos: list[AvisoDaRestricao] = Field(
        description="Avisos vigentes da restrição. Lista vazia até a feature 09 preenchê-los."
    )
    snapshot_id: str = Field(description="Snapshot do dado e versão do cadastro exibido.")
    presente_no_snapshot: bool = Field(
        description="A restrição foi medida no snapshot ativo. Quando `false`, ela existe como "
        "identidade — e por isso vínculo, avisos e simulações salvas continuam apontando para "
        "ela — mas não teve corte apurado neste snapshot: `energia_mwh`, `fatia_do_total` e "
        "`fontes` vêm zerados ou vazios, e `texto` é o primeiro texto visto, não o do dia. "
        "Pode acontecer porque ela deixou de cortar, ou porque o ONS reescreveu o texto e ela "
        "virou outra ([ADR 0009])."
    )
    equipamentos: list[EquipamentoNaTela] = Field(
        description="Linhas com vínculo autorizado, cada uma com a capacidade dela."
    )


class PontoDaSerie(BaseModel):
    instante: datetime = Field(description="Início da meia hora.")
    corte_mw: float = Field(description="Corte médio na meia hora, em MW.")
    minutos_cnf: int | None = Field(
        default=None,
        description="Minutos da meia hora com corte por razão CNF. `null`: dado ausente.",
    )


class BaldeDaSerie(BaseModel):
    inicio: datetime = Field(
        description="Início do balde: o dia, a segunda-feira da semana ou o dia 1 do mês."
    )
    energia_mwh: float = Field(description="Energia cortada no balde, em MWh. Zero sem corte.")


class SerieNaTela(BaseModel):
    restricao_id: str
    snapshot_id: str
    fonte: Fonte
    agregacao: Agregacao
    pontos: list[PontoDaSerie] = Field(
        description="Só com `agregacao=meia_hora`. Esparsa: meia hora sem corte não tem ponto."
    )
    baldes: list[BaldeDaSerie] = Field(
        description="Só com `agregacao` de `dia`, `semana` ou `mes`. Cobre a janela do snapshot "
        "inteira, e a soma é a `energia_mwh` da restrição na mesma fonte."
    )


class OcorrenciaNaTela(BaseModel):
    """Um episódio de corte da restrição, para auditoria."""

    inicio: datetime = Field(description="Início da primeira meia hora com corte.")
    fim: datetime = Field(
        description="Fecho da última meia hora com corte. Uma ocorrência de um único intervalo "
        "dura meia hora, e não zero."
    )
    intervalos: int = Field(description="Meias horas com corte dentro do episódio.")
    duracao_horas: float = Field(
        description="Relógio do início ao fim. Igual a `intervalos` x 0,5 enquanto a tolerância "
        "da premissa for zero, que é o padrão."
    )
    energia_mwh: float = Field(description="Energia cortada no episódio.")
    corte_medio_maximo_mw: float = Field(
        description="Maior potência **média** de meia hora do episódio. Não é o pico: a série do "
        "ONS é média da meia hora. Cem MW médios com 10 minutos de corte são 300 MW de pico, e é "
        "contra o pico que a simulação dimensiona a alavanca.",
    )


class OcorrenciasNaTela(BaseModel):
    restricao_id: str
    snapshot_id: str
    fonte: Fonte
    total: int = Field(description="Quantas ocorrências no período do snapshot.")
    energia_mwh: float = Field(
        description="Soma das ocorrências, igual à `energia_mwh` da restrição na mesma fonte."
    )
    aviso: str = Field(
        description="Limite do número, para aparecer junto dele na interface, como manda o "
        "invariante."
    )
    itens: list[OcorrenciaNaTela] = Field(
        description="Da maior energia para a menor, que é a ordem de quem audita."
    )


class PremissasNaTela(BaseModel):
    """O que a tela precisa antes de existir cálculo: com que valor abrir e o status de cada um."""

    cenario: Cenario = Field(description="Cenário a que `valores_iniciais` se refere.")
    modalidade: Modalidade | None = Field(
        description="Modalidade a que os valores se ajustam, quando o pedido a informa. Sem ela, "
        "os valores são os do cenário sem ajuste."
    )
    valores_iniciais: list[ValorInicial] = Field(
        description="Valor inicial de cada campo da configuração, com unidade, fonte e status. "
        "Todos editáveis: o cenário só preenche. Campo que não aparece aqui não tem premissa com "
        "fonte e fica no padrão do tipo."
    )
    metodo: list[Premissa] = Field(
        description="Premissas de método que o cálculo aplica, `preco_energia` entre elas. Não "
        "são campos do formulário; a tela as exibe com o status ao lado."
    )


class PedidoDeSimulacao(BaseModel):
    """Um cálculo pedido.

    **Conferência que só a rota faz, porque depende do dado do snapshot** — nenhum esquema a
    expressa, e o cliente só descobre chamando:

    - `configuracao.equipamento.cod_equipamento` tem de ter vínculo autorizado **nesta**
      restrição, senão `422`;
    - `configuracao.bateria.subestacao` tem de ser terminal de um equipamento autorizado **desta**
      restrição, senão `422`;
    - restrição sem nenhum vínculo autorizado responde `409`: o casamento com o cadastro ficou
      duvidoso e ninguém resolveu.

    Os equipamentos e as subestações válidos de uma restrição saem de
    `GET /restricoes/{restricao_id}`, e é de lá que a tela deve montar as escolhas.
    """

    restricao_id: str = Field(description="A restrição simulada. Uma simulação, uma restrição.")
    configuracao: Configuracao = Field(
        description="Modalidade e parâmetros técnicos e financeiros."
    )
    fonte: Fonte = Field(
        default=Fonte.EOLICA,
        description="Fonte de geração cujo corte entra no cálculo. `ambas` soma as duas.",
    )
    correcao_minutos: bool = Field(
        default=True,
        description="Premissa `correcao_minutos`: corrige a potência cortada pelos minutos de "
        "corte dentro da meia hora. Ligada por padrão. Desligar fica registrado em "
        "`premissas_usadas`, com status `proposta`.",
    )
    snapshot_id: str | None = Field(
        default=None, description="Snapshot do cálculo. Vazio usa o snapshot ativo."
    )


class PedidoDeSalvamento(PedidoDeSimulacao):
    nome: str = Field(min_length=1, max_length=200, description="Nome da simulação.")
    pergunta: str | None = Field(
        default=None,
        description="A pergunta que esta simulação responde, opcional. Só vale ao criar: "
        "revisão nova herda a da simulação.",
    )
    restricao_id: str | None = Field(  # type: ignore[assignment]
        default=None,
        description="A restrição simulada. Obrigatória ao **criar**; proibida ao revisar, onde "
        "ela vem da simulação. Mandar as duas seria ter a mesma informação em dois lugares, e "
        "quando discordassem o cálculo usaria uma e o registro ficaria sob a outra.",
    )
    simulacao_id: int | None = Field(
        default=None,
        description="A simulação que recebe esta revisão. Com ele, a revisão entra na simulação "
        "existente, nascida de `revisao_base_id` ou, sem ele, da revisão mais nova dela; sem "
        "`simulacao_id`, nasce uma simulação nova.",
    )
    revisao_base_id: int | None = Field(
        default=None,
        description="A revisão de onde esta nasce, que tem de ser da simulação de "
        "`simulacao_id`: `422` se for de outra ou não existir. Sem ele, a revisão nasce da mais "
        "nova da simulação, como a tela faz. Só vale ao revisar: ao criar, não há de onde "
        "nascer. É o que permite variações irmãs, cada uma comparada com a mesma origem "
        "([ADR 0014]).",
    )
    procedencia: ProcedenciaDaRevisao = Field(
        default=ProcedenciaDaRevisao.POR_PESSOA,
        description="Como esta revisão nasce. Não é autor nem aprovação ([ADR 0011]). "
        "`por_agente` sem `nota` é `422`.",
    )
    nota: str | None = Field(
        default=None,
        max_length=NOTA_MAXIMO,
        description=f"O porquê desta configuração, até {NOTA_MAXIMO} caracteres. Obrigatória em "
        "`por_agente`, opcional em `por_pessoa`. Em branco conta como ausente. Texto, nunca "
        "número de cálculo.",
    )

    @field_validator("nota")
    @classmethod
    def _nota_em_branco_e_ausente(cls, nota: str | None) -> str | None:
        return (nota or "").strip() or None

    @model_validator(mode="after")
    def _cria_ou_revisa(self) -> PedidoDeSalvamento:
        if (self.restricao_id is None) == (self.simulacao_id is None):
            raise ValueError(
                "informe `restricao_id` para criar uma simulação, ou `simulacao_id` para "
                "revisar uma existente — exatamente um dos dois"
            )
        if self.revisao_base_id is not None and self.simulacao_id is None:
            raise ValueError(
                "`revisao_base_id` só vale ao revisar, com `simulacao_id`: a primeira revisão "
                "de uma simulação não nasce de nenhuma"
            )
        if self.procedencia is ProcedenciaDaRevisao.POR_AGENTE and self.nota is None:
            raise ValueError(
                "revisão `por_agente` exige `nota`, com o porquê da configuração: sem ela, a "
                "exploração vira uma lista de números sem a decisão que os pediu"
            )
        return self


class RevisaoIrma(BaseModel):
    """Uma revisão vista de outra: o bastante para o seletor, sem carregar o resultado dela."""

    id: int
    posicao: int = Field(
        description="Posição na simulação, de 1 a N em ordem de gravação. A árvore, quando há "
        "ramos, se lê por `revisao_anterior_id`."
    )
    atual: bool = Field(description="Verdadeiro só na revisão mais nova da simulação.")
    criada_em: datetime
    revisao_anterior_id: int | None = Field(description=REVISAO_ANTERIOR)
    procedencia: ProcedenciaDaRevisao = Field(description=PROCEDENCIA_DA_REVISAO)
    nota: str | None = Field(description=NOTA)


class RevisaoNaLista(RevisaoIrma):
    """Uma revisão como a listagem a mostra: o bastante para decidir se vale abrir."""

    snapshot_id: str = Field(description="Snapshot do ONS sobre o qual esta revisão foi calculada.")
    metodo_versao: str = Field(description="Versão do método de cálculo em vigor ao salvar.")
    periodo_inicio: datetime | None = Field(
        description="Início da janela analisada **por esta revisão**, que é a do snapshot dela e "
        "não a do ativo. `null` se aquele snapshot não a declara."
    )
    periodo_fim: datetime | None = Field(description="Fim da janela analisada por esta revisão.")
    vpl_reais: float | None = Field(
        description="VPL do investimento, em reais. `null` em revisão gravada sem o campo."
    )
    energia_recuperada_mwh: float | None = Field(
        description="Energia recuperada na janela, em MWh. `null` em revisão gravada sem o campo."
    )
    o_que_mudou: str = Field(
        description="O que mudou da revisão de onde esta nasceu (`revisao_anterior_id`) para "
        "esta, em uma frase, comparando as configurações. Gerado, não digitado: o porquê fica "
        "em `nota`, e o quê sai da comparação, que não envelhece nem mente."
    )


class SimulacaoNaLista(BaseModel):
    """Uma simulação e o histórico dela. A listagem é por simulação, não por revisão."""

    id: int
    nome: str
    pergunta: str | None = Field(description="A pergunta que a simulação responde, se houver.")
    restricao_id: str
    restricao_texto: str | None = Field(
        description="Texto do ONS da restrição, do snapshot da revisão mais nova. `null` quando a "
        "restrição não existe naquele snapshot. `nome_curto` é feature 10."
    )
    modalidade: Modalidade | None = Field(
        description="Modalidade da revisão mais nova. `null` em revisão gravada sem o campo."
    )
    criada_em: datetime
    revisoes: list[RevisaoNaLista] = Field(
        description="Da mais nova para a mais velha. Sempre ao menos uma: salvar cria revisão."
    )


class RevisaoSalva(BaseModel):
    id: int = Field(description="Identificador da revisão.")
    simulacao_id: int = Field(description="A simulação a que a revisão pertence.")
    nome: str = Field(description="Nome da simulação.")
    pergunta: str | None = Field(description="A pergunta que a simulação responde, se houver.")
    restricao_id: str
    snapshot_id: str = Field(description="Snapshot do dado usado no cálculo.")
    metodo_versao: str = Field(description="Versão do método de cálculo em vigor ao salvar.")
    revisao_anterior_id: int | None = Field(description=REVISAO_ANTERIOR)
    procedencia: ProcedenciaDaRevisao = Field(description=PROCEDENCIA_DA_REVISAO)
    nota: str | None = Field(description=NOTA)
    criada_em: datetime


class RevisaoCompleta(RevisaoSalva):
    """A revisão como foi salva: o que entrou, as premissas com status e o que saiu."""

    periodo_inicio: datetime | None = Field(
        description="Início da janela analisada, do snapshot desta revisão."
    )
    periodo_fim: datetime | None = Field(description="Fim da janela analisada.")
    configuracao: Configuracao
    premissas_usadas: dict[str, Premissa]
    resultado: Resultado
    avisos: list[Aviso]
    revisoes: list[RevisaoIrma] = Field(
        description="As revisões da mesma simulação, da mais nova para a mais velha, com esta "
        "entre elas. É o que o seletor de revisão precisa, sem carregar a listagem inteira."
    )
    cruzamentos: Cruzamentos = Field(
        description="Entre as revisões da simulação: onde o payback simples passa a caber no "
        "horizonte e onde a TIR passa da taxa, com a revisão de cada lado, sem interpolar. Os "
        "diagnósticos desta revisão estão em `resultado.diagnosticos`."
    )


CONTINGENCIADA_NAO_RECEBE = (
    "não recebe circuito novo: o método só modela adição de circuito na linha monitorada, e esta "
    "é a que se supõe perder"
)
"""O texto da jornada da feature 17, o mesmo na tela, no 422 e na ferramenta do MCP."""


def _confere_escolhas(config: Configuracao, equipamentos: list[EquipamentoNaTela]) -> None:
    """O que a configuração escolhe precisa existir na restrição e caber no que o método modela.

    - o equipamento que recebe o circuito tem vínculo autorizado **e é o monitorado**: a
      contingenciada é a linha que se supõe perder, e circuito novo nela daria VPL de uma
      intervenção que o método não calcula;
    - a subestação da bateria é terminal de uma linha autorizada, contingenciada inclusive: a
      bateria se prende à restrição, não a um equipamento;
    - potência da bateria e ganho de limite não passam de `teto_alavanca_capacidade` vezes a
      capacidade de longa duração da linha de maior capacidade da restrição.

    Vale para a pessoa e para o agente. É conferência de rota, não do motor: o motor não lê
    banco e não sabe o que existe no cadastro deste snapshot."""
    if config.equipamento is not None:
        codigo = config.equipamento.cod_equipamento
        papeis = {e.papel for e in equipamentos if e.cod_equipamento == codigo}
        if not papeis:
            raise HTTPException(
                status_code=422,
                detail=f"equipamento {codigo} não tem vínculo autorizado nesta restrição",
            )
        if MONITORADO not in papeis:
            raise HTTPException(
                status_code=422, detail=f"equipamento {codigo} {CONTINGENCIADA_NAO_RECEBE}"
            )
    if config.bateria is not None:
        subestacao = config.bateria.subestacao
        if subestacao not in _subestacoes(equipamentos):
            raise HTTPException(
                status_code=422,
                detail=f"subestação {subestacao} não é terminal de equipamento autorizado desta "
                "restrição",
            )
    teto = teto_do_cadastro_mw(_cadastro(equipamentos), PREMISSAS_PADRAO)
    if teto is None:
        return
    for campo, valor in (
        ("bateria.potencia_mw", config.bateria.potencia_mw if config.bateria else None),
        (
            "equipamento.ganho_limite_mw",
            config.equipamento.ganho_limite_mw if config.equipamento else None,
        ),
    ):
        if valor is not None and valor > teto:
            raise HTTPException(
                status_code=422,
                detail=f"{campo} de {numero_br(valor)} MW passa do teto de {numero_br(teto)} MW, "
                "a capacidade de longa duração da linha de maior capacidade da restrição no "
                "cadastro, lida como MW (premissa `teto_alavanca_capacidade`): potência acima da "
                "capacidade de cadastro não é caso que o método represente. O teto é múltiplo "
                "declarado do cadastro, não limite físico",
            )


def _cadastro(equipamentos: list[EquipamentoNaTela]) -> list[LinhaDoCadastro]:
    """As linhas da restrição como o motor as lê para montar configuração e faixa."""
    return [
        LinhaDoCadastro(
            cod_equipamento=e.cod_equipamento,
            papel=e.papel,
            tensao_kv=e.tensao_kv,
            comprimento_km=e.comprimento_km,
            capacidade_longa_mva=e.capacidade_longa_mva,
            subestacao_de=e.subestacao_de,
            subestacao_para=e.subestacao_para,
        )
        for e in equipamentos
    ]


def _snapshot_ativo(s) -> str:  # type: ignore[no-untyped-def]
    ativo = s.scalar(select(Snapshot.id).where(Snapshot.ativo.is_(True)))
    if ativo is None:
        raise HTTPException(status_code=409, detail="nenhum snapshot ativo; rode a carga")
    return ativo


def _autorizados(restricao_id: str | None = None):  # type: ignore[no-untyped-def]
    """Vínculos que alimentam ranking, série e simulação. Quem autoriza é código, não assinatura.

    `casado` quer dizer que tensão, código de circuito e os dois terminais concordaram contra o
    cadastro, com candidato único: quatro informações independentes, e nenhuma escolha. Entra.

    `provavel`, `ambiguo` e `sem_candidato` ficam de fora — ali houve chute, e vínculo errado não
    estoura erro, vira capacidade errada e VPL errado com cara de número bom.

    Quem uma pessoa validou entra de qualquer situação, porque ela decidiu olhando. E `rejeitado`
    nunca entra, mesmo casado: o veto de gente vale mais que a concordância do código.
    """
    consulta = select(VinculoRestricaoEquipamento).where(
        VinculoRestricaoEquipamento.cod_equipamento.is_not(None),
        VinculoRestricaoEquipamento.status != REJEITADO,
        or_(
            VinculoRestricaoEquipamento.status == VALIDADO,
            VinculoRestricaoEquipamento.situacao == CASADO,
        ),
    )
    if restricao_id is not None:
        consulta = consulta.where(VinculoRestricaoEquipamento.restricao_id == restricao_id)
    return consulta


@rotas.get("/snapshot", tags=["snapshot"], operation_id="ver_snapshot")
def ver_snapshot() -> SnapshotAtivo:
    """O snapshot ativo e a janela analisada. `409` enquanto nenhuma carga foi feita."""
    with sessao() as s:
        snapshot = s.get(Snapshot, _snapshot_ativo(s))
        assert snapshot is not None
        return SnapshotAtivo(
            id=snapshot.id,
            carregado_em=snapshot.carregado_em,
            periodo_inicio=snapshot.periodo_inicio,
            periodo_fim=snapshot.periodo_fim,
            meias_horas_no_periodo=meias_horas(snapshot.periodo_inicio, snapshot.periodo_fim),
        )


@rotas.get("/premissas", tags=["premissas"], operation_id="listar_premissas")
def listar_premissas(
    cenario: Annotated[
        Cenario, Query(description="Cenário dos valores iniciais. Só preenche; tudo é editável.")
    ] = Cenario.REFERENCIA,
    modalidade: Annotated[
        Modalidade | None,
        Query(
            description="Modalidade já escolhida na etapa 3. Muda o horizonte inicial: em "
            "`bateria` ele é a vida útil da bateria, e não o da linha de transmissão, que a "
            "ultrapassa nos três cenários."
        ),
    ] = None,
) -> PremissasNaTela:
    """Com que valores a tela abre o formulário, e o status de cada um. Não toca o banco."""
    return PremissasNaTela(
        cenario=cenario,
        modalidade=modalidade,
        valores_iniciais=valores_iniciais(cenario, modalidade),
        metodo=list(PREMISSAS_PADRAO.itens.values()),
    )


def _ranking(s, snapshot_id: str, fonte: Fonte) -> list[tuple[str, float]]:  # type: ignore[no-untyped-def]
    """Restrições com vínculo autorizado e corte na fonte pedida, da maior energia para a menor."""
    autorizadas = {vinculo.restricao_id for vinculo in s.scalars(_autorizados())}
    energia = energia_por_restricao(s, snapshot_id, fonte)
    ranking = [(id, mwh) for id, mwh in energia.items() if id in autorizadas and mwh > 0]
    return sorted(ranking, key=lambda par: (-par[1], par[0]))


def _equipamentos(s, restricao_id: str, snapshot_id: str) -> list[EquipamentoNaTela]:  # type: ignore[no-untyped-def]
    equipamentos = []
    for vinculo in s.scalars(_autorizados(restricao_id)):
        cadastro = s.get(Equipamento, (vinculo.cod_equipamento, snapshot_id))
        capacidades = (cadastro.capacidades or {}) if cadastro else {}
        equipamentos.append(
            EquipamentoNaTela(
                cod_equipamento=str(vinculo.cod_equipamento),
                papel=vinculo.papel,
                procedencia=procedencia(vinculo),
                nome=cadastro.nome if cadastro else None,
                tensao_kv=cadastro.tensao_kv if cadastro else None,
                subestacao_de=cadastro.subestacao_de if cadastro else None,
                subestacao_para=cadastro.subestacao_para if cadastro else None,
                comprimento_km=cadastro.comprimento_km if cadastro else None,
                proprietario=cadastro.proprietario if cadastro else None,
                capacidade_longa_mva=capacidades.get("val_capacoperlongasemlimit"),
            )
        )
    return equipamentos


def _subestacoes(equipamentos: list[EquipamentoNaTela]) -> list[str]:
    nomes = {e.subestacao_de for e in equipamentos} | {e.subestacao_para for e in equipamentos}
    return sorted(nome for nome in nomes if nome)


@rotas.get("/restricoes", tags=["restricoes"], operation_id="listar_restricoes")
def listar_restricoes(
    fonte: Annotated[Fonte, Query(description="Fonte de geração do ranking.")] = Fonte.EOLICA,
    limite: int = Query(default=50, ge=1, le=500, description="Máximo de itens devolvidos."),
) -> ListaDeRestricoes:
    """Ranking por energia cortada na fonte pedida. Só entra restrição com vínculo autorizado."""
    with sessao() as s:
        snapshot_id = _snapshot_ativo(s)
        ranking = _ranking(s, snapshot_id, fonte)
        total = sum(mwh for _, mwh in ranking)
        exibidas = [restricao_id for restricao_id, _ in ranking[:limite]]
        ocorrencias = _contagem_de_ocorrencias(s, snapshot_id, fonte.value, exibidas)
        itens = []
        for posicao, (restricao_id, mwh) in enumerate(ranking[:limite], start=1):
            medicao = s.get(RestricaoSnapshot, (restricao_id, snapshot_id))
            identidade = s.get(Restricao, restricao_id)
            if medicao is None or identidade is None:
                continue
            equipamentos = _equipamentos(s, restricao_id, snapshot_id)
            itens.append(
                RestricaoNaLista(
                    posicao=posicao,
                    id=restricao_id,
                    texto=medicao.texto,
                    nome_curto=identidade.nome_curto,
                    contingencia=identidade.contingencia,
                    instrucao_operacao=identidade.instrucao_operacao,
                    energia_mwh=mwh,
                    fatia_do_total=mwh / total,
                    equipamentos=len(equipamentos),
                    subestacoes=_subestacoes(equipamentos),
                    ocorrencias=ocorrencias.get(restricao_id, 0),
                    snapshot_id=snapshot_id,
                )
            )
        return ListaDeRestricoes(
            resumo=ResumoDasRestricoes(
                fonte=fonte,
                snapshot_id=snapshot_id,
                restricoes=len(ranking),
                energia_mwh=total,
                aviso_ocorrencias=AVISO_OCORRENCIAS,
            ),
            itens=itens,
        )


@rotas.get("/restricoes/{restricao_id}", tags=["restricoes"], operation_id="ver_restricao")
def ver_restricao(
    restricao_id: str,
    fonte: Annotated[Fonte, Query(description="Fonte de geração dos números.")] = Fonte.EOLICA,
) -> RestricaoDetalhada:
    """A restrição com os equipamentos autorizados dela, cada um com a capacidade dele.

    `404` só quando a identidade não existe. Identidade que existe e não foi medida no snapshot
    ativo responde `200` com `presente_no_snapshot` falso: ela não some, porque vínculo, avisos e
    simulações salvas apontam para ela ([ADR 0009]), e uma simulação salva tem de continuar
    abrindo mesmo quando a restrição sai do snapshot.
    """
    with sessao() as s:
        snapshot_id = _snapshot_ativo(s)
        restricao = s.get(Restricao, restricao_id)
        if restricao is None:
            raise HTTPException(status_code=404, detail="restrição não existe")
        medicao = s.get(RestricaoSnapshot, (restricao_id, snapshot_id))
        ranking = dict(_ranking(s, snapshot_id, fonte)) if medicao else {}
        total = sum(ranking.values())
        energia = (
            energia_por_restricao(s, snapshot_id, fonte).get(restricao_id, 0.0) if medicao else 0.0
        )
        equipamentos = _equipamentos(s, restricao_id, snapshot_id)
        avisos = s.scalars(
            select(AvisoRestricao).where(AvisoRestricao.restricao_id == restricao_id)
        ).all()
        return RestricaoDetalhada(
            id=restricao.id,
            texto=medicao.texto if medicao else restricao.texto,
            nome_curto=restricao.nome_curto,
            contingencia=restricao.contingencia,
            instrucao_operacao=restricao.instrucao_operacao,
            origem=restricao.origem,
            razao=restricao.razao,
            fonte=fonte,
            fontes=fontes_com_serie(s, snapshot_id, restricao_id) if medicao else [],
            energia_mwh=energia,
            fatia_do_total=ranking.get(restricao_id, 0.0) / total if total else 0.0,
            subestacoes=_subestacoes(equipamentos),
            avisos=[
                AvisoDaRestricao(codigo=a.codigo, mensagem=a.mensagem, fonte=a.fonte)
                for a in avisos
            ],
            snapshot_id=snapshot_id,
            presente_no_snapshot=medicao is not None,
            equipamentos=equipamentos,
        )


class ConfiguracaoNaTela(ConfiguracaoMontada):
    """A configuração que a alavanca monta, antes de salvar: o cartão da revisão."""

    restricao_id: str
    snapshot_id: str = Field(
        description="Snapshot do cadastro de onde saíram tensão e comprimento."
    )


@rotas.get(
    "/restricoes/{restricao_id}/montar", tags=["simulacoes"], operation_id="montar_configuracao"
)
def montar(
    restricao_id: str,
    modalidade: Annotated[Modalidade, Query(description="O que se instala.")],
    cenario: Annotated[
        Cenario, Query(description="Cenário dos valores iniciais e do custo unitário.")
    ] = Cenario.REFERENCIA,
    potencia_mw: Annotated[
        float | None, Query(gt=0, description="Potência da bateria. Com bateria, obrigatória.")
    ] = None,
    capacidade_mwh: Annotated[
        float | None, Query(gt=0, description="Capacidade da bateria. Com bateria, obrigatória.")
    ] = None,
    subestacao: Annotated[
        str | None,
        Query(description="Subestação de conexão da bateria, terminal de linha da restrição."),
    ] = None,
    cod_equipamento: Annotated[
        str | None,
        Query(
            description="A linha **monitorada** que recebe o circuito. Com circuito, obrigatória."
        ),
    ] = None,
    ganho_limite_mw: Annotated[
        float | None, Query(ge=0, description="Ganho de limite do circuito novo.")
    ] = None,
) -> ConfiguracaoNaTela:
    """A configuração inteira a partir da alavanca, sem calcular nem salvar.

    Cada campo sai com a premissa, a fonte e o status: os valores iniciais do cenário, os
    padrões do tipo e o investimento inicial por custo unitário vezes quantidade, com a conta em
    `investimento`. É o que o cartão da revisão mostra antes do botão que salva; a configuração
    devolvida vai inteira em `POST /simulacoes`.

    `422` quando a alavanca não combina com a modalidade (bateria pede potência, capacidade e
    subestação; circuito pede linha e ganho) e pelas mesmas conferências de salvar: linha
    contingenciada não recebe circuito, subestação tem de ser terminal da restrição, potência e
    ganho têm teto pela capacidade da linha. `409` na restrição sem vínculo autorizado.
    """
    bateria = {
        "potencia_mw": potencia_mw,
        "capacidade_mwh": capacidade_mwh,
        "subestacao": subestacao,
    }
    circuito = {"cod_equipamento": cod_equipamento, "ganho_limite_mw": ganho_limite_mw}
    try:
        alavanca = Alavanca.model_validate(
            {
                "bateria": bateria if modalidade is not Modalidade.EQUIPAMENTO else None,
                "circuito": circuito if modalidade is not Modalidade.BATERIA else None,
            }
        )
    except ValidationError as erro:
        faltam = sorted({str(e["loc"][-1]) for e in erro.errors()})
        raise HTTPException(
            status_code=422, detail=f"modalidade {modalidade} pede {', '.join(faltam)}"
        ) from erro
    with sessao() as s:
        snapshot_id = _snapshot_ativo(s)
        if s.get(Restricao, restricao_id) is None:
            raise HTTPException(status_code=404, detail="restrição não existe")
        equipamentos = _equipamentos(s, restricao_id, snapshot_id)
    if not equipamentos:
        raise HTTPException(
            status_code=409,
            detail="restrição sem vínculo autorizado: o casamento com o cadastro ficou "
            "duvidoso e ninguém resolveu ainda",
        )
    try:
        montada = montar_configuracao(
            modalidade, cenario, alavanca, PREMISSAS_PADRAO, _cadastro(equipamentos)
        )
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    _confere_escolhas(montada.configuracao, equipamentos)
    return ConfiguracaoNaTela(
        restricao_id=restricao_id, snapshot_id=snapshot_id, **montada.model_dump()
    )


def _pontos(s, restricao_id: str, snapshot_id: str, fonte: str):  # type: ignore[no-untyped-def]
    consulta = select(SerieRestricao).where(
        SerieRestricao.restricao_id == restricao_id,
        SerieRestricao.snapshot_id == snapshot_id,
    )
    if fonte != "ambas":
        consulta = consulta.where(SerieRestricao.fonte == fonte)
    linhas = s.scalars(consulta.order_by(SerieRestricao.instante)).all()
    cruas = [(x.instante, x.corte_mw, x.minutos_cnf) for x in linhas]
    return cruas if fonte != "ambas" else _somar_fontes(cruas)


def _somar_fontes(linhas):  # type: ignore[no-untyped-def]
    """Com `ambas`, a série é a soma das duas fontes na mesma meia hora."""
    somado: dict[datetime, list[float]] = {}
    for instante, corte_mw, minutos_cnf in linhas:
        atual = somado.setdefault(instante, [0.0, 0.0, 0.0])
        atual[0] += corte_mw
        if minutos_cnf is not None:
            atual[1] += corte_mw * minutos_cnf
            atual[2] += corte_mw
    return [
        (instante, mw, round(peso / base) if base > 0 else None)
        for instante, (mw, peso, base) in sorted(somado.items())
    ]


def _contagem_de_ocorrencias(s, snapshot_id: str, fonte: str, restricao_ids):  # type: ignore[no-untyped-def]
    """Quantas ocorrências por restrição, para a lista, numa consulta só.

    Agrupar aqui pela mesma função do motor vale mais que uma contagem em SQL: a regra ficaria
    em dois lugares, e é regra de cálculo.

    A consulta se limita às restrições do ranking, não ao snapshot inteiro. Não é só volume —
    as de fora nunca apareceriam na lista, e `Intervalo` valida o que lê, então uma linha ruim
    numa restrição sem vínculo derrubaria a listagem toda com 500.
    """
    if not restricao_ids:
        return {}
    consulta = select(SerieRestricao).where(
        SerieRestricao.snapshot_id == snapshot_id,
        SerieRestricao.restricao_id.in_(restricao_ids),
    )
    if fonte != "ambas":
        consulta = consulta.where(SerieRestricao.fonte == fonte)
    por_restricao: dict[str, list[tuple[datetime, float, int | None]]] = {}
    for x in s.scalars(consulta.order_by(SerieRestricao.restricao_id, SerieRestricao.instante)):
        por_restricao.setdefault(x.restricao_id, []).append((x.instante, x.corte_mw, x.minutos_cnf))
    contagem: dict[str, int] = {}
    for restricao_id, linhas in por_restricao.items():
        pontos = linhas if fonte != "ambas" else _somar_fontes(linhas)
        serie = SerieDoMotor(
            restricao_id=restricao_id,
            snapshot_id=snapshot_id,
            intervalos=[Intervalo(instante=i, corte_mw=mw, minutos_cnf=m) for i, mw, m in pontos],
        )
        contagem[restricao_id] = len(agrupar(serie, PREMISSAS_PADRAO))
    return contagem


@rotas.get("/restricoes/{restricao_id}/serie", tags=["restricoes"], operation_id="ver_serie")
def ver_serie(
    restricao_id: str,
    fonte: Annotated[Fonte, Query(description="Fonte de geração da série.")] = Fonte.EOLICA,
    agregacao: Annotated[
        Agregacao,
        Query(
            description="`meia_hora` devolve `pontos` em MW; as outras devolvem `baldes` em MWh."
        ),
    ] = Agregacao.MEIA_HORA,
) -> SerieNaTela:
    """Série da restrição no snapshot ativo, crua ou somada por dia, semana ou mês."""
    with sessao() as s:
        snapshot_id = _snapshot_ativo(s)
        pontos = _pontos(s, restricao_id, snapshot_id, fonte.value)
        snapshot = s.get(Snapshot, snapshot_id)
        assert snapshot is not None
        crua = agregacao is Agregacao.MEIA_HORA
        baldes = (
            []
            if crua
            else agregar(
                ((i, mw) for i, mw, _ in pontos),
                agregacao,
                snapshot.periodo_inicio,
                snapshot.periodo_fim,
            )
        )
        return SerieNaTela(
            restricao_id=restricao_id,
            snapshot_id=snapshot_id,
            fonte=fonte,
            agregacao=agregacao,
            pontos=[PontoDaSerie(instante=i, corte_mw=mw, minutos_cnf=m) for i, mw, m in pontos]
            if crua
            else [],
            baldes=[BaldeDaSerie(inicio=i, energia_mwh=mwh) for i, mwh in baldes],
        )


def _ocorrencias(s, restricao_id: str, snapshot_id: str, fonte: str):  # type: ignore[no-untyped-def]
    """Agrupa pela regra do motor. A regra mora num lugar só: nunca se repete em SQL."""
    pontos = _pontos(s, restricao_id, snapshot_id, fonte)
    if not pontos:
        return []
    serie = SerieDoMotor(
        restricao_id=restricao_id,
        snapshot_id=snapshot_id,
        intervalos=[Intervalo(instante=i, corte_mw=mw, minutos_cnf=m) for i, mw, m in pontos],
    )
    return agrupar(serie, PREMISSAS_PADRAO)


@rotas.get(
    "/restricoes/{restricao_id}/ocorrencias",
    tags=["restricoes"],
    operation_id="ver_ocorrencias",
)
def ver_ocorrencias(
    restricao_id: str,
    fonte: Annotated[Fonte, Query(description="Fonte de geração da série.")] = Fonte.EOLICA,
) -> OcorrenciasNaTela:
    """Episódios de corte da restrição no snapshot ativo, para auditoria.

    Restrição sem série responde lista vazia, não `404`: não ter cortado nesta fonte é um fato
    sobre a restrição, não uma restrição que não existe.
    """
    with sessao() as s:
        snapshot_id = _snapshot_ativo(s)
        ocorrencias = _ocorrencias(s, restricao_id, snapshot_id, fonte.value)
    return OcorrenciasNaTela(
        restricao_id=restricao_id,
        snapshot_id=snapshot_id,
        fonte=fonte,
        total=len(ocorrencias),
        energia_mwh=sum(o.energia_mwh for o in ocorrencias),
        aviso=AVISO_OCORRENCIAS,
        itens=sorted(
            (
                OcorrenciaNaTela(
                    inicio=o.inicio,
                    fim=o.fim,
                    intervalos=o.intervalos,
                    duracao_horas=o.duracao_horas,
                    energia_mwh=o.energia_mwh,
                    corte_medio_maximo_mw=o.corte_medio_maximo_mw,
                )
                for o in ocorrencias
            ),
            key=lambda o: o.energia_mwh,
            reverse=True,
        ),
    )


def _serie_do_motor(pedido: PedidoDeSimulacao, restricao_id: str | None = None) -> SerieDoMotor:
    """`restricao_id` sobrepõe o do pedido: ao revisar, quem manda é a simulação."""
    restricao_id = restricao_id or pedido.restricao_id
    with sessao() as s:
        snapshot_id = pedido.snapshot_id or _snapshot_ativo(s)
        equipamentos = _equipamentos(s, restricao_id, snapshot_id)
        if not equipamentos:
            raise HTTPException(
                status_code=409,
                detail="restrição sem vínculo autorizado: o casamento com o cadastro ficou "
                "duvidoso e ninguém resolveu ainda",
            )
        _confere_escolhas(pedido.configuracao, equipamentos)
        pontos = _pontos(s, restricao_id, snapshot_id, pedido.fonte.value)
        snapshot = s.get(Snapshot, snapshot_id)
        inicio = snapshot.periodo_inicio if snapshot else None
        fim = snapshot.periodo_fim if snapshot else None
    if not pontos:
        raise HTTPException(status_code=404, detail="sem série para esta restrição e fonte")
    # A janela vai declarada: a série é esparsa e contar linhas daria dois meses num ano.
    return SerieDoMotor(
        restricao_id=restricao_id,
        snapshot_id=snapshot_id,
        intervalos=[Intervalo(instante=i, corte_mw=mw, minutos_cnf=m) for i, mw, m in pontos],
        periodo_inicio=inicio,
        periodo_fim=fim,
    )


def _premissas(pedido: PedidoDeSimulacao) -> Premissas:
    """As premissas padrão, com o que o pedido altera. Só altera o que sai do padrão, porque
    alterar rebaixa o status da premissa para `proposta`.

    Fixar sempre, mesmo no padrão, marcaria "o usuário mexeu nisto" em toda simulação e apagaria
    a validação de um engenheiro no dia em que uma destas premissas for validada."""
    alteradas: dict[str, float | int | bool | str] = {}
    if not pedido.correcao_minutos:
        alteradas["correcao_minutos"] = False
    if pedido.fonte.value != PREMISSAS_PADRAO.valor("fonte_geracao"):
        alteradas["fonte_geracao"] = pedido.fonte.value
    return PREMISSAS_PADRAO.com(**alteradas) if alteradas else PREMISSAS_PADRAO


def _salva(revisao: SimulacaoRevisao, simulacao: Simulacao) -> dict[str, object]:
    return {
        "id": revisao.id,
        "simulacao_id": simulacao.id,
        "nome": simulacao.nome,
        "pergunta": simulacao.pergunta,
        "restricao_id": simulacao.restricao_id,
        "snapshot_id": revisao.snapshot_id,
        "metodo_versao": revisao.metodo_versao,
        "revisao_anterior_id": revisao.revisao_anterior_id,
        "procedencia": revisao.procedencia,
        "nota": revisao.nota,
        "criada_em": revisao.criada_em,
    }


def _janelas(s, snapshot_ids: set[str]) -> dict[str, tuple[datetime | None, datetime | None]]:  # type: ignore[no-untyped-def]
    """A janela de cada snapshot citado. Revisão velha tem janela velha, e não a do ativo."""
    if not snapshot_ids:
        return {}
    linhas = s.execute(
        select(Snapshot.id, Snapshot.periodo_inicio, Snapshot.periodo_fim).where(
            Snapshot.id.in_(snapshot_ids)
        )
    ).all()
    return {id: (inicio, fim) for id, inicio, fim in linhas}


def _cronologicas(s, simulacao_ids: list[int]) -> dict[int, list[SimulacaoRevisao]]:  # type: ignore[no-untyped-def]
    """As revisões de cada simulação, da mais velha para a mais nova."""
    por_simulacao: dict[int, list[SimulacaoRevisao]] = {}
    if not simulacao_ids:
        return por_simulacao
    consulta = (
        select(SimulacaoRevisao)
        .where(SimulacaoRevisao.simulacao_id.in_(simulacao_ids))
        .order_by(SimulacaoRevisao.id)
    )
    for revisao in s.scalars(consulta):
        por_simulacao.setdefault(revisao.simulacao_id, []).append(revisao)
    return por_simulacao


def _irmas(cronologicas: list[SimulacaoRevisao]) -> list[RevisaoIrma]:
    return [
        RevisaoIrma(
            id=revisao.id,
            posicao=posicao,
            atual=posicao == len(cronologicas),
            criada_em=revisao.criada_em,
            revisao_anterior_id=revisao.revisao_anterior_id,
            procedencia=ProcedenciaDaRevisao(revisao.procedencia),
            nota=revisao.nota,
        )
        for posicao, revisao in enumerate(cronologicas, start=1)
    ][::-1]


def _numero_do_resultado(revisao: SimulacaoRevisao, bloco: str, campo: str) -> float | None:
    dentro = (revisao.resultado or {}).get(bloco) or {}
    valor = dentro.get(campo) if isinstance(dentro, dict) else None
    return valor if isinstance(valor, int | float) and not isinstance(valor, bool) else None


@rotas.post("/simular", tags=["simulacoes"], operation_id="simular")
def simular(pedido: PedidoDeSimulacao) -> Resultado:
    """Calcula sem persistir. O resultado carrega método, snapshot, premissas e avisos."""
    return calcular(_serie_do_motor(pedido), pedido.configuracao, _premissas(pedido))


@rotas.post("/simulacoes", tags=["simulacoes"], operation_id="salvar_simulacao")
def salvar_simulacao(pedido: PedidoDeSalvamento) -> RevisaoSalva:
    """Calcula e salva como revisão. Alterar depois cria revisão nova; nada se sobrescreve.

    Com `simulacao_id`, a restrição vem da simulação, **nunca do pedido** — é dela que a
    revisão trata, e o invariante diz que uma simulação é uma restrição só. A revisão nasce de
    `revisao_base_id`, conferida como desta simulação, ou, sem ele, da mais nova, que é a que o
    usuário está vendo quando pede para alterar ([ADR 0014]).
    """
    with sessao() as s:
        if pedido.simulacao_id is not None:
            simulacao_existente = s.get(Simulacao, pedido.simulacao_id)
            if simulacao_existente is None:
                raise HTTPException(status_code=404, detail="simulação não existe")
            restricao_id = simulacao_existente.restricao_id
            anterior_id = (
                _revisao_base(s, pedido.simulacao_id, pedido.revisao_base_id)
                if pedido.revisao_base_id is not None
                else _revisao_mais_nova(s, pedido.simulacao_id)
            )
        else:
            assert pedido.restricao_id is not None  # o validador do pedido garante
            restricao_id = pedido.restricao_id
            anterior_id = None

    serie = _serie_do_motor(pedido, restricao_id)
    resultado = calcular(serie, pedido.configuracao, _premissas(pedido))
    with sessao() as s:
        if pedido.simulacao_id is not None:
            simulacao = s.get(Simulacao, pedido.simulacao_id)
        else:
            simulacao = Simulacao(
                nome=pedido.nome, pergunta=pedido.pergunta, restricao_id=restricao_id
            )
            s.add(simulacao)
            s.flush()
        assert simulacao is not None
        revisao = SimulacaoRevisao(
            simulacao_id=simulacao.id,
            revisao_anterior_id=anterior_id,
            procedencia=pedido.procedencia.value,
            nota=pedido.nota,
            snapshot_id=serie.snapshot_id,
            metodo_versao=METODO_VERSAO,
            configuracao=pedido.configuracao.model_dump(mode="json"),
            premissas_usadas={
                id: p.model_dump(mode="json") for id, p in resultado.premissas_usadas.items()
            },
            resultado=resultado.model_dump(mode="json"),
            avisos=[a.model_dump(mode="json") for a in resultado.avisos],
        )
        s.add(revisao)
        s.commit()
        return RevisaoSalva.model_validate(_salva(revisao, simulacao))


def _revisao_mais_nova(s, simulacao_id: int) -> int | None:  # type: ignore[no-untyped-def]
    """De qual revisão a nova nasce quando o pedido não diz: a mais recente da simulação, que é
    a que a tela mostra quando a pessoa pede para alterar.

    Não é mais a única origem possível. O explorador da feature 17 roda um lote de variações a
    partir da mesma revisão, e com "a mais nova" cada irmã ficaria registrada como filha da que
    terminou antes, com "o que mudou" dizendo duas mudanças onde houve uma ([ADR 0014])."""
    return s.scalars(
        select(SimulacaoRevisao.id)
        .where(SimulacaoRevisao.simulacao_id == simulacao_id)
        .order_by(SimulacaoRevisao.id.desc())
        .limit(1)
    ).first()


def _revisao_base(s, simulacao_id: int, revisao_base_id: int) -> int:  # type: ignore[no-untyped-def]
    """A revisão de partida que o pedido escolheu, conferida como desta simulação.

    De outra simulação, a origem apontaria para fora dela: a árvore atravessaria simulações, e
    "o que mudou", que só procura dentro da simulação, diria "Original" de uma revisão que não
    é. Não existir é o mesmo erro: a origem pedida não está aqui."""
    base = s.get(SimulacaoRevisao, revisao_base_id)
    if base is None or base.simulacao_id != simulacao_id:
        de_onde = "não existe" if base is None else f"é da simulação {base.simulacao_id}"
        raise HTTPException(
            status_code=422,
            detail=f"revisão de partida {revisao_base_id} {de_onde}; a revisão nasce de uma "
            f"revisão da simulação {simulacao_id}",
        )
    return base.id


def _na_lista(
    revisao: SimulacaoRevisao,
    posicao: int,
    atual: bool,
    anterior: SimulacaoRevisao | None,
    posicao_anterior: int | None,
    janela: tuple[datetime | None, datetime | None],
) -> RevisaoNaLista:
    inicio, fim = janela
    return RevisaoNaLista(
        id=revisao.id,
        posicao=posicao,
        atual=atual,
        criada_em=revisao.criada_em,
        revisao_anterior_id=revisao.revisao_anterior_id,
        procedencia=ProcedenciaDaRevisao(revisao.procedencia),
        nota=revisao.nota,
        snapshot_id=revisao.snapshot_id,
        metodo_versao=revisao.metodo_versao,
        periodo_inicio=inicio,
        periodo_fim=fim,
        vpl_reais=_numero_do_resultado(revisao, "financeiro", "vpl_reais"),
        energia_recuperada_mwh=_numero_do_resultado(revisao, "tecnico", "energia_recuperada_mwh"),
        o_que_mudou=descrever(
            revisao.configuracao or {},
            anterior.configuracao if anterior else None,
            revisao.snapshot_id,
            anterior.snapshot_id if anterior else None,
            posicao_anterior,
            revisao.premissas_usadas or {},
            anterior.premissas_usadas if anterior else None,
        ),
    )


@rotas.get("/simulacoes", tags=["simulacoes"], operation_id="listar_simulacoes")
def listar_simulacoes(
    restricao_id: str | None = Query(
        default=None, description="Só as simulações desta restrição. Sem ele, todas."
    ),
) -> list[SimulacaoNaLista]:
    """As simulações salvas, com as revisões dentro, da mais nova para a mais velha.

    Uma linha por simulação, e não por revisão: uma simulação com três revisões é um item com
    três linhas dentro. Nada se apaga."""
    with sessao() as s:
        consulta = select(Simulacao)
        if restricao_id is not None:
            consulta = consulta.where(Simulacao.restricao_id == restricao_id)
        simulacoes = list(s.scalars(consulta))
        por_simulacao = _cronologicas(s, [simulacao.id for simulacao in simulacoes])
        janelas = _janelas(
            s,
            {revisao.snapshot_id for revisoes in por_simulacao.values() for revisao in revisoes},
        )
        itens: list[tuple[int, SimulacaoNaLista]] = []
        for simulacao in simulacoes:
            cronologicas = por_simulacao.get(simulacao.id, [])
            if not cronologicas:
                continue
            posicoes = {revisao.id: posicao for posicao, revisao in enumerate(cronologicas, 1)}
            por_id = {revisao.id: revisao for revisao in cronologicas}
            mais_nova = cronologicas[-1]
            # A identidade da restrição não tem snapshot e nunca se apaga ([ADR 0009]), então
            # o texto não some mais quando o ONS reescreve ou a restrição sai do snapshot.
            restricao = s.get(Restricao, simulacao.restricao_id)
            modalidade = (mais_nova.configuracao or {}).get("modalidade")
            linhas = [
                _na_lista(
                    revisao,
                    posicoes[revisao.id],
                    revisao.id == mais_nova.id,
                    por_id.get(revisao.revisao_anterior_id or -1),
                    posicoes.get(revisao.revisao_anterior_id or -1),
                    janelas.get(revisao.snapshot_id, (None, None)),
                )
                for revisao in reversed(cronologicas)
            ]
            itens.append(
                (
                    mais_nova.id,
                    SimulacaoNaLista(
                        id=simulacao.id,
                        nome=simulacao.nome,
                        pergunta=simulacao.pergunta,
                        restricao_id=simulacao.restricao_id,
                        restricao_texto=restricao.texto if restricao else None,
                        modalidade=Modalidade(modalidade) if modalidade else None,
                        criada_em=simulacao.criada_em,
                        revisoes=linhas,
                    ),
                )
            )
        return [item for _, item in sorted(itens, key=lambda par: par[0], reverse=True)]


@rotas.get("/simulacoes/{revisao_id}", tags=["simulacoes"], operation_id="ver_simulacao")
def ver_simulacao(revisao_id: int) -> RevisaoCompleta:
    """A revisão inteira: parâmetros, premissas com status, resultado e avisos."""
    with sessao() as s:
        revisao = s.get(SimulacaoRevisao, revisao_id)
        if revisao is None:
            raise HTTPException(status_code=404, detail="revisão não existe")
        simulacao = s.get(Simulacao, revisao.simulacao_id)
        assert simulacao is not None
        cronologicas = _cronologicas(s, [simulacao.id])[simulacao.id]
        inicio, fim = _janelas(s, {revisao.snapshot_id}).get(revisao.snapshot_id, (None, None))
        resultado = Resultado.model_validate(revisao.resultado)
        if resultado.diagnosticos is None:
            resultado.diagnosticos = _diagnosticos_na_leitura(s, revisao, simulacao, resultado)
        return RevisaoCompleta.model_validate(
            _salva(revisao, simulacao)
            | {
                "periodo_inicio": inicio,
                "periodo_fim": fim,
                "configuracao": revisao.configuracao,
                "premissas_usadas": revisao.premissas_usadas,
                "resultado": resultado,
                "avisos": revisao.avisos,
                "revisoes": _irmas(cronologicas),
                "cruzamentos": cruzamentos(
                    [
                        RevisaoCoberta(
                            revisao_id=r.id,
                            posicao=posicao,
                            criada_em=r.criada_em,
                            configuracao=Configuracao.model_validate(r.configuracao),
                            resultado=Resultado.model_validate(r.resultado),
                            o_que_mudou="",
                        )
                        for posicao, r in enumerate(cronologicas, start=1)
                    ]
                ),
            }
        )


def _diagnosticos_na_leitura(s, revisao, simulacao, resultado: Resultado):  # type: ignore[no-untyped-def]
    """Revisão calculada antes da 0.9.0 não gravou diagnósticos: calcula na leitura, com a série
    do snapshot e da fonte dela. Se a série não bater com a que ela calculou, fica sem: melhor
    nada que diagnóstico de outra série."""
    fonte = ((revisao.premissas_usadas or {}).get("fonte_geracao") or {}).get("valor", "eolica")
    pontos = _pontos(s, simulacao.restricao_id, revisao.snapshot_id, fonte)
    if len(pontos) != len(resultado.tecnico.cortado_mw):
        return None
    serie = SerieDoMotor(
        restricao_id=simulacao.restricao_id,
        snapshot_id=revisao.snapshot_id,
        intervalos=[Intervalo(instante=i, corte_mw=mw, minutos_cnf=m) for i, mw, m in pontos],
    )
    configuracao = Configuracao.model_validate(revisao.configuracao)
    return diagnosticar(serie, configuracao, resultado.tecnico)
