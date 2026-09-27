"""Os cartões do chat. Cada função recebe o que a API devolveu e monta a `PrefabApp`.

Nenhum número nasce aqui, como em `resumos.py`: o cartão mostra o que a API devolveu, ou o
que a pessoa escolheu, formatado. A energia do ranking e a contagem da exploração vêm prontas;
o cartão só as desenha.
"""

from __future__ import annotations

from typing import Any

from prefab_ui.actions import SetState
from prefab_ui.actions.mcp import CallTool, SendMessage
from prefab_ui.actions.navigation import OpenLink
from prefab_ui.actions.timing import SetInterval
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge,
    Button,
    Column,
    Div,
    Elif,
    Else,
    If,
    Input,
    Label,
    Progress,
    Row,
    Svg,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
    Text,
)
from prefab_ui.rx import RESULT, Rx

from arco_agentes import resumos
from arco_agentes.interfaces.tema import TEMA, cabecalho, indicador

CENARIOS = {"conservador": "Conservador", "referencia": "Referência", "otimista": "Otimista"}


NO_CARTAO_DA_LISTA = (
    "\n\nO cartão mostra esta lista, e a pessoa escolhe a restrição nele, pelo botão Simular; a "
    "escolha volta na conversa. Não repita a lista e não pergunte ainda a restrição nem a "
    "modalidade: diga em uma frase para escolher no cartão, e espere."
)
"""O recado ao modelo no fim do texto de cada ferramenta com cartão: o que a pessoa faz no
cartão, e que ele espera. O texto continua completo, para cliente que não desenha o cartão."""

NO_CARTAO_DA_NOVA_SIMULACAO = (
    "\n\nO cartão mostra estes campos, sem edição, e avisa que, ao confirmar, o agente do ARCO "
    "explora a simulação. Nada foi salvo. Não repita os valores: pergunte agora se a pessoa "
    "confirma, com a pergunta de escolha do próprio cliente quando houver, com duas opções, "
    "Confirmar e Alterar valor. Com Confirmar, chame criar_simulacao com estes mesmos valores: "
    "ela cria a simulação e dispara a exploração. Com Alterar valor, pergunte o que mudar e "
    "chame conferir_simulacao de novo."
)

NO_CARTAO_DA_EXPLORACAO = (
    "\n\nO cartão só avisa que o agente do ARCO vai explorar a simulação; o resumo acima é para "
    "você, e não para repetir. Pergunte agora, com a pergunta de escolha do próprio cliente "
    "quando houver, Confirmar ou Cancelar. Só com Confirmar chame explorar_variacoes de novo, "
    "com confirmado=true e os mesmos parâmetros."
)


def no_cartao_de_andamento(tarefa_id: int) -> str:
    """O recado ao modelo depois do disparo: acompanhar dentro do turno, porque o cartão não o
    acorda quando a exploração termina."""
    return (
        "\n\nO cartão mostra o andamento e se atualiza sozinho; não repita a contagem. Acompanhe "
        f"agora até o fim: chame ver_andamento com tarefa_id={tarefa_id} e aguardar=true, e de "
        "novo enquanto a exploração estiver em andamento, sem escrever nada entre as chamadas. "
        "Quando terminar, leia o relatório com ver_relatorio e conte em poucas linhas o que ele "
        "encontrou."
    )


def _app(view: Any, titulo: str, estado: dict[str, Any] | None = None) -> PrefabApp:
    return PrefabApp(title=titulo, view=view, state=estado or {}, theme=TEMA)


# 1. Lista de restrições -------------------------------------------------------------------


def lista_de_restricoes(dados: dict[str, Any]) -> PrefabApp:
    """Nome curto, energia cortada e fatia; o botão manda a escolha de volta à conversa, e o
    modelo segue para a simulação daquela restrição."""
    resumo = dados["resumo"]
    with Column(gap=4, css_class="arco-cartao") as view:
        cabecalho(
            "Restrições com mais corte",
            f"{resumo['restricoes']} no ranking de {resumo['fonte']}, snapshot "
            f"{resumo['snapshot_id']}",
        )
        with Table():
            with TableHeader(), TableRow():
                TableHead("Restrição")
                TableHead("Energia cortada")
                TableHead("Fatia")
                TableHead("")
            with TableBody():
                for item in dados["itens"]:
                    with TableRow():
                        TableCell(f"{item['posicao']}. {item['nome']}", css_class="arco-destaque")
                        TableCell(
                            f"{resumos.numero_br(item['energia_mwh'], 0)} MWh",
                            css_class="arco-destaque",
                        )
                        TableCell(resumos.porcentagem(item["fatia_do_total"]))
                        with TableCell():
                            Button(
                                "Simular",
                                variant="outline",
                                size="sm",
                                on_click=SendMessage(
                                    f"Quero simular a restrição {item['nome']} "
                                    f"(id {item['restricao_id']})."
                                ),
                            )
        Text(
            "A fatia é da energia cortada no ranking inteiro. Escolher uma restrição segue na "
            "conversa para montar a simulação.",
            css_class="arco-nota",
        )
    return _app(view, "Restrições do ARCO")


