"""Tipos do motor: o contrato entre motor, dados e api.

Unidades no nome: _mw, _mwh, _reais, _horas, _anos. Percentuais são frações de 0 a 1.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from arco_motor.premissas import Premissa

PASSO_HORAS = 0.5
"""Duração de um intervalo da série, em horas. O dado do ONS é semi-horário."""


class Intervalo(BaseModel):
    """Uma meia hora da série de uma restrição."""

    instante: datetime
    corte_mw: float = Field(ge=0, description="Potência média cortada no intervalo, em MW.")
    minutos_cnf: int | None = Field(
        default=None,
        ge=0,
        le=30,
        description="Minutos com restrição de razão CNF dentro da meia hora. É o campo da "
        "razão específica (num_minutos_cnf), nunca o total: a apuração titula a meia hora por "
        "prevalência. Vazio significa sem correção de minutos.",
    )

    @property
    def corte_mwh(self) -> float:
        return self.corte_mw * PASSO_HORAS


class SerieRestricao(BaseModel):
    """Série de corte de uma restrição, para um snapshot, em ordem cronológica.

    **A série é esparsa, e isso é de propósito.** O ONS só registra a meia hora em que houve
    corte: um ano com 17.520 meias horas costuma trazer algumas milhares. Materializar o
    resto como zero custaria cem vezes o volume para dizer "não aconteceu nada".

    O que se perde ao ser esparsa está declarado em vez de contado:

    - **o tamanho da janela** vem de `periodo_inicio` e `periodo_fim`, não do número de
      linhas, senão um ano com poucos cortes pareceria dois meses;
    - **o tempo parado entre dois cortes** vem da diferença entre os carimbos de duas linhas
      vizinhas, que é o que a bateria usa para descarregar.
    """

    restricao_id: str
    snapshot_id: str
    intervalos: list[Intervalo]
    submercado: str | None = None
    periodo_inicio: datetime | None = None
    periodo_fim: datetime | None = None

    @model_validator(mode="after")
    def _cronologica(self) -> SerieRestricao:
        for anterior, atual in zip(self.intervalos, self.intervalos[1:], strict=False):
            if atual.instante <= anterior.instante:
                raise ValueError(f"série fora de ordem em {atual.instante.isoformat()}")
        return self

    @model_validator(mode="after")
    def _periodo_cobre_a_serie(self) -> SerieRestricao:
        if not self.intervalos:
            return self
        if self.periodo_inicio and self.periodo_inicio > self.intervalos[0].instante:
            raise ValueError("periodo_inicio depois do primeiro corte")
        if self.periodo_fim and self.periodo_fim < self.intervalos[-1].instante:
            raise ValueError("periodo_fim antes do último corte")
        return self

    @property
    def energia_cortada_mwh(self) -> float:
        return sum(intervalo.corte_mwh for intervalo in self.intervalos)

    @property
    def horas_no_periodo(self) -> float:
        """Duração da janela analisada. Declarada quando se sabe; senão, o que a série cobre.

        Nunca é o número de linhas vezes meia hora: a série é esparsa."""
        if not self.intervalos:
            return 0.0
        inicio = self.periodo_inicio or self.intervalos[0].instante
        fim = self.periodo_fim or self.intervalos[-1].instante
        return (fim - inicio).total_seconds() / 3600.0 + PASSO_HORAS


class Ocorrencia(BaseModel):
    """Um episódio de corte: intervalos com corte, seguidos no tempo.

    `intervalos` conta as meias horas com corte; `duracao_horas` mede o relógio do início ao
    fim. Os dois só coincidem quando a premissa de tolerância é zero, que é o padrão: com
    tolerância acima de zero a folga tolerada fica dentro do episódio e não é intervalo.
    """

    inicio: datetime = Field(description="Carimbo do primeiro intervalo com corte.")
    fim: datetime = Field(description="Fecho da última meia hora com corte, não o carimbo dela.")
    intervalos: int = Field(gt=0, description="Meias horas com corte dentro da ocorrência.")
    energia_mwh: float = Field(ge=0, description="Energia cortada no episódio.")
    corte_medio_maximo_mw: float = Field(
        ge=0,
        description="Maior potência **média** de meia hora do episódio. Não é o pico: a série do "
        "ONS é média da meia hora, e o pico sai dela por `fator_pico`, que divide pela fração da "
        "meia hora com corte (`minutos_cnf`) quando a premissa `correcao_minutos` está ligada. "
        "Cem MW médios com 10 minutos de corte são 300 MW de pico, e é contra o pico que a "
        "alavanca é dimensionada.",
    )

    @property
    def duracao_horas(self) -> float:
        return (self.fim - self.inicio).total_seconds() / 3600.0


class Modalidade(StrEnum):
    BATERIA = "bateria"
    EQUIPAMENTO = "equipamento"
    COMBINADA = "combinada"


class TipoIntervencao(StrEnum):
    """Única intervenção de equipamento desde 2026-09-17: uma linha nova entre as mesmas
    subestações, ou por outro caminho. Substituição, ampliação do existente e aumento de
    limite saíram com a decisão de não aumentar capacidade térmica de linha.
    """

    ADICAO_CIRCUITO = "adicao_circuito"


class Cenario(StrEnum):
    CONSERVADOR = "conservador"
    REFERENCIA = "referencia"
    OTIMISTA = "otimista"


class ConfigBateria(BaseModel):
    """Bateria da simulação.

    **Regra que o JSON Schema não expressa, e o validador aplica:**
    `soc_min <= soc_inicial <= soc_max`. `soc_inicial` vazio assume `soc_min`, então omiti-lo é
    sempre seguro; informá-lo fora da faixa é `422`.
    """

    potencia_mw: float = Field(gt=0, description="Potência de carga e descarga.")
    capacidade_mwh: float = Field(gt=0, description="Energia armazenável, em MWh.")
    subestacao: str = Field(
        min_length=1,
        description="Subestação de conexão, pelo nome do cadastro do ONS, que é a chave que o "
        "produto tem. Precisa ser terminal de equipamento validado da restrição simulada. A "
        "bateria se prende à restrição e a uma subestação, nunca a um equipamento; serve ao "
        "custo de conexão, que hoje está dentro de `capex_reais`.",
    )
    soc_inicial: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Estado de carga no início da janela, fração de 0 a 1. **Vazio assume "
        "`soc_min`**, e não zero: a bateria começa no piso que a operação permite, que é a "
        "hipótese conservadora — zero seria carga proibida sempre que `soc_min` for maior que "
        "zero, e o pedido seria recusado sem que quem o montou tivesse escolhido nada.",
    )
    soc_min: float = Field(default=0.0, ge=0, le=1, description="Estado de carga mínimo, fração.")
    soc_max: float = Field(default=1.0, ge=0, le=1, description="Estado de carga máximo, fração.")
    eficiencia_ida_volta: float = Field(
        default=0.85, gt=0, le=1, description="Fração da energia absorvida que volta para a rede."
    )
    disponibilidade: float = Field(
        default=1.0, gt=0, le=1, description="Fração de 0 a 1 que multiplica a potência."
    )
    degradacao_por_ciclo: float = Field(
        default=0.0, ge=0, lt=1, description="Fração da capacidade perdida a cada ciclo acumulado."
    )
    degradacao_por_ano: float = Field(
        default=0.0,
        ge=0,
        lt=1,
        description="Fração por ano. Não entra na réplica do histórico; acima de zero gera aviso.",
    )
    vida_util_anos: int = Field(default=15, gt=0, description="Vida útil da bateria, em anos.")

    @property
    def carga_inicial(self) -> float:
        """A carga com que a janela começa. É por aqui que o cálculo lê, nunca por
        `soc_inicial` cru, que pode estar vazio."""
        return self.soc_min if self.soc_inicial is None else self.soc_inicial

    @model_validator(mode="after")
    def _limites_de_carga(self) -> ConfigBateria:
        if self.soc_min > self.soc_max:
            raise ValueError(
                f"exige soc_min <= soc_max; veio soc_min={self.soc_min}, soc_max={self.soc_max}"
            )
        if not self.soc_min <= self.carga_inicial <= self.soc_max:
            raise ValueError(
                f"exige soc_min <= soc_inicial <= soc_max; veio soc_min={self.soc_min}, "
                f"soc_inicial={self.soc_inicial}, soc_max={self.soc_max}"
            )
        return self


class ConfigEquipamento(BaseModel):
    tipo: TipoIntervencao = Field(description="Hoje só `adicao_circuito`.")
    cod_equipamento: str = Field(
        min_length=1,
        description="A linha da restrição que recebe o circuito novo, pelo código do cadastro do "
        "ONS. A adição de circuito acompanha um equipamento escolhido, e é por este código que a "
        "revisão salva diz qual foi. A capacidade atual da linha não se repete aqui: sai do "
        "cadastro pela chave `(cod_equipamento, snapshot_id)`, que a revisão grava.",
    )
    capacidade_depois_mva: float | None = Field(
        default=None,
        gt=0,
        description="Contexto de tela. Não entra no cálculo, não é conferida contra o cadastro e "
        "não tem relação verificada com `ganho_limite_mw`: MVA e MW só se convertem a fator de "
        "potência 1, e não há premissa que o registre. Quem parametriza a alavanca é o ganho.",
    )
    ganho_limite_mw: float = Field(
        ge=0, description="Acréscimo efetivo no limite operativo. Premissa visível, editável."
    )
    disponibilidade: float = Field(
        default=1.0, gt=0, le=1, description="Fração de 0 a 1 que multiplica o ganho de limite."
    )
    vida_util_anos: int = Field(default=25, gt=0, description="Vida útil do circuito, em anos.")


class Reposicao(BaseModel):
    ano: int = Field(ge=1, description="Ano do fluxo de caixa em que a reposição acontece.")
    valor_reais: float = Field(ge=0, description="Valor da reposição, em reais.")


class ConfigFinanceira(BaseModel):
    cenario: Cenario = Field(
        description="Cenário de partida. Só preenche valores iniciais, todos editáveis."
    )
    taxa_desconto_aa: float = Field(ge=0, lt=1, description="Fração ao ano.")
    horizonte_anos: int = Field(gt=0, description="Anos do fluxo de caixa.")
    capex_reais: float = Field(ge=0, description="Investimento inicial, em reais.")
    opex_fixo_reais_ano: float = Field(
        default=0.0, ge=0, description="Custo fixo de operação, em reais por ano."
    )
    opex_variavel_reais_mwh: float = Field(
        default=0.0, ge=0, description="Custo variável de operação, em reais por MWh recuperado."
    )
    reposicoes: list[Reposicao] = Field(
        default_factory=list, description="Reposições de equipamento ao longo do horizonte."
    )
    valor_residual_reais: float = Field(
        default=0.0, ge=0, description="Valor residual, em reais, somado ao último ano."
    )
    preco_energia_reais_mwh: float | None = Field(
        default=None,
        ge=0,
        description="Preço fixo em reais por MWh, editável na simulação. Não é série "
        "temporal. Vazio usa a premissa preco_energia.",
    )
    receitas_adicionais_reais_ano: float = Field(
        default=0.0, ge=0, description="Receitas além da energia recuperada, em reais por ano."
    )


class Configuracao(BaseModel):
    """O que a simulação faz, e com que números.

    **Regras que o JSON Schema não expressa, e o validador aplica**, todas entre `modalidade` e
    os dois blocos de configuração:

    | `modalidade` | `bateria` | `equipamento` |
    |---|---|---|
    | `bateria` | obrigatória | **proibido** |
    | `equipamento` | **proibida** | obrigatório |
    | `combinada` | obrigatória | obrigatório |

    Mandar o bloco que a modalidade não aceita é `422`, não campo ignorado: configuração que o
    cálculo não usaria ficaria salva na revisão sugerindo que usou.
    """

    modalidade: Modalidade = Field(
        description="`bateria`, `equipamento` (na tela, adição de circuito) ou `combinada`."
    )
    bateria: ConfigBateria | None = Field(
        default=None,
        description="Obrigatória em `bateria` e `combinada`; proibida em `equipamento`.",
    )
    equipamento: ConfigEquipamento | None = Field(
        default=None,
        description="Obrigatório em `equipamento` e `combinada`; proibido em `bateria`.",
    )
    financeira: ConfigFinanceira = Field(
        description="Cenário de partida, taxa de desconto, horizonte, investimento e custos. "
        "Obrigatória em qualquer modalidade: o resultado econômico não é opcional."
    )

    @model_validator(mode="after")
    def _coerente_com_modalidade(self) -> Configuracao:
        precisa_bateria = self.modalidade in (Modalidade.BATERIA, Modalidade.COMBINADA)
        precisa_equipamento = self.modalidade in (Modalidade.EQUIPAMENTO, Modalidade.COMBINADA)
        if precisa_bateria and self.bateria is None:
            raise ValueError(f"modalidade {self.modalidade} exige bateria")
        if precisa_equipamento and self.equipamento is None:
            raise ValueError(f"modalidade {self.modalidade} exige equipamento")
        if not precisa_bateria and self.bateria is not None:
            raise ValueError(f"modalidade {self.modalidade} não aceita bateria")
        if not precisa_equipamento and self.equipamento is not None:
            raise ValueError(f"modalidade {self.modalidade} não aceita equipamento")
        return self


class ResultadoTecnico(BaseModel):
    """Séries alinhadas aos intervalos da entrada, mais os totais."""

    cortado_mw: list[float]
    evitado_equipamento_mw: list[float]
    absorvido_bateria_mw: list[float]
    devolvido_bateria_mw: list[float]
    residual_mw: list[float]
    soc_mwh: list[float]
    energia_cortada_mwh: float
    energia_evitada_equipamento_mwh: float
    energia_absorvida_bateria_mwh: float
    energia_devolvida_bateria_mwh: float
    energia_recuperada_mwh: float
    fracao_recuperada: float = Field(ge=0, le=1)


class FluxoAnual(BaseModel):
    ano: int
    beneficio_bruto_reais: float
    receitas_adicionais_reais: float
    opex_reais: float
    reposicoes_reais: float
    fluxo_liquido_reais: float
    fluxo_descontado_reais: float
    acumulado_reais: float
    acumulado_descontado_reais: float


class ResultadoFinanceiro(BaseModel):
    vpl_reais: float
    tir_aa: float | None
    payback_simples_anos: float | None
    payback_descontado_anos: float | None
    custo_por_mwh_reais: float | None
    beneficio_bruto_reais: float
    beneficio_liquido_reais: float
    fluxos: list[FluxoAnual]


class Aviso(BaseModel):
    codigo: str
    mensagem: str
    premissa_id: str | None = None


class SaturacaoDaBateria(BaseModel):
    """Se falta capacidade ou falta tempo: o que o explorador lê para escolher a próxima
    alavanca (regras do explorador, seção 4)."""

    meias_horas_com_corte: int = Field(
        description="Meias horas em que chegou corte à bateria, depois do equipamento."
    )
    meias_horas_cheia: int = Field(
        description="Dessas, em quantas a bateria terminou cheia e ainda sobrou corte: o que se "
        "perdeu ali é falta de capacidade, não de potência."
    )
    fracao_cheia: float | None = Field(
        description="`meias_horas_cheia` sobre `meias_horas_com_corte`, de 0 a 1. `null` sem "
        "corte que chegasse à bateria."
    )
    episodios: int = Field(
        description="Episódios de corte que chegaram à bateria: meias horas seguidas, sem folga "
        "entre os carimbos."
    )
    episodios_comecaram_vazia: int = Field(
        description="Episódios em que a bateria começou vazia, no piso de carga."
    )
    episodios_comecaram_com_carga: int = Field(
        description="Episódios em que ela começou acima do piso: com carga do corte anterior, "
        "que é falta de tempo para descarregar entre um corte e o seguinte, ou, no primeiro "
        "episódio, com a carga inicial da configuração."
    )


class CorteResidual(BaseModel):
    energia_mwh: float = Field(
        description="Corte que sobrou depois da intervenção: cortado menos recuperado."
    )
    por_hora_do_dia_mwh: list[float] = Field(
        description="A mesma energia pela hora do carimbo da meia hora, de 0 a 23. Soma "
        "`energia_mwh`."
    )


class Diagnosticos(BaseModel):
    """Leitura do resultado para decidir a próxima variação. Cálculo do motor, nunca do modelo."""

    metodo_versao: str = Field(
        description="A versão do método que calculou estes diagnósticos. Pode ser mais nova que "
        "a do resultado: revisão gravada antes da 0.9.0 os ganha calculados na leitura."
    )
    saturacao: SaturacaoDaBateria | None = Field(description="`null` sem bateria.")
    corte_residual: CorteResidual


class Resultado(BaseModel):
    metodo_versao: str
    snapshot_id: str
    restricao_id: str
    tecnico: ResultadoTecnico
    financeiro: ResultadoFinanceiro
    premissas_usadas: dict[str, Premissa]
    avisos: list[Aviso] = Field(default_factory=list)
    diagnosticos: Diagnosticos | None = Field(
        default=None,
        description="Desde a versão 0.9.0 do método. `null` em resultado calculado antes.",
    )
