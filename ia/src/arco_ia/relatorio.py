"""Analista e verificador do relatório da simulação. Feature 17, marco 0.

O analista escreve a prosa sobre a parte calculada, em uma chamada ao modelo. O verificador é
código puro, sem modelo: todo número da prosa tem de existir na parte calculada, nenhuma forma
de recomendação passa, e cada seção cabe no seu limite
([ADR 0012](../../../docs/adr/0012-relatorio-compila-evidencia-nao-recomenda.md)). Concordância
entre modelos não é evidência; conferência por código é.

A parte calculada chega serializada em JSON, como a API a grava: cabeçalho, trilha, derivados e
a linha de cada revisão. `ia` não importa `api`, e o verificador só precisa dos números e dos
textos que ela carrega.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator, Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field

from arco_ia.chamada import Cliente, Resposta, chamar

ParteCalculada = Mapping[str, Any]
"""A parte calculada do relatório, em JSON: `cabecalho`, `trilha`, `derivados`, `por_revisao` e
`nao_afirma`, como no contrato (`docs/features/agentes/17-relatorio-contrato.md`)."""


class Prosa(BaseModel):
    """As cinco seções que o modelo escreve. Cada uma tem limite conferido por código."""

    leitura_geral: str = Field(
        description="O que a simulação perguntou, o que se viu nas revisões e em que faixa "
        "ficaram as métricas. Até 6 frases."
    )
    o_que_variou: list[str] = Field(
        description="Uma frase por campo que variou entre as revisões, com o efeito observado "
        "na métrica. Lista vazia se nada variou."
    )
    sensibilidade: str = Field(
        description="A que o resultado se mostrou sensível entre as revisões, e a quais "
        "premissas não validadas o resultado depende. Até 4 frases."
    )
    fora_do_metodo: str = Field(
        description="Os limites do método que se aplicam, os avisos e as obras previstas. Até 4 "
        "frases."
    )
    perguntas_que_ficaram: list[str] = Field(
        description="Até 3 perguntas sobre o que a exploração não testou. Cada item termina em "
        "ponto de interrogação; nunca instrução."
    )


Secao = Literal[
    "leitura_geral", "o_que_variou", "sensibilidade", "fora_do_metodo", "perguntas_que_ficaram"
]
Motivo = Literal["sem_origem", "forma_proibida", "tamanho"]

LIMITES: dict[Secao, int] = {
    "leitura_geral": 6,
    "sensibilidade": 4,
    "fora_do_metodo": 4,
    "perguntas_que_ficaram": 3,
}
"""Frases por seção de texto; itens em `perguntas_que_ficaram`. `o_que_variou` tem um item por
campo que variou, e cada item uma frase: o limite sai da parte calculada."""

TOLERANCIA = "meia unidade da última casa escrita, com no mínimo 2 algarismos significativos"


class FalhaDeVerificacao(BaseModel):
    secao: Secao
    numero: str | None = Field(
        description="O número como apareceu, em `sem_origem`; a forma achada, em "
        "`forma_proibida`; nulo em `tamanho`."
    )
    motivo: Motivo
    trecho: str = Field(description="A frase onde a falha está.")


class Verificacao(BaseModel):
    resultado: Literal["passou", "falhou"] | None = Field(
        description="Nulo enquanto o relatório está em `gerando`."
    )
    numeros_na_prosa: int
    encontrados: int = Field(description="Números da prosa achados na parte calculada.")
    tolerancia: str = TOLERANCIA
    falhas: list[FalhaDeVerificacao] = Field(default_factory=list)
    contagens: dict[Secao, tuple[int, int]] = Field(
        default_factory=dict, description="Por seção: (usadas, limite), em frases ou itens."
    )


# Analista ----------------------------------------------------------------------------------

INSTRUCAO = """\
Você escreve a leitura de um relatório do ARCO, ferramenta que refaz os cortes de geração
renovável registrados pelo ONS com uma intervenção hipotética (bateria, adição de circuito, ou
as duas) e calcula o efeito técnico e financeiro. Uma simulação tem várias revisões; cada
revisão é uma configuração calculada. Você recebe, em JSON, a parte calculada por código:
cabeçalho da restrição, trilha das revisões, linha de cada revisão, derivados entre elas
(ordenações, diferenças, sensibilidade observada, fronteiras, o que variou e o que ficou
parado, premissas não validadas) e o que o relatório não afirma.