# 2. Conferência da simulação nova ---------------------------------------------------------

MODALIDADES = {
    "bateria": "Bateria",
    "equipamento": "Circuito novo",
    "combinada": "Combinada (circuito e bateria)",
}


def cartao_da_nova_simulacao(
    escolhas: dict[str, Any], restricao: dict[str, Any], teto: int
) -> PrefabApp:
    """Só os campos que criam a simulação, sem edição, para a pessoa conferir antes de ela
    existir: nome, restrição, modalidade, cenário e a alavanca; e o aviso de que, ao confirmar,
    o agente explora. Nenhum valor montado nem calculado, e nenhum botão: quem confirma ou pede
    para alterar é a pergunta que o modelo abre logo depois do cartão."""
    modalidade = escolhas["modalidade"]
    with Column(gap=4, css_class="arco-cartao") as view:
        cabecalho("Nova simulação, para confirmar", "Nada foi salvo ainda.")
        _campo("Nome da simulação", escolhas["nome"])
        _campo("Restrição", resumos.nome_da_restricao(restricao))
        with Row(gap=3):
            _campo("Modalidade", MODALIDADES[modalidade])
            _campo("Cenário", CENARIOS[escolhas["cenario"]])
        if modalidade in ("equipamento", "combinada"):
            with Row(gap=3):
                _campo(
                    "Linha que recebe o circuito",
                    resumos.linha(restricao, escolhas["cod_equipamento"]),
                )
                _campo("Ganho de limite (MW)", resumos.numero_br(escolhas["ganho_limite_mw"]))
        if modalidade in ("bateria", "combinada"):
            with Row(gap=3):
                _campo("Potência (MW)", resumos.numero_br(escolhas["potencia_mw"]))
                _campo("Capacidade (MWh)", resumos.numero_br(escolhas["capacidade_mwh"]))
                _campo("Subestação de conexão", escolhas["subestacao"])
        _aviso_dos_agentes(teto, "desta simulação")
    return _app(view, "Nova simulação do ARCO")


def _campo(rotulo: str, valor: str) -> Column:
    """Rótulo e valor no desenho dos campos do painel, sem edição."""
    with Column(gap=1) as campo:
        Label(rotulo)
        Input(value=valor, read_only=True)
    return campo


# 3. O aviso dos agentes, o disparo e o andamento ------------------------------------------

PASSOS = (
    "Parte da simulação, mantendo preço da energia, taxa de desconto e cenário.",
    "Escolhe um lote de variações da alavanca, dentro da faixa permitida.",
    "As variações rodam juntas, e cada uma vira uma revisão.",
    "Lê os resultados e decide a próxima rodada; no fim, sai o relatório.",
)
"""Como a exploração funciona, em quatro linhas: as regras em `17-regras-do-explorador.md`."""

_VARIACOES_1 = (28, 54, 80, 106, 132)
_VARIACOES_2 = (41, 67, 93, 119)
DESENHO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 160" role="img" '
    'aria-label="O agente parte da simulação, solta lotes de variações que rodam juntas, lê os '
    'resultados e decide a próxima rodada; no fim, sai o relatório.">'
    '<line class="arco-fio" x1="68" y1="80" x2="128" y2="80"/>'
    + "".join(
        f'<path class="arco-fio" d="M182 80 C 230 80, 240 {y}, 282 {y}"/>' for y in _VARIACOES_1
    )
    + "".join(
        f'<path class="arco-fio" d="M182 80 C 250 80, 290 {y}, 342 {y}"/>' for y in _VARIACOES_2
    )
    + '<line class="arco-fio" x1="358" y1="80" x2="460" y2="80"/>'
    '<path class="arco-volta" d="M296 20 C 262 2, 196 4, 164 50"/>'
    '<text x="306" y="16">lê os resultados</text>'
    '<circle class="arco-no" cx="48" cy="80" r="20"/>'
    '<text x="48" y="122" text-anchor="middle">Simulação</text>'
    '<g class="arco-pulso">'
    '<rect class="arco-agente" x="130" y="54" width="52" height="52" rx="14"/>'
    '<circle class="arco-agente-olho" cx="147" cy="76" r="4.5"/>'
    '<circle class="arco-agente-olho" cx="165" cy="76" r="4.5"/>'
    '<rect class="arco-agente-olho" x="147" y="88" width="18" height="4" rx="2"/></g>'
    '<text x="156" y="122" text-anchor="middle">Agente</text>'
    + "".join(
        f'<circle class="arco-variacao" cx="290" cy="{y}" r="8" '
        f'style="animation-delay:{i * 0.15:.2f}s"/>'
        for i, y in enumerate(_VARIACOES_1)
    )
    + "".join(
        f'<circle class="arco-variacao" cx="350" cy="{y}" r="8" '
        f'style="animation-delay:{2.4 + i * 0.15:.2f}s"/>'
        for i, y in enumerate(_VARIACOES_2)
    )
    + '<text x="290" y="156" text-anchor="middle">rodada 1</text>'
    '<text x="350" y="156" text-anchor="middle">rodada 2</text>'
    '<rect class="arco-relatorio" x="462" y="58" width="36" height="44" rx="4"/>'
    '<line class="arco-fio" x1="470" y1="72" x2="490" y2="72"/>'
    '<line class="arco-fio" x1="470" y1="82" x2="490" y2="82"/>'
    '<line class="arco-fio" x1="470" y1="92" x2="484" y2="92"/>'
    '<text x="480" y="122" text-anchor="middle">Relatório</text>'
    "</svg>"
)
"""O que os passos dizem, animado: a animação para em quem desliga movimento no sistema."""


