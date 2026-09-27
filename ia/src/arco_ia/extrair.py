"""Extração de equipamento dos textos de restrição que a regra determinística não lê.

A camada determinística da feature 02 resolve 29 das 64 restrições do snapshot de 2026-09-21 —
92,9% da energia cortada — e continua decidindo esses casos: é grátis, roda em menos de um
segundo, é testável caso a caso e não varia. O modelo entra onde ela falhou, e **vendo mais do
que ela vê**: o texto inteiro, e não o trecho que o regex ancora.

O que autoriza o vínculo não é o modelo: é a conferência contra o cadastro, feita em `dados`
pelo mesmo `casar()` que confere o regex. Aqui se garante só o que dá para garantir sem o
cadastro — que todo nome devolvido está no texto de entrada.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from arco_ia.chamada import Cliente, chamar

PAPEIS = ("monitorado", "contingenciado")


class EquipamentoExtraido(BaseModel):
    """Uma linha de transmissão citada no texto, na forma que `dados` sabe conferir."""

    tensao_kv: int = Field(description="Tensão nominal em kV, como 230 ou 500.")
    de: str = Field(description="Subestação de um terminal, como escrita no texto.")
    para: str = Field(description="Subestação do outro terminal, como escrita no texto.")
    ordem_circuito: int = Field(description="O número em C1, C2: 1, 2...")
    codigo_circuito: str = Field(description="O código entre parênteses em C1(V7): V7.")
    papel: Literal["monitorado", "contingenciado"] = Field(
        description="`monitorado` é a linha cujo carregamento se controla. `contingenciado` é a "
        "que se supõe perder, citada depois de PARA CONTINGÊNCIA DA ou PREVENINDO A PERDA DA."
    )


class Extracao(BaseModel):
    """O que o modelo leu de um texto, mais o rastro de quem leu."""

    equipamentos: list[EquipamentoExtraido] = Field(default_factory=list)
    modelo: str = ""
    versao_prompt: str = ""


class NomeForaDoTexto(ValueError):
    """O modelo devolveu uma subestação que não está no texto de entrada. Erro, não achado."""


INSTRUCAO = """\
Você lê textos de restrição de operação do ONS, o operador do sistema elétrico brasileiro, e
extrai as linhas de transmissão citadas.

O formato usual é `LT <tensão> KV <SUBESTAÇÃO A> / <SUBESTAÇÃO B> – C<n>(<código>)`, mas o texto
é livre e varia: pode ter quebra de linha no meio, travessão ou hífen, caixa alta ou mista, e
citar mais de uma linha.

Regras:
- Devolva as subestações **exatamente como estão escritas no texto**, sem corrigir, completar,
  abreviar nem expandir. Se o texto escreve AÇU III, devolva AÇU III.
- `papel` é `contingenciado` para a linha citada depois de PARA CONTINGÊNCIA DA, PREVENINDO A
  PERDA DA ou equivalente. As demais são `monitorado`.
- Quando o texto citar dois circuitos da mesma linha, devolva um item por circuito.
- Se o texto não citar linha de transmissão nenhuma, devolva a lista vazia. **Não invente.**
"""


def extrair(texto_restricao: str, cliente: Cliente | None = None) -> Extracao:
    """Lê o texto e devolve os equipamentos citados, tipados e conferidos contra o texto.

    Nome fora do texto sobe como `NomeForaDoTexto` sem nova chamada: é conferência de conteúdo,
    e reenviar seria pedir ao modelo que insistisse no erro.
    """
    resposta = chamar(
        "extrator",
        INSTRUCAO,
        f"Texto da restrição:\n{texto_restricao}",
        Extracao,
        conferir=lambda lido: conferir_contra_o_texto(lido, texto_restricao),
        cliente=cliente,
    )
    return Extracao(
        equipamentos=resposta.saida.equipamentos,
        modelo=resposta.registro.modelo,
        versao_prompt=resposta.registro.versao_prompt,
    )


def conferir_contra_o_texto(lido: Extracao, texto_restricao: str) -> None:
    """Todo nome devolvido tem de estar no texto de entrada.

    É a única conferência que cabe aqui: sem o cadastro não dá para saber se o equipamento
    existe. Nome que o modelo escreveu e não está no texto é alucinação, e alucinação é erro.
    """
    alvo = _comparavel(texto_restricao)
    for equipamento in lido.equipamentos:
        for nome in (equipamento.de, equipamento.para):
            if _comparavel(nome) not in alvo:
                raise NomeForaDoTexto(f"{nome!r} não aparece no texto da restrição")


def _comparavel(texto: str) -> str:
    """Caixa alta e espaço colapsado. Acento fica: o modelo foi mandado copiar do texto."""
    return " ".join(texto.upper().split())
