"""Premissas: tudo que o cálculo usa e que pode ser questionado.

Cada premissa tem id, valor, unidade, faixa, fonte e status. O motor lê premissas da entrada,
nunca de constante escondida.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class StatusPremissa(StrEnum):
    NAO_VERIFICADA = "nao_verificada"
    PROPOSTA = "proposta"
    VALIDADA = "validada"


class Premissa(BaseModel):
    id: str
    descricao: str
    valor: float | int | bool | str
    unidade: str | None = None
    faixa: tuple[float, float] | None = None
    fonte: str
    status: StatusPremissa = StatusPremissa.NAO_VERIFICADA
    validado_por: str | None = None
    validado_em: date | None = None

    @model_validator(mode="after")
    def _validada_tem_autor(self) -> Premissa:
        if self.status is StatusPremissa.VALIDADA and not (self.validado_por and self.validado_em):
            raise ValueError(f"premissa {self.id}: validada exige validado_por e validado_em")
        return self


class Premissas(BaseModel):
    """Conjunto de premissas usado por uma execução. Imutável na prática: `com()` devolve cópia."""

    itens: dict[str, Premissa] = Field(default_factory=dict)

    def obter(self, id: str) -> Premissa:
        try:
            return self.itens[id]
        except KeyError as erro:
            raise KeyError(f"premissa desconhecida: {id}") from erro

    def valor(self, id: str) -> float | int | bool | str:
        return self.obter(id).valor

    def com(self, **valores: float | int | bool | str) -> Premissas:
        """Cópia com valores alterados pelo usuário. Alterar rebaixa o status para proposta."""
        novos = dict(self.itens)
        for id, valor in valores.items():
            atual = self.obter(id)
            novos[id] = atual.model_copy(
                update={
                    "valor": valor,
                    "status": StatusPremissa.PROPOSTA,
                    "validado_por": None,
                    "validado_em": None,
                }
            )
        return Premissas(itens=novos)


METODO = "premissa de método"

PREMISSAS_PADRAO = Premissas(
    itens={
        p.id: p
        for p in [
            Premissa(
                id="sensibilidade_equipamento",
                descricao="MW de corte evitado por MW de limite adicional no equipamento, "
                "em cada meia hora: evitado = min(corte, ganho x sensibilidade). Adotado 1 para 1 "
                "em 2026-09-17, com a limitação declarada na tela: a sensibilidade real depende "
                "da rede e não foi estimada.",
                valor=1.0,
                unidade="MW/MW",
                fonte=METODO,
            ),
            Premissa(
                id="fonte_geracao",
                descricao="Qual fonte alimenta a série da restrição: eolica, solar ou ambas. "
                "Os dois arquivos do ONS são sempre ingeridos; a flag só filtra. Com ambas, a "
                "série é a soma na mesma meia hora e a regra de ocorrência roda sobre a soma. "
                "O filtro acontece em quem monta a série, antes do motor: aqui ela é carimbada "
                "para a revisão ser reproduzível, não lida para calcular.",
                valor="eolica",
                fonte=METODO,
                status=StatusPremissa.PROPOSTA,
            ),
            Premissa(
                id="despacho_bateria",
                descricao="Estratégia de despacho: carrega enquanto há corte residual, até a "
                "potência e o espaço restante; descarrega até a potência quando o corte cessa. "
                "A devolução usa a mesma linha e não é limitada pelo limite da restrição: "
                "premissa declarada, não omissão.",
                valor="gulosa",
                fonte=METODO,
                status=StatusPremissa.PROPOSTA,
            ),
            Premissa(
                id="bateria_carrega_so_do_corte",
                descricao="A bateria só absorve energia que seria cortada; não compra da rede.",
                valor=True,
                fonte=METODO,
                status=StatusPremissa.PROPOSTA,
            ),
            Premissa(
                id="ordem_combinada",
                descricao="Na modalidade combinada, o equipamento reduz o corte primeiro e a "
                "bateria atua sobre o residual.",
                valor="equipamento_depois_bateria",
                fonte=METODO,
                status=StatusPremissa.PROPOSTA,
            ),
            Premissa(
                id="regra_ocorrencia_intervalos_tolerados",
                descricao="Meias horas sem corte que podem separar dois intervalos da mesma "
                "ocorrência. Zero: intervalos estritamente consecutivos.",
                valor=0,
                unidade="intervalos",
                fonte=METODO,
                status=StatusPremissa.PROPOSTA,
            ),
            Premissa(
                id="correcao_minutos",
                descricao="Ligada: a potência cortada dentro da meia hora é a média x 30 / "
                "num_minutos_cnf, supondo corte constante nesses minutos. O campo é o da razão "
                "específica, nunca o total, porque a apuração titula a meia hora por prevalência. "
                "A correção muda a potência que cada alavanca captura, nunca a energia da meia "
                "hora.",
                valor=True,
                fonte=METODO,
                status=StatusPremissa.PROPOSTA,
            ),
            Premissa(
                id="preco_energia",
                descricao="Valor da energia recuperada, fixo e editável na simulação. Não é série "
                "temporal. Partida: CMO médio ponderado do corte local por confiabilidade em 2025.",
                valor=216.0,
                unidade="R$/MWh",
                fonte="CMO semi-horário do ONS, dado aberto; média ponderada de 2025 na classe "
                "corte local por confiabilidade",
                status=StatusPremissa.PROPOSTA,
            ),
            Premissa(
                id="agregacao_minutos",
                descricao="Como os minutos de restrição por usina viram um valor por meia hora "
                "da restrição, que soma vários conjuntos: média ponderada pela potência "
                "cortada. Alternativas descartadas: o máximo, que é otimista porque reduz a "
                "correção, e o mínimo, que é pessimista. Usada no preparo, em dados/.",
                valor="ponderada_pela_potencia",
                fonte=METODO,
            ),
            Premissa(
                id="bateria_duracao_horas",
                descricao="Duração da bateria, capacidade sobre potência, do custo por kWh: a "
                "EPE dá o custo de bateria de 4 horas. A faixa de 2 a 6 horas é decisão de "
                "método, sem fonte: fora dela o investimento montado sai com aviso, e dentro "
                "dela o custo por kWh de 4 horas é usado sem ressalva, embora parte do custo "
                "real seja por kW. É também a faixa em que o explorador pode variar a duração.",
                valor=4,
                unidade="h",
                faixa=(2, 6),
                fonte="EPE, Caderno de Parâmetros de Custos do PDE 2035, bateria de 4 horas; a "
                "faixa de 2 a 6 horas é decisão de método de 2026-09-22 (regras do explorador, "
                "seção 7)",
            ),
            Premissa(
                id="teto_alavanca_capacidade",
                descricao="Teto de `potencia_mw` da bateria e de `ganho_limite_mw` do circuito, "
                "em vezes a capacidade de longa duração do cadastro, lida como MW a fator de "
                "potência 1: ao salvar, a da linha de maior capacidade da restrição; na faixa do "
                "explorador, o ganho usa a da linha que recebe o circuito. Potência acima da "
                "capacidade de cadastro não é caso que o método represente. É múltiplo declarado "
                "do cadastro, não limite físico nem limite com fonte: nesses corredores o que "
                "corta costuma ser tensão, não capacidade.",
                valor=1.0,
                unidade="vezes a capacidade de longa duração",
                fonte=METODO,
            ),
            Premissa(
                id="anualizacao",
                descricao="Período diferente de 12 meses é escalado por 12 / meses na conta anual. "
                "Dormente: o período está travado em 12 meses completos.",
                valor="proporcional",
                fonte=METODO,
            ),
        ]
    }
)