O relatório compila evidência e **nunca recomenda**. Ordenar por um critério nomeado é
evidência; escolher é recomendação. Nunca use "melhor", "recomenda", "recomendamos", "deve",
"deveria", "instale", "escolha", "ideal", "ótimo", "vale a pena", "sugere-se", "aconselha" nem
equivalentes. Nunca chame uma revisão de vencedora. Essas palavras barram o relatório **mesmo
negadas ou atribuídas ao leitor**: não escreva "não há vencedora", "o leitor deve" nem "deve-se
a"; escreva "o resultado depende de", "decorre de". **Não comente que o relatório não recomenda
nem escolhe**: o texto fixo em `nao_afirma` já diz isso na tela, e a frase só abre caminho para
a palavra proibida. Ordene por critério nomeado e siga.

**Números.** Todo número que você escrever tem de estar na parte calculada, com a mesma unidade.
Não calcule nada: não some, não subtraia, não divida, não faça porcentagem nem razão nova. Pode
arredondar, mantendo pelo menos dois algarismos significativos. Escreva no formato brasileiro:
milhar com ponto, decimal com vírgula (1.234,5), R$ antes do valor (R$ 600 mil, R$ 10 milhões),
unidade depois (50 MW, 200 MWh, 12 anos). Frações de 0 a 1 viram porcentagem (0,12 é 12%).
Para citar uma revisão, escreva "rev" e a posição dela (rev 3). Números que não estão na parte
calculada barram o relatório inteiro.

Seções:
- `leitura_geral`: o que a simulação perguntou, o que se viu nas revisões e em que faixa ficaram
  as métricas. Até 6 frases.
- `o_que_variou`: uma frase por campo em `derivados.variou`, com o efeito observado a partir das
  diferenças. Lista vazia se nada variou.
- `sensibilidade`: a partir de `derivados.sensibilidades` e `derivados.premissas_expostas`, a que
  o resultado se mostrou sensível entre as revisões e de quais premissas não validadas ele
  depende. Só sensibilidade observada entre revisões que existem. Até 4 frases.
- `fora_do_metodo`: os limites que se aplicam, a partir de `nao_afirma`, dos avisos da restrição
  e de `cabecalho.presente_no_snapshot`. Diga sempre que o resultado é contrafactual e que
  associação não é causalidade. Até 4 frases.
- `perguntas_que_ficaram`: até 3 perguntas sobre o que a exploração não testou, a partir de
  `derivados.ficou_parado`, respondíveis com uma revisão nova. Sempre em forma de pergunta,
  terminando em "?", nunca de instrução.

Com uma revisão só, não há comparação: diga isso na leitura geral e deixe `o_que_variou` vazio.
Frases curtas, sem jargão sem explicação, português do Brasil.
"""


def escrever_prosa(
    parte_calculada: ParteCalculada, cliente: Cliente | None = None
) -> Resposta[Prosa]:
    """Uma chamada ao modelo do papel `analista`. A prosa volta **sem conferir**: quem chama
    passa por `verificar` antes de gravar, e guarda a prosa barrada para inspeção."""
    return chamar(
        "analista",
        INSTRUCAO,
        "Parte calculada do relatório:\n" + json.dumps(parte_calculada, ensure_ascii=False),
        Prosa,
        cliente=cliente,
    )


# Verificador -------------------------------------------------------------------------------

FORMAS_PROIBIDAS = re.compile(
    r"\b("
    r"melhor(?:es)?|"
    r"recomend\w*|"
    r"dev(?:e|em|eria|eriam)(?:-se)?|"
    r"instal(?:e|em)|"
    r"escolh(?:a|am|e|em|er|ida|ido|idas|idos)|"
    r"ideal|ideais|"
    r"ótim[oa]s?|"
    r"vale a pena|"
    r"suger(?:e|imos|e-se)|"
    r"aconselh\w*|"
    r"preferível|preferíveis|"
    r"vencedor[a]?(?:es)?"
    r")\b",
    re.IGNORECASE,
)
"""As formas da ADR 0012 e equivalentes. "Deve" também barra o uso causal ("deve-se ao preço"):
o modelo é instruído a evitá-lo, e o custo de uma frase reescrita é menor que o de deixar
passar uma recomendação."""

_MULTIPLICADORES = {
    "mil": 1e3,
    "mi": 1e6,
    "milhão": 1e6,
    "milhões": 1e6,
    "bi": 1e9,
    "bilhão": 1e9,
    "bilhões": 1e9,
}

_NUMERO = re.compile(
    r"(?:(?<![\w,.])(?P<sinal_antes>[-−])\s*)?"
    r"(?P<moeda>R\$\s*)?"
    r"(?:(?<![\w,.])(?P<sinal>[-−])\s*)?"
    r"(?<![\w,.])(?P<numero>"
    r"\d{1,3}(?:\.\d{3})+(?:,\d+)?(?!\d|\.\d)"  # 1.234,5 — o formato pedido
    r"|\d+\.\d+(?!\d)"  # 1.5 — decimal com ponto, fora do formato, mas lido pelo valor
    r"|\d+(?:,\d+)?"
    r")(?!\d)"
    r"(?:\s*(?P<mult>milhões|milhão|mil|mi|bilhões|bilhão|bi)\b)?"
    r"(?:\s*(?P<unidade>%|por cento|p\.p\.|pontos percentuais|ao ano|a\.a\.|MWh|MW|MVA|kV|anos?)"
    r"(?![\w]))?",
    re.IGNORECASE,
)
"""Número no formato brasileiro, com sinal e moeda antes e multiplicador e unidade depois. Não
pega dígito colado em letra (C1, V7): é código, não número. Decimal com ponto ("1.5 MW") é lido
pelo valor e conferido como os outros; "1.500" é sempre mil e quinhentos, como em português.

