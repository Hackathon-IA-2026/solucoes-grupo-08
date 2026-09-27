"""Texto da restrição: normalização e extração determinística do equipamento.

Não existe chave entre o texto e o cadastro. `dsc_restricao` é texto livre do operador, e o
arquivo de corte não traz `cod_equipamento`. O que existe é forma: o operador escreve sempre
`LT <tensão> KV <SE A> / <SE B> – C<n>(<código>)`, e o `<código>` é o mesmo que o cadastro
guarda em `nom_linhadetransmissao` como `C <código>`. É isso que o casamento usa.

Duas armadilhas que custaram medição errada:

- **Normalizar antes de usar como chave.** O texto da maior restrição do escopo aparece em
  duas formas que diferem por um espaço no fim, 108 e 109 caracteres. Agrupar pelo texto cru
  parte 3.320 GWh em 2.699 e 620.
- **O travessão é `–` (U+2013), não hífen**, mas nem sempre: há texto com hífen.

O que o regex não reconhecer sai marcado, nunca adivinhado. O resíduo é da feature 08.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

MONITORADO = "monitorado"
CONTINGENCIADO = "contingenciado"
PAPEL_EQUIPAMENTO = (MONITORADO, CONTINGENCIADO)

# Quanta evidência o casamento contra o cadastro reuniu. Mora aqui, e não em `preparar`, porque
# a `api` decide a entrada do vínculo por este campo (ADR 0008) e não deve importar DuckDB por
# causa de quatro strings.
CASADO = "casado"
PROVAVEL = "provavel"
AMBIGUO = "ambiguo"
SEM_CANDIDATO = "sem_candidato"
SITUACAO_VINCULO = (CASADO, PROVAVEL, AMBIGUO, SEM_CANDIDATO)

_ESPACO = re.compile(r"\s+")
# A âncora aceita as duas formas em que o ONS abre a citação de uma linha: pela tensão,
# `LT 230 KV ...`, e pelo código operativo, `LT 04F1 ...`, onde `04` é a classe de tensão e
# `F1` é o circuito. Medido no cadastro de 2026-09-15: `04F1` **não** é `cod_equipamento` — a
# linha é `CEAQR-2FTZ-1`, e `F1` é o `codigo_circuito`. Por isso o código entra como circuito e
# a tensão fica vazia: quem sabe a tensão é o cadastro, e é lá que `completar` a busca. Mapear
# a classe `04` para 230 kV seria premissa sem fonte.
_ANCORA = re.compile(
    r"\b(?:LTS?|LINHAS?)\s+(?:(?P<kv>\d{2,4})\s*KV\b|(?P<codigo>\d{2}(?P<circuito>[A-Z]\d))\b)"
)
_TRAVESSAO = r"[‐-―\-]"
_CIRCUITO = r"C\s*\d+\s*\(\s*[A-Z0-9]{1,4}\s*\)"
_PAR = re.compile(
    r"(?P<de>[A-Z0-9][A-Z0-9.\- ]*?)\s*/\s*(?P<para>[A-Z0-9][A-Z0-9.\- ]*?)\s*"
    rf"{_TRAVESSAO}\s*(?P<circuitos>{_CIRCUITO}(?:\s*(?:E|OU|,)\s*{_CIRCUITO})*)"
)
_UM_CIRCUITO = re.compile(r"C\s*(?P<ordem>\d+)\s*\(\s*(?P<codigo>[A-Z0-9]{1,4})\s*\)")
# Par sem o sufixo `– C1(XX)`. Sem ele não há o que marque o fim do segundo terminal, então o
# fim vem de uma palavra que só aparece depois do par: `PARA CONTINGÊNCIA`, `PREVENINDO A
# PERDA`, `QUANDO DA PERDA`, a pontuação, o travessão do código de Instrução de Operação, ou o
# fim do trecho. Sem isso `ITABIRA 5 PARA CONTINGENCIA DUPLA DAS` viraria nome de subestação.
_FIM_DO_PAR = (
    r"(?=\s*(?:[,.;]|$)"
    r"|\s+(?:PARA|PREVENINDO|QUANDO|CONFORME|E\b|OU\b)"
    r"|\s*[‐-―\-]\s*(?:IO|CONFORME)"
    r"|\s*\()"
)
_PAR_SEM_CIRCUITO = re.compile(
    r"(?P<de>[A-Z0-9][A-Z0-9. ]*?)\s*/\s*(?P<para>[A-Z0-9][A-Z0-9. ]*?)" + _FIM_DO_PAR
)
_JUNCAO_OU = re.compile(r"\)\s*OU\s*C", re.IGNORECASE)
# "PARA CONTINGÊNCIA DA", "PREVENINDO A PERDA DA" e "QUANDO DA PERDA DUPLA DAS" abrem a lista
# de contingenciadas. A terceira forma passava batido e marcava a linha como monitorada.
_MARCA_CONTINGENCIA = re.compile(r"CONTING|PERDA")
# "… C1(V2), AÇU III / … E AÇU III / …": a conjunção entre pares gruda no nome da primeira
# subestação, porque "E" e "OU" também são letras maiúsculas.
_CONJUNCAO_COLADA = re.compile(r"^(?:E|OU)\s+(?=\S)")


@dataclass(frozen=True)
class EquipamentoCitado:
    """Um equipamento nomeado dentro do texto de uma restrição."""

    tensao_kv: int | None
    """Vazia quando o texto abre pelo código operativo, `LT 04F1 ...`: ali a tensão está na
    classe `04`, e mapeá-la para kV seria premissa sem fonte. Quem sabe é o cadastro."""
    de: str
    para: str
    ordem_circuito: int | None
    """Vazia quando o texto não traz o sufixo `– C1(XX)`."""
    codigo_circuito: str | None
    """Vazio quando o texto não nomeia o circuito. `casar` então usa só tensão e par."""
    papel: str
    alternativo: bool = False
    de_exibicao: str = ""
    """O terminal como o texto escreve, com acento. `de` é a forma comparável, sem acento."""
    para_exibicao: str = ""

    @property
    def par(self) -> frozenset[str]:
        """O par de subestações, sem ordem: o texto e o cadastro invertem os terminais."""
        return frozenset({self.de, self.para})


def normalizar(texto: str) -> str:
    """Espaço colapsado e pontas limpas. É a chave da restrição, nunca o texto cru."""
    return _ESPACO.sub(" ", texto).strip()


def sem_acento(texto: str) -> str:
    """Maiúsculas sem acento. O cadastro do ONS escreve ACU, o texto escreve AÇU."""
    decomposto = unicodedata.normalize("NFD", texto.upper())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def chave_subestacao(nome: str) -> str:
    """Nome comparável dos dois lados: sem acento, maiúsculo, espaço colapsado."""
    return normalizar(sem_acento(nome))


_LIGACOES = frozenset({"DO", "DA", "DE", "DOS", "DAS", "E"})
_ROMANOS = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7"}


def tokens(nome: str) -> frozenset[str]:
    """Tokens significativos de um nome de subestação, para comparar texto e cadastro.

    O cadastro abrevia e o texto escreve por extenso: "MORRO DO CHAPÉU II" vira "MORRO
    CHAPEU II", "CEARÁ MIRIM II" vira "CEARA MIRIM 2", "PAULO AFONSO" vira "P.AFONSO III".
    Tira preposições, troca algarismo romano por arábico e quebra a abreviação com ponto.

    O hífen quebra junto porque o cadastro cola a tensão no nome: "JAGUARA-345" é a mesma
    subestação que o texto chama de "JAGUARA", e sem quebrar não sobrava token em comum — eram
    23,3 GWh sem candidato.
    """
    bruto = chave_subestacao(nome).replace(".", " ").replace("-", " ")
    return frozenset(
        _ROMANOS.get(palavra, palavra)
        for palavra in bruto.split()
        if palavra and palavra not in _LIGACOES
    )


LINHA = "linha"
TRANSFORMACAO = "transformacao"
FLUXO = "fluxo"
SISTEMICA = "sistemica"
INDETERMINADO = "indeterminado"
ESCOPO = (LINHA, TRANSFORMACAO, FLUXO, SISTEMICA, INDETERMINADO)
"""O que a inequação vigia. Só `linha` é ingerida (docs/invariantes.md, Abrangência)."""

# O sujeito da inequação é o que vem logo depois do verbo. "CONTROLE DE CARREGAMENTO DA LT ..."
# vigia uma linha; "CONTROLE DE CARREGAMENTO DA TRANSFORMAÇÃO ..." vigia um transformador,
# ainda que cite LTs depois, como contingência. É essa posição que decide, não a presença da
# palavra no texto.
_SUJEITO = re.compile(
    r"(?:CONTROLE\s+DE\s+CARREGAMENTO|LIMITACAO\s+DA\s+TRANSMISSAO|DESENERGIZACAO)"
    r"\s+(?:D[AO]S?|N[AO]S?)\s+(?P<sujeito>.{0,40})",
)
# Nem todo texto traz verbo: "Controle de inequação: LT 500 KV JAGUARUANA II / PACATUBA – C1(L1)"
# nomeia o equipamento direto depois dos dois pontos. Aí o sujeito é o que vem ali.
_SUJEITO_SEM_VERBO = re.compile(r"^(?:CONTROLE|LIMITACAO|LIMITE)[^:]*:\s*(?P<sujeito>.{0,40})")
_E_LINHA = re.compile(r"^(?:LTS?|LINHAS?)\b")
_E_TRANSFORMACAO = re.compile(r"^(?:TRANSFORMACAO|TRANSFORMADOR(?:ES)?)\b")
# `TR9`, `TR-10`: notação do ONS para transformador, que aparece em inequação escrita como
# fórmula, sem verbo nenhum — "F(TR9 TRI) + 0,51 F(TR10 TRI) - 0,45 SEP < 350 MW".
_TRANSFORMADOR_EM_FORMULA = re.compile(r"\bTR\s*-?\s*\d+\b")
# O ONS marca a sistêmica no próprio texto, e o invariante manda deixá-la fora.
_SISTEMICA = re.compile(r"\(\s*SISTEMICO\s*\)")
_FLUXO = re.compile(r"\b(?:LIMITACAO\s+DO\s+FLUXO|CONTROLE\s+DO\s+FLUXO|LIMITE\s+DE)\b")


def escopo(texto: str) -> str:
    """O que esta inequação vigia, para decidir se entra no produto.

    Os [invariantes](../../../docs/invariantes.md) dizem que só restrição de **linha de
    transmissão** é ingerida. A classificação olha o **sujeito** da inequação — o que vem logo
    depois de "CONTROLE DE CARREGAMENTO DA" ou "LIMITAÇÃO DA TRANSMISSÃO NA" — e não a presença
    da palavra no texto: `CONTROLE DE CARREGAMENTO DA TRANSFORMAÇÃO 500/230 KV DA SE SÃO JOÃO DO
    PIAUÍ PARA CONTINGÊNCIA DA LT 500 KV ...` cita uma LT e vigia um transformador.

    `indeterminado` é resposta legítima: o texto não segue nenhuma forma conhecida. Ele não
    entra no produto, mas sai listado pelo preparo, porque linha de verdade que a regra não
    reconhece some calada — e é isso que o teste dourado e o aviso do preparo guardam.
    """
    limpo = sem_acento(normalizar(texto))
    if _SISTEMICA.search(limpo):
        return SISTEMICA
    for regra in (_SUJEITO, _SUJEITO_SEM_VERBO):
        achado = regra.search(limpo)
        if achado is None:
            continue
        sujeito = achado.group("sujeito").strip()
        if _E_LINHA.match(sujeito):
            return LINHA
        if _E_TRANSFORMACAO.match(sujeito):
            return TRANSFORMACAO
    if _FLUXO.search(limpo):
        return FLUXO
    if _TRANSFORMADOR_EM_FORMULA.search(limpo):
        return TRANSFORMACAO
    return INDETERMINADO


def extrair(texto: str) -> list[EquipamentoCitado]:
    """Equipamentos citados no texto, em ordem de aparição. Lista vazia quando não reconhece.

    Um texto pode citar um equipamento, três, dois circuitos alternativos ligados por `OU`,
    ou um monitorado seguido de um contingenciado depois de `PARA CONTINGÊNCIA DA` ou
    `PREVENINDO A PERDA DA`.
    """
    # Duas versões do mesmo texto, posição a posição: `limpo` é onde os regex casam, `exibicao`
    # é de onde sai o nome que aparece na tela. `sem_acento` e `upper` não mudam a extensão em
    # português, mas se mudarem a exibição cai na forma sem acento em vez de cortar no lugar
    # errado.
    exibicao = normalizar(texto)
    limpo = sem_acento(exibicao.upper())
    if len(limpo) != len(exibicao):
        exibicao = limpo

    ancoras = list(_ANCORA.finditer(limpo))
    if not ancoras:
        return []

    citados: list[EquipamentoCitado] = []
    # O papel começa monitorado e **gruda** em contingenciado: a primeira citação é de quem a
    # restrição trata, e depois da marca de contingência tudo que vem é contingenciado.
    papel = MONITORADO
    for indice, ancora in enumerate(ancoras):
        inicio = ancora.end()
        fim = ancoras[indice + 1].start() if indice + 1 < len(ancoras) else len(limpo)
        trecho = limpo[inicio:fim]
        # Para a primeira âncora, o que vem antes é o começo do texto: "DA TRANSFORMAÇÃO ...
        # PARA CONTINGÊNCIA DUPLA DAS LT ..." abre direto em contingenciada, e olhar `""`
        # fazia dela a monitorada.
        anterior = (
            limpo[ancoras[indice - 1].end() : ancora.start()] if indice else limpo[: ancora.start()]
        )
        # O papel **gruda**: aberta a lista de contingenciadas, tudo que vem depois é
        # contingenciado. "DA LT A PARA CONTINGÊNCIA DUPLA DAS LT B E LT C" cita a marca só
        # antes de B, e C ficava como monitorada — uma linha que se supõe perder entrando como
        # candidata a receber circuito novo.
        if _MARCA_CONTINGENCIA.search(anterior):
            papel = CONTINGENCIADO
        kv = ancora.group("kv")
        tensao_kv = int(kv) if kv else None
        # `LT 04F1 ...`: o circuito vem na própria âncora, não num sufixo `– C1(XX)`.
        circuito_da_ancora = ancora.group("circuito")

        achou_par = False
        for par in _PAR.finditer(trecho):
            achou_par = True
            circuitos = par.group("circuitos")
            alternativo = bool(_JUNCAO_OU.search(circuitos))
            for ordem, circuito in enumerate(_UM_CIRCUITO.finditer(circuitos)):
                citados.append(
                    EquipamentoCitado(
                        tensao_kv=tensao_kv,
                        de=_CONJUNCAO_COLADA.sub("", normalizar(par.group("de"))),
                        para=normalizar(par.group("para")),
                        de_exibicao=_CONJUNCAO_COLADA.sub(
                            "",
                            normalizar(exibicao[inicio + par.start("de") : inicio + par.end("de")]),
                        ),
                        para_exibicao=normalizar(
                            exibicao[inicio + par.start("para") : inicio + par.end("para")]
                        ),
                        ordem_circuito=int(circuito.group("ordem")),
                        codigo_circuito=circuito.group("codigo"),
                        papel=papel,
                        alternativo=alternativo and ordem > 0,
                    )
                )

        # Sem o sufixo de circuito o par não casa em `_PAR`, e o texto seguiria sem equipamento
        # nenhum: era o que acontecia com `LT 230 KV ITABIRA 4 / ITABIRA 5`, 114,5 GWh, e com
        # `LT 04F1 Aquiraz II / Fortaleza`. O que o texto não diz fica vazio.
        if achou_par:
            continue
        par = _PAR_SEM_CIRCUITO.search(trecho)
        if par is None:
            continue
        citados.append(
            EquipamentoCitado(
                tensao_kv=tensao_kv,
                de=_CONJUNCAO_COLADA.sub("", normalizar(par.group("de"))),
                para=normalizar(par.group("para")),
                de_exibicao=_CONJUNCAO_COLADA.sub(
                    "", normalizar(exibicao[inicio + par.start("de") : inicio + par.end("de")])
                ),
                para_exibicao=normalizar(
                    exibicao[inicio + par.start("para") : inicio + par.end("para")]
                ),
                ordem_circuito=None,
                codigo_circuito=circuito_da_ancora,
                papel=papel,
                alternativo=False,
            )
        )
    return citados


_IO = re.compile(r"\bIO-[A-Z0-9]+(?:[.\-][A-Z0-9]+)*")
_ROMANOS_DE_EXIBICAO = frozenset({"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"})


def instrucao_de_operacao(texto: str) -> str | None:
    """O código da Instrução de Operação citado no texto, como `IO-ON.NE.5NE`.

    Aparece em 55 dos 64 textos do escopo, em formato regular. `None` quando não aparece: nunca
    se inventa código.
    """
    achado = _IO.search(sem_acento(texto.upper()))
    return achado.group(0) if achado else None


def _caixa_de_exibicao(nome: str) -> str:
    """Caixa mista para ler numa lista de 64 linhas, sem estragar romano nem abreviação.

    O ONS escreve tudo em caixa alta. `III` continua `III`, `P.AFONSO` continua `P.AFONSO`,
    `MOSSORÓ` vira `Mossoró` e a preposição no meio do nome fica minúscula, como em
    `São João do Piauí`.
    """
    saida = []
    for posicao, palavra in enumerate(nome.split()):
        if palavra in _ROMANOS_DE_EXIBICAO or not palavra.isalpha():
            saida.append(palavra)
        elif posicao and palavra in _LIGACOES:
            saida.append(palavra.lower())
        else:
            saida.append(palavra.capitalize())
    return " ".join(saida)


def _rotulo(citado: EquipamentoCitado) -> str:
    """`LT 230 kV Açu III / Mossoró II · C1`.

    Forma fixa: sempre os mesmos campos, sempre na mesma ordem, inclusive o circuito quando a
    restrição cita um só. Forma constante vale mais que nome curto — numa lista de 64, o olho
    acha a diferença por ela estar sempre na mesma posição.

    Campo que o texto não traz **some em vez de aparecer vazio**, e a ordem dos que sobram não
    muda. É o que o texto disse, e o que o cadastro completou em `completar`: nunca se inventa
    tensão nem circuito para manter a forma cheia.
    """
    de = _caixa_de_exibicao(citado.de_exibicao or citado.de)
    para = _caixa_de_exibicao(citado.para_exibicao or citado.para)
    tensao = f"{citado.tensao_kv} kV " if citado.tensao_kv is not None else ""
    circuito = f" · C{citado.ordem_circuito}" if citado.ordem_circuito is not None else ""
    return f"LT {tensao}{de} / {para}{circuito}"


def nome_curto(citados: Sequence[EquipamentoCitado]) -> str | None:
    """O nome da restrição: o equipamento **monitorado**, que é de quem a restrição trata.

    A contingência fica de fora de propósito — ela dobra o tamanho e descreve o cenário, não a
    restrição. Sai em campo próprio, e é ela que distingue duas restrições sobre a mesma linha.

    `None` quando o texto não cita monitorado nenhum: aí a tela cai no texto do ONS.
    """
    monitorados = [c for c in citados if c.papel == MONITORADO]
    return _rotulo(monitorados[0]) if monitorados else None


def contingencia(citados: Sequence[EquipamentoCitado]) -> str | None:
    """O equipamento que se supõe perder, no mesmo formato. `None` quando o texto não cita um."""
    contingenciados = [c for c in citados if c.papel == CONTINGENCIADO]
    return _rotulo(contingenciados[0]) if contingenciados else None
