"""O que cada ferramenta devolve: o JSON da API resumido e o texto equivalente.

**Nenhum número nasce aqui.** Os números são os da API, só formatados — milhar com ponto,
fração como porcentagem. Contar, comparar e decidir o que é melhor não é papel desta camada.

Resumir não é enfeite: a revisão inteira traz a série de cada meia hora do ano, milhares de
números por lista, e isso no contexto do modelo não informa nada e custa caro. A consulta
devolve totais, diagnósticos e configuração; a série fica na API, para a tela.
"""

from __future__ import annotations

from typing import Any

from arco_motor.relatorio import numero_br


def reais(valor: float | None) -> str:
    return "sem valor" if valor is None else f"R$ {numero_br(valor, 0)}"


def porcentagem(fracao: float | None) -> str:
    return "sem valor" if fracao is None else f"{numero_br(fracao * 100, 1)} %"


def anos(valor: float | None, vazio: str = "não ocorre no horizonte") -> str:
    return vazio if valor is None else f"{numero_br(valor, 1)} anos"


def alavanca(configuracao: dict[str, Any]) -> str:
    """O que se instalou, em uma linha, como o relatório escreve."""
    partes: list[str] = []
    equipamento = configuracao.get("equipamento")
    bateria = configuracao.get("bateria")
    if equipamento:
        partes.append(
            f"circuito novo em {equipamento['cod_equipamento']}, ganho de "
            f"{numero_br(equipamento['ganho_limite_mw'])} MW"
        )
    if bateria:
        partes.append(
            f"bateria de {numero_br(bateria['potencia_mw'])} MW e "
            f"{numero_br(bateria['capacidade_mwh'])} MWh em {bateria['subestacao']}"
        )
    financeira = configuracao.get("financeira") or {}
    instalado = " + ".join(partes) or configuracao.get("modalidade")
    cenario = str(financeira.get("cenario"))
    return f"{instalado}, cenário {CENARIOS.get(cenario, cenario)}"


CENARIOS = {"conservador": "conservador", "referencia": "de referência", "otimista": "otimista"}


# Restrições ---------------------------------------------------------------------------------