O sinal só conta quando está escrito: "−20 milhões" tem de casar com valor negativo. Sem sinal,
a conferência compara o valor absoluto, porque "queda de R$ 20 milhões" diz o mesmo número por
extenso — e por isso **o verificador confere a grandeza, não o sentido**: "VPL positivo de R$ 20
milhões" sobre um VPL de −20 milhões passa. É limite declarado, não achado."""

_MILHAR = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")

Unidade = Literal["R$", "fracao", "MWh", "MW", "MVA", "kV", "anos"]


class Numero(BaseModel):
    texto: str
    valor: float = Field(description="Sempre positivo; o sinal escrito vai em `negativo`.")
    unidade: Unidade | None
    negativo: bool = False
    algarismos: int = Field(
        description="Algarismos significativos como escritos: 3 em 10,4 milhões, 1 em 1.000."
    )


def numeros(texto: str) -> list[Numero]:
    """Os números de um texto, com valor e unidade. "12%" vale 0,12 em fração, como no motor."""
    achados: list[Numero] = []
    for m in _NUMERO.finditer(texto):
        escrito = m["numero"]
        brasileiro = "," in escrito or bool(_MILHAR.fullmatch(escrito))
        # Fora do formato brasileiro só sobra inteiro ou decimal com ponto ("1.5").
        valor = float(escrito.replace(".", "").replace(",", ".") if brasileiro else escrito)
        decimal = "," in escrito or (not brasileiro and "." in escrito)
        if m["mult"]:
            valor *= _MULTIPLICADORES[m["mult"].lower()]
        unidade = _unidade(m["unidade"])
        if unidade == "fracao" and m["unidade"].lower() not in ("ao ano", "a.a."):
            # "12%" é 0,12; "0,08 ao ano" já é fração, como o motor escreve taxa.
            valor /= 100
        if m["moeda"]:
            unidade = "R$"
        achados.append(
            Numero(
                texto=m.group(0).strip(),
                valor=valor,
                unidade=unidade,
                negativo=bool(m["sinal_antes"] or m["sinal"]),
                algarismos=_algarismos(escrito, decimal),
            )
        )
    return achados


def _algarismos(escrito: str, decimal: bool) -> int:
    """Significativos do número como escrito. Zero à esquerda não conta; zero à direita de um
    inteiro também não, porque "1.000" pode ser mil redondo: é arredondamento, não precisão."""
    digitos = re.sub(r"\D", "", escrito).lstrip("0")
    if not decimal:
        digitos = digitos.rstrip("0")
    return max(len(digitos), 1)


def _unidade(escrita: str | None) -> Unidade | None:
    if not escrita:
        return None
    escrita = escrita.lower()
    if escrita in ("%", "por cento", "p.p.", "pontos percentuais", "ao ano", "a.a."):
        return "fracao"
    if escrita.startswith("ano"):
        return "anos"
    return _UNIDADES_ESCRITAS[escrita]


_UNIDADES_ESCRITAS: dict[str, Unidade] = {"mwh": "MWh", "mw": "MW", "mva": "MVA", "kv": "kV"}