def _aviso_dos_agentes(teto: int, alvo: str) -> Column:
    """O que acontece ao confirmar, sem os números da faixa e das condições fixas: esses são os
    mesmos de sempre, gravados na exploração, e não se mostram."""
    with Column(gap=3, css_class="arco-agentes") as aviso:
        Text(
            f"Ao confirmar, o agente do ARCO vai testar até {teto} variações {alvo}, em rodadas.",
            css_class="arco-agentes-titulo",
        )
        Svg(content=DESENHO, css_class="arco-desenho")
        with Column(gap=1):
            for numero, passo in enumerate(PASSOS, start=1):
                Text(f"{numero}. {passo}", css_class="arco-passo")
    return aviso


def cartao_de_exploracao(simulacao_id: int, teto: int) -> PrefabApp:
    """Explorar de novo uma simulação que já existe: só o aviso dos agentes. Quem confirma é a
    pergunta que o modelo abre logo depois do cartão."""
    with Column(gap=4, css_class="arco-cartao") as view:
        cabecalho(f"Explorar a simulação {simulacao_id}", "Nada foi disparado ainda.")
        _aviso_dos_agentes(teto, f"da simulação {simulacao_id}")
    return _app(view, "Explorar variações")


def cartao_de_andamento(tarefa: dict[str, Any], link: str) -> PrefabApp:
    """A contagem da exploração, que se atualiza sozinha a cada meio segundo por
    `ver_andamento` enquanto ela está em andamento, e o link Ver processamento para o painel."""
    em_andamento = Rx("tarefa.estado") == "em_andamento"
    with Column(
        gap=4,
        css_class="arco-cartao",
        on_mount=SetInterval(
            500,
            while_=em_andamento,
            on_tick=CallTool(
                "ver_andamento",
                arguments={"tarefa_id": tarefa["id"]},
                on_success=SetState("tarefa", RESULT),
            ),
        ),
    ) as view:
        cabecalho(f"Exploração {tarefa['id']}", tarefa.get("pedido"))
        with Row(gap=6, align="center"):
            indicador("Revisões prontas", "{{ tarefa.contagem.prontas }}")
            with If(Rx("tarefa.estado") == "em_andamento"):
                Badge("em andamento")
            with Elif(Rx("tarefa.estado") == "concluida"):
                Badge("concluída", variant="success")
            with Else():
                Badge("falhou", variant="destructive")
        # Quantas variações haverá, só o agente sabe, e ele costuma parar antes do limite: uma
        # porcentagem enquanto roda voltaria para trás a cada rodada nova. A barra só anima
        # enquanto trabalha, e enche quando termina.
        with If(em_andamento), Div(css_class="arco-barra-rodando"):
            Div(css_class="arco-barra-rodando-faixa")
        with Else():
            Progress(value=100, max=100.0)
        Text(
            "Trabalhando: {{ tarefa.contagem.trabalhando }} · recusadas: "
            "{{ tarefa.contagem.recusadas }} · rodadas: {{ tarefa.contagem.rodadas }}"
        )
        Text("Limite de {{ tarefa.teto }} variações.", css_class="arco-nota")
        with If("{{ tarefa.motivo }}"):
            Text("Terminou: {{ tarefa.motivo }}", css_class="arco-nota")
        Button("Ver processamento", variant="outline", on_click=OpenLink(link))
    return _app(view, "Andamento da exploração", {"tarefa": tarefa})