def restricoes(lista: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    resumo = lista["resumo"]
    itens = [
        {
            "restricao_id": item["id"],
            "posicao": item["posicao"],
            "nome": item.get("nome_curto") or item["texto"],
            "energia_mwh": item["energia_mwh"],
            "fatia_do_total": item["fatia_do_total"],
            "equipamentos": item["equipamentos"],
            "subestacoes": item["subestacoes"],
        }
        for item in lista["itens"]
    ]
    linhas = [
        f"{i['posicao']}. {i['nome']} (id {i['restricao_id']}): "
        f"{numero_br(i['energia_mwh'], 0)} MWh cortados, "
        f"{porcentagem(i['fatia_do_total'])} do total"
        for i in itens
    ]
    texto = (
        f"{resumo['restricoes']} restrições no ranking de {resumo['fonte']}, snapshot "
        f"{resumo['snapshot_id']}, {numero_br(resumo['energia_mwh'], 0)} MWh ao todo. "
        f"As {len(itens)} primeiras:\n" + "\n".join(linhas)
    )
    return texto, {"resumo": resumo, "itens": itens}


def restricao(detalhe: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    equipamentos = [
        {
            k: e.get(k)
            for k in (
                "cod_equipamento",
                "papel",
                "nome",
                "tensao_kv",
                "subestacao_de",
                "subestacao_para",
                "comprimento_km",
                "capacidade_longa_mva",
            )
        }
        for e in detalhe["equipamentos"]
    ]
    dados = {
        k: detalhe.get(k)
        for k in (
            "id",
            "nome_curto",
            "texto",
            "contingencia",
            "instrucao_operacao",
            "fonte",
            "energia_mwh",
            "fatia_do_total",
            "subestacoes",
            "presente_no_snapshot",
            "snapshot_id",
        )
    } | {"equipamentos": equipamentos, "avisos": detalhe.get("avisos", [])}
    linhas = [
        f"- {e['cod_equipamento']} ({e['papel']}), {e.get('tensao_kv')} kV, "
        f"{e.get('subestacao_de')} / {e.get('subestacao_para')}"
        + (" — não recebe circuito novo" if e["papel"] == "contingenciado" else "")
        for e in equipamentos
    ]
    texto = (
        f"{detalhe.get('nome_curto') or detalhe['texto']} (id {detalhe['id']}): "
        f"{numero_br(detalhe['energia_mwh'], 0)} MWh cortados em {detalhe['fonte']}, "
        f"{porcentagem(detalhe['fatia_do_total'])} do ranking. Subestações onde a bateria pode "
        f"se conectar: {', '.join(detalhe['subestacoes']) or 'nenhuma'}. Linhas:\n"
        + "\n".join(linhas)
    )
    return texto, dados


# Simulações e revisões ----------------------------------------------------------------------


def simulacoes(lista: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    dados = [
        {
            "simulacao_id": s["id"],
            "nome": s["nome"],
            "pergunta": s.get("pergunta"),
            "restricao_id": s["restricao_id"],
            "modalidade": s.get("modalidade"),
            "revisoes": [
                {
                    "revisao_id": r["id"],
                    "posicao": r["posicao"],
                    "procedencia": r.get("procedencia"),
                    "revisao_anterior_id": r.get("revisao_anterior_id"),
                    "nota": r.get("nota"),
                    "o_que_mudou": r["o_que_mudou"],
                    "vpl_reais": r.get("vpl_reais"),
                    "energia_recuperada_mwh": r.get("energia_recuperada_mwh"),
                }
                for r in s["revisoes"]
            ],
        }
        for s in lista
    ]
    linhas = [
        f'- Simulação {s["simulacao_id"]}, "{s["nome"]}" ({s["modalidade"]}), restrição '
        f"{s['restricao_id']}: {len(s['revisoes'])} revisões, a mais nova é a "
        f"{s['revisoes'][0]['revisao_id']}"
        for s in dados
        if s["revisoes"]
    ]
    return (f"{len(dados)} simulações salvas:\n" + "\n".join(linhas)) if dados else (
        "Nenhuma simulação salva."
    ), dados


def resultado(resultado: dict[str, Any]) -> dict[str, Any]:
    tec, fin = resultado["tecnico"], resultado["financeiro"]
    return {
        "energia_cortada_mwh": tec["energia_cortada_mwh"],
        "energia_recuperada_mwh": tec["energia_recuperada_mwh"],
        "fracao_recuperada": tec["fracao_recuperada"],
        "vpl_reais": fin["vpl_reais"],
        "tir_aa": fin.get("tir_aa"),
        "payback_simples_anos": fin.get("payback_simples_anos"),
        "payback_descontado_anos": fin.get("payback_descontado_anos"),
        "custo_por_mwh_reais": fin.get("custo_por_mwh_reais"),
    }


def revisao(completa: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """A revisão sem as séries: configuração, totais, diagnósticos, avisos, premissas com
    status, as outras revisões da simulação e os cruzamentos entre elas."""
    irmas = completa.get("revisoes", [])
    posicao = next((r["posicao"] for r in irmas if r["id"] == completa["id"]), None)
    numeros = resultado(completa["resultado"])
    diagnosticos = completa["resultado"].get("diagnosticos")
    dados = {
        "revisao_id": completa["id"],
        "simulacao_id": completa["simulacao_id"],
        "posicao": posicao,
        "restricao_id": completa["restricao_id"],
        "procedencia": completa.get("procedencia"),
        "nota": completa.get("nota"),
        "revisao_anterior_id": completa.get("revisao_anterior_id"),
        "snapshot_id": completa["snapshot_id"],
        "metodo_versao": completa["metodo_versao"],
        "configuracao": completa["configuracao"],
        "resultado": numeros,
        "diagnosticos": diagnosticos,
        "avisos": [{"codigo": a["codigo"], "mensagem": a["mensagem"]} for a in completa["avisos"]],
        "premissas": [
            {"id": p["id"], "valor": p["valor"], "status": p["status"]}
            for p in completa["premissas_usadas"].values()
        ],
        "cruzamentos": completa.get("cruzamentos"),
        "revisoes_da_simulacao": [
            {
                "revisao_id": r["id"],
                "posicao": r["posicao"],
                "procedencia": r.get("procedencia"),
                "revisao_anterior_id": r.get("revisao_anterior_id"),
            }
            for r in irmas
        ],
    }
    texto = [
        f"Revisão {completa['id']} (rev {posicao} da simulação {completa['simulacao_id']}, "
        f"{completa.get('procedencia')}): {alavanca(completa['configuracao'])}.",
        texto_do_resultado(numeros),
    ]
    if completa.get("nota"):
        texto.append(f"Nota: {completa['nota']}")
    if diagnosticos:
        texto.append(texto_dos_diagnosticos(diagnosticos))
    if completa.get("cruzamentos"):
        texto.append(texto_dos_cruzamentos(completa["cruzamentos"]))
    if dados["avisos"]:
        texto.append("Avisos: " + " ".join(a["mensagem"] for a in dados["avisos"]))
    return "\n".join(texto), dados


def texto_do_resultado(numeros: dict[str, Any]) -> str:
    return (
        f"Recupera {numero_br(numeros['energia_recuperada_mwh'], 0)} MWh de "
        f"{numero_br(numeros['energia_cortada_mwh'], 0)} "
        f"({porcentagem(numeros['fracao_recuperada'])}); "
        f"VPL {reais(numeros['vpl_reais'])}; TIR "
        f"{porcentagem(numeros['tir_aa']) if numeros['tir_aa'] is not None else 'não existe'}; "
        f"payback simples {anos(numeros['payback_simples_anos'])}; custo por MWh "
        f"{reais(numeros['custo_por_mwh_reais'])}."
    )


def texto_dos_diagnosticos(diagnosticos: dict[str, Any]) -> str:
    residual = diagnosticos["corte_residual"]
    por_hora = residual["por_hora_do_dia_mwh"]
    horas = sorted(range(24), key=lambda h: -por_hora[h])[:3]
    partes = [
        f"Corte que sobrou: {numero_br(residual['energia_mwh'], 0)} MWh, mais nas horas "
        + ", ".join(f"{h}h ({numero_br(por_hora[h], 0)} MWh)" for h in horas if por_hora[h] > 0)
        + "."
    ]
    saturacao = diagnosticos.get("saturacao")
    if saturacao:
        cheia = saturacao.get("fracao_cheia")
        partes.append(
            f"Bateria cheia com corte sobrando em {saturacao['meias_horas_cheia']} de "
            f"{saturacao['meias_horas_com_corte']} meias horas com corte"
            + (f" ({porcentagem(cheia)})" if cheia is not None else "")
            + f"; dos {saturacao['episodios']} episódios de corte, "
            f"{saturacao['episodios_comecaram_vazia']} a pegaram vazia e "
            f"{saturacao['episodios_comecaram_com_carga']} ainda com carga."
        )
    return " ".join(partes)


def texto_dos_cruzamentos(cruzamentos: dict[str, Any]) -> str:
    partes = []
    payback = cruzamentos.get("payback_no_horizonte")
    tir = cruzamentos.get("tir_acima_da_taxa")
    if payback:
        partes.append(
            f"o payback passa a caber no horizonte entre as revisões {payback['antes_revisao_id']} "
            f"e {payback['depois_revisao_id']}"
        )
    if tir:
        partes.append(
            f"a TIR passa da taxa entre as revisões {tir['antes_revisao_id']} e "
            f"{tir['depois_revisao_id']}"
        )
    return (
        "Entre as revisões da simulação, " + "; ".join(partes) + "."
        if partes
        else "Nenhuma revisão da simulação cruza o horizonte de payback nem a taxa."
    )


# Simulação nova, relatório e tarefa ---------------------------------------------------------------


def nome_da_restricao(restricao: dict[str, Any]) -> str:
    return restricao.get("nome_curto") or restricao["texto"]


def linha(restricao: dict[str, Any], cod_equipamento: str | None) -> str:
    """A linha pelas duas pontas e pela tensão, com o código do cadastro."""
    for equipamento in restricao["equipamentos"]:
        if equipamento["cod_equipamento"] == cod_equipamento:
            return (
                f"{equipamento['subestacao_de']} – {equipamento['subestacao_para']}, "
                f"{equipamento['tensao_kv']} kV ({cod_equipamento})"
            )
    return str(cod_equipamento)


ALAVANCAS_DA_MODALIDADE = {
    "bateria": "potência, duração e subestação da bateria",
    "equipamento": "ganho de limite do circuito novo",
    "combinada": "potência, duração e subestação da bateria e ganho de limite do circuito novo",
}


def pedido_padrao(restricao: dict[str, Any], revisao_id: int, configuracao: dict[str, Any]) -> str:
    """O pedido da exploração que a simulação criada pelo chat dispara quando a pessoa não disse
    o que quer descobrir: percorrer a faixa da alavanca e ver onde o resultado muda."""
    return (
        f"Explorar variações de {ALAVANCAS_DA_MODALIDADE[configuracao['modalidade']]} na "
        f"restrição {nome_da_restricao(restricao)}, a partir da revisão {revisao_id} "
        f"({alavanca(configuracao)}), mostrando como o corte que sobra, o VPL, a TIR e o payback "
        "mudam: onde melhoram, onde param de melhorar e onde o payback passa a caber no "
        "horizonte."
    )


def nova_simulacao(escolhas: dict[str, Any], restricao: dict[str, Any]) -> str:
    """Os campos que criam a simulação, como o cartão os mostra: nada montado nem calculado."""
    modalidade = escolhas["modalidade"]
    linhas = [
        f"- nome: {escolhas['nome']}",
        f"- restrição: {nome_da_restricao(restricao)} (id {restricao['id']})",
        f"- modalidade: {modalidade}",
        f"- cenário: {escolhas['cenario']}",
    ]
    if modalidade in ("equipamento", "combinada"):
        linhas += [
            f"- linha que recebe o circuito: {linha(restricao, escolhas['cod_equipamento'])}",
            f"- ganho de limite: {numero_br(escolhas['ganho_limite_mw'])} MW",
        ]
    if modalidade in ("bateria", "combinada"):
        linhas += [
            f"- potência: {numero_br(escolhas['potencia_mw'])} MW",
            f"- capacidade: {numero_br(escolhas['capacidade_mwh'])} MWh",
            f"- subestação de conexão: {escolhas['subestacao']}",
        ]
    return (
        "Simulação nova para confirmar, ainda não salva. Os valores passaram nas conferências "
        "do ARCO:\n" + "\n".join(linhas)
    )


def relatorio(completo: dict[str, Any], link: str | None) -> tuple[str, dict[str, Any]]:
    dados = {
        "relatorio_id": completo["id"],
        "simulacao_id": completo["simulacao_id"],
        "estado": completo["estado"],
        "revisoes_cobertas": completo["revisoes_cobertas"],
        "revisoes_novas": completo.get("revisoes_novas", []),
        "prosa": completo.get("prosa"),
        "verificacao": completo.get("verificacao"),
        "fronteiras": (completo.get("derivados") or {}).get("fronteiras"),
        "erro": completo.get("erro"),
        "link": link,
    }
    estado = completo["estado"]
    if estado == "gerando":
        texto = (
            f"O relatório {completo['id']} ainda está sendo gerado. Consulte de novo em instantes."
        )
    elif estado == "pronto" and completo.get("prosa"):
        prosa = completo["prosa"]
        texto = (
            f"Relatório {completo['id']}, sobre as revisões {completo['revisoes_cobertas']}, "
            f"com a prosa conferida por código.\n\n{prosa['leitura_geral']}\n\n"
            f"Sensibilidade: {prosa['sensibilidade']}\n\nFora do método: {prosa['fora_do_metodo']}"
        )
    elif estado == "barrado":
        texto = (
            f"O relatório {completo['id']} foi barrado pelo verificador: a prosa tinha número sem "
            "origem ou forma de recomendação, e não é mostrada. A parte calculada está no link."
        )
    else:
        texto = f"O relatório {completo['id']} falhou: {completo.get('erro')}"
    if link:
        texto += f"\nAbrir no painel: {link}"
    return texto, dados


def andamento(tarefa: dict[str, Any], link: str) -> tuple[str, dict[str, Any]]:
    contagem = tarefa["contagem"]
    texto = (
        f"Exploração {tarefa['id']} ({tarefa['estado']}): {contagem['prontas']} revisões "
        f"prontas, {contagem['trabalhando']} trabalhando, {contagem['recusadas']} recusadas, "
        f"em {contagem['rodadas']} rodadas; limite de {tarefa['teto']}."
    )
    if tarefa.get("motivo"):
        texto += f" Terminou: {tarefa['motivo']}"
    if tarefa.get("relatorio_id"):
        texto += f" Relatório {tarefa['relatorio_id']} pedido."
    texto += f"\nVer processamento: {link}"
    return texto, tarefa | {"link": link}