_SUFIXOS: tuple[tuple[str, Unidade], ...] = (
    ("_reais_mwh", "R$"),
    ("_reais_ano", "R$"),
    ("_reais", "R$"),
    ("_mwh", "MWh"),
    ("_mw", "MW"),
    ("_mva", "MVA"),
    ("_kv", "kV"),
    ("_anos", "anos"),
    ("_aa", "fracao"),
)
"""Ordem importa: `preco_energia_reais_mwh` é R$, não MWh."""


def _unidade_da_chave(chave: str) -> Unidade | None:
    """Unidade pelo nome do campo, a convenção do contrato. Sem sufixo, qualquer unidade vale."""
    if chave in ("fracao", "fatia") or chave.startswith(("fracao_", "delta_fracao")):
        return "fracao"
    return next((u for sufixo, u in _SUFIXOS if chave.endswith(sufixo)), None)


def _unidade_declarada(unidade: str) -> Unidade | None:
    """A unidade de uma premissa, escrita por extenso ("MW/MW", "R$/MWh", "fração"): vale o que
    vem antes da barra, que é o que a prosa escreve depois do número."""
    base = unidade.split("/")[0].strip()
    if base.startswith("R$"):
        return "R$"
    if base.startswith("fração"):
        return "fracao"
    return (
        _unidade(base)
        if base.lower() in _UNIDADES_ESCRITAS or base.lower().startswith("ano")
        else None
    )


def valores(parte_calculada: ParteCalculada) -> list[tuple[float, Unidade | None]]:
    """Todo número que a parte calculada carrega: os campos numéricos, com a unidade do nome, e
    os números escritos dentro dos textos dela, lidos pela mesma regra que lê a prosa."""
    return list(_percorrer(parte_calculada, None))


_SEM_NUMERO_DE_CALCULO = re.compile(
    r"(^|_)id$|^cod_|^url$|^empate_com$|^instrucao_operacao$|_em$|^inicio$|^fim$|^periodo_"
)
"""Chaves cujos dígitos não são número de cálculo: identificadores, códigos, caminhos e datas.
Deixá-los entrar faria 2026, 9, 22 e o id de cada revisão contarem como origem de qualquer
número sem unidade da prosa. A posição da revisão (`posicao`) fica: é o que "rev 3" cita."""


def _percorrer(no: Any, chave: str | None) -> Iterator[tuple[float, Unidade | None]]:
    if isinstance(no, bool) or no is None:
        return
    if chave is not None and _SEM_NUMERO_DE_CALCULO.search(chave):
        return
    if isinstance(no, int | float):
        yield float(no), _unidade_da_chave(chave or "")
    elif isinstance(no, str):
        for n in numeros(no):
            yield -n.valor if n.negativo else n.valor, n.unidade
    elif isinstance(no, Mapping):
        declarada = no.get("unidade")
        # A nota de uma revisão é texto de quem a salvou, pessoa ou agente: número escrito nela
        # não foi calculado, e aceitá-lo como origem deixaria o modelo citar número de modelo.
        nota = str(no.get("origem_do_texto", "")).startswith("nota_")
        for k, v in no.items():
            if nota and k == "texto":
                continue
            ao_lado = _unidade_declarada(declarada) if isinstance(declarada, str) else None
            if k == "valor" and ao_lado is not None:
                # Premissa exposta: o valor vem em texto e a unidade num campo ao lado.
                for n in numeros(str(v)):
                    yield -n.valor if n.negativo else n.valor, n.unidade or ao_lado
            else:
                yield from _percorrer(v, str(k))
    elif isinstance(no, list | tuple):
        for item in no:
            yield from _percorrer(item, chave)


