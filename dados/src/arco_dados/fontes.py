"""Fontes do ONS usadas pelo ARCO: pasta no bucket, padrão de nome e finalidade.

Bucket público, sem credencial. Cada pasta traz os Parquet e o dicionário de dados
(`DicionarioDados_*`), que entra no snapshot para a auditoria citar a versão exata.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime

import httpx

BASE_URL = "https://ons-aws-prod-opendata.s3.amazonaws.com"
RAIZ = "dataset/"
PORTAL = "https://dados.ons.org.br/dataset/"
LICENCA = "CC-BY. Operador Nacional do Sistema Elétrico (ONS), Portal de Dados Abertos."
_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
_DICIONARIO = r"^DicionarioDados_.*\.(pdf|json)$"
_ANO = r"20(2[5-9]|[3-9]\d)"


@dataclass(frozen=True)
class Fonte:
    nome: str
    pasta: str
    padrao: str
    finalidade: str
    portal: str
    obrigatoria: bool = True

    def aceita(self, nome_arquivo: str) -> bool:
        return re.search(self.padrao, nome_arquivo) is not None


def _fonte(
    nome: str, pasta: str, arquivo: str, finalidade: str, portal: str, obrigatoria: bool = True
) -> Fonte:
    return Fonte(
        nome, pasta, f"(?:{arquivo})|(?:{_DICIONARIO})", finalidade, PORTAL + portal, obrigatoria
    )


FONTES: tuple[Fonte, ...] = (
    _fonte(
        "corte_eolica",
        "restricao_coff_eolica_tm/",
        rf"^RESTRICAO_COFF_EOLICA_{_ANO}_\d{{2}}\.parquet$",
        "Corte eólico por conjunto e meia hora, com razão, origem, texto e energia apurada.",
        "restricao_coff_eolica_usi",
    ),
    _fonte(
        "corte_solar",
        "restricao_coff_fotovoltaica_tm/",
        rf"^RESTRICAO_COFF_FOTOVOLTAICA_{_ANO}_\d{{2}}\.parquet$",
        "Corte solar por conjunto e meia hora, com razão, origem, texto e energia apurada.",
        "restricao_coff_fotovoltaica",
    ),
    _fonte(
        "linhas",
        "linha_transmissao/",
        r"^LINHA_TRANSMISSAO\.parquet$",
        "Cadastro de linhas: terminais, tensão, circuito, capacidades em MVA, cod_equipamento.",
        "linha-transmissao",
    ),
    _fonte(
        "transformadores",
        "capacidade-transformacao/",
        r"^CAPACIDADE_TRANSFORMACAO\.parquet$",
        "Cadastro de transformadores: potência nominal e tensões.",
        "capacidade-transformacao",
    ),
    _fonte(
        "subestacoes",
        "subestacao/",
        r"^SUBESTACAO\.parquet$",
        "Subestações com latitude e longitude, para o mapa.",
        "subestacao",
    ),
    _fonte(
        "cmo",
        "cmo_tm/",
        rf"^CMO_SEMIHORARIO_{_ANO}\.parquet$",
        "CMO semi-horário por submercado: sugestão de preço da energia recuperada.",
        "cmo-semi-horario",
    ),
    _fonte(
        "usina_conjunto",
        "usina_conjunto/",
        r"^RELACIONAMENTO_USINA_CONJUNTO\.parquet$",
        "Relação entre usina e conjunto, com vigência, para abrir um conjunto nas usinas.",
        "usina_conjunto",
    ),
    _fonte(
        "comandos_eolica",
        "restricao_coff_eolica_intrasemihora/",
        rf"^COFF_USI_EOLICAS_INTRASEMIHORA_{_ANO}_\d{{2}}\.parquet$",
        "Comandos de restrição evento a evento, eólica. Só para auditoria de ocorrência.",
        "coff_eolica_usi_intrasemihora",
        obrigatoria=False,
    ),
    _fonte(
        "comandos_solar",
        "restricao_coff_fotovoltaica_intrasemihora/",
        rf"^COFF_USI_FOTOVOLTAICA_INTRASEMIHORA_{_ANO}_\d{{2}}\.parquet$",
        "Comandos de restrição evento a evento, solar. Só para auditoria de ocorrência.",
        "coff_fotovoltaica_intrasemihora",
        obrigatoria=False,
    ),
)


@dataclass(frozen=True)
class Objeto:
    chave: str
    tamanho: int
    etag: str
    modificado_em: datetime

    @property
    def nome(self) -> str:
        return self.chave.rsplit("/", 1)[-1]


def nome_local(chave: str) -> str:
    """Nome achatado do arquivo dentro do snapshot: `<pasta>__<arquivo>`."""
    relativo = chave[len(RAIZ) :] if chave.startswith(RAIZ) else chave
    return relativo.replace("/", "__")


def interpretar_listagem(xml: str) -> tuple[list[Objeto], str | None]:
    """Lê uma página da listagem do S3 (list-type=2): objetos e token da próxima página."""
    raiz = ET.fromstring(xml)
    objetos = []
    for item in raiz.findall("s3:Contents", _NS):
        chave = item.findtext("s3:Key", default="", namespaces=_NS)
        tamanho = int(item.findtext("s3:Size", default="0", namespaces=_NS))
        etag = item.findtext("s3:ETag", default="", namespaces=_NS).strip('"')
        modificado = item.findtext("s3:LastModified", default="", namespaces=_NS)
        objetos.append(
            Objeto(chave, tamanho, etag, datetime.fromisoformat(modificado.replace("Z", "+00:00")))
        )
    truncado = raiz.findtext("s3:IsTruncated", default="false", namespaces=_NS) == "true"
    proximo = raiz.findtext("s3:NextContinuationToken", default=None, namespaces=_NS)
    return objetos, (proximo if truncado else None)


def listar(pasta: str, cliente: httpx.Client) -> list[Objeto]:
    """Lista todos os objetos de uma pasta do bucket, seguindo a paginação."""
    objetos: list[Objeto] = []
    token: str | None = None
    while True:
        parametros: dict[str, str] = {"list-type": "2", "prefix": RAIZ + pasta, "max-keys": "1000"}
        if token:
            parametros["continuation-token"] = token
        resposta = cliente.get(BASE_URL, params=parametros)
        resposta.raise_for_status()
        pagina, token = interpretar_listagem(resposta.text)
        objetos.extend(pagina)
        if not token:
            return objetos


def selecionar(fonte: Fonte, objetos: list[Objeto]) -> list[Objeto]:
    return [objeto for objeto in objetos if fonte.aceita(objeto.nome)]