def casa(numero: Numero, conhecidos: list[tuple[float, Unidade | None]]) -> bool:
    """O número da prosa é um arredondamento de algum valor da parte calculada.

    O modelo pode arredondar até dois algarismos significativos; o que ele escreve além disso
    tem de estar certo. Por isso a comparação é na precisão escrita, com meia unidade da última
    casa: "R$ 10 milhões" casa com 10,4 milhões, "R$ 10,4 milhões" não casa com 10,6 milhões, e
    "R$ 648.279.851,14" só casa com esse valor. Comparar sempre a dois significativos deixaria
    passar qualquer erro de cópia depois do segundo dígito. Sinal escrito tem de bater com valor
    negativo; sem sinal escrito, vale a grandeza (ver `_NUMERO`).

    Com unidade na prosa, só casa com valor da mesma unidade: "20 anos" não casa com 20 MWh por
    MW. Sem unidade na prosa, casa com qualquer valor; é o caso de "rev 3" e de um VPL escrito
    sem o R$. Porcentagem casa também com fração guardada sem unidade — a eficiência 0,85 é
    "85%" —, mas só com valor entre 0 e 1 exclusive: "100%" não casa com a posição 1 de uma
    revisão.
    """
    x = numero.valor
    if x == 0:
        folga = 1e-9
    else:
        casa_final = math.floor(math.log10(x)) - max(numero.algarismos, 2) + 1
        folga = 0.5 * 10**casa_final * (1 + 1e-9)
    return any(
        abs(abs(v) - x) <= folga and (v < 0 or not numero.negativo or x == 0)
        for v, u in conhecidos
        if numero.unidade is None
        or numero.unidade == u
        or (numero.unidade == "fracao" and u is None and 0 < abs(v) < 1)
    )


_ABREVIACOES = re.compile(r"\b(p\.p\.|a\.a\.|ex\.|aprox\.|etc\.)", re.IGNORECASE)
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+")


def frases(texto: str) -> list[str]:
    """Frases de um texto, cortadas em ponto final, exclamação ou interrogação seguidos de
    espaço. Ponto de milhar (1.000) não corta, porque não vem seguido de espaço."""
    protegido = _ABREVIACOES.sub(lambda m: m[0].replace(".", "\x00"), texto.strip())
    return [f.replace("\x00", ".").strip() for f in _FIM_DE_FRASE.split(protegido) if f.strip()]


def verificar(prosa: Prosa, parte_calculada: ParteCalculada) -> Verificacao:
    """Confere a prosa contra a parte calculada. Uma falha qualquer barra o relatório."""
    conhecidos = valores(parte_calculada)
    campos_variados = len(parte_calculada.get("derivados", {}).get("variou", []))
    falhas: list[FalhaDeVerificacao] = []
    contagens: dict[Secao, tuple[int, int]] = {}
    total = encontrados = 0

    for secao, itens in _secoes(prosa):
        sentencas = [(item, f) for item in itens for f in frases(item)]
        for _, frase in sentencas:
            for n in numeros(frase):
                total += 1
                if casa(n, conhecidos):
                    encontrados += 1
                else:
                    falhas.append(_falha(secao, "sem_origem", frase, n.texto))
            for proibida in FORMAS_PROIBIDAS.finditer(frase):
                falhas.append(_falha(secao, "forma_proibida", frase, proibida[0]))

        if secao == "o_que_variou":
            limite = campos_variados
            contagens[secao] = (len(itens), limite)
            if len(itens) > limite:
                falhas.append(_falha(secao, "tamanho", itens[limite], None))
            falhas += [
                _falha(secao, "tamanho", item, None) for item in itens if len(frases(item)) > 1
            ]
        elif secao == "perguntas_que_ficaram":
            limite = LIMITES[secao]
            contagens[secao] = (len(itens), limite)
            if len(itens) > limite:
                falhas.append(_falha(secao, "tamanho", itens[limite], None))
            falhas += [
                _falha(secao, "forma_proibida", item, None)
                for item in itens
                if not item.strip().endswith("?")
            ]
        else:
            limite = LIMITES[secao]
            contagens[secao] = (len(sentencas), limite)
            if len(sentencas) > limite:
                falhas.append(_falha(secao, "tamanho", sentencas[limite][1], None))

    return Verificacao(
        resultado="falhou" if falhas else "passou",
        numeros_na_prosa=total,
        encontrados=encontrados,
        falhas=falhas,
        contagens=contagens,
    )


def _secoes(prosa: Prosa) -> Iterator[tuple[Secao, list[str]]]:
    yield "leitura_geral", [prosa.leitura_geral]
    yield "o_que_variou", prosa.o_que_variou
    yield "sensibilidade", [prosa.sensibilidade]
    yield "fora_do_metodo", [prosa.fora_do_metodo]
    yield "perguntas_que_ficaram", prosa.perguntas_que_ficaram


def _falha(secao: Secao, motivo: Motivo, trecho: str, numero: str | None) -> FalhaDeVerificacao:
    return FalhaDeVerificacao(secao=secao, numero=numero, motivo=motivo, trecho=trecho)
