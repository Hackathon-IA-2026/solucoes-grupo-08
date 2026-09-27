from __future__ import annotations

from arco_dados.fontes import FONTES, interpretar_listagem, nome_local, selecionar

LISTAGEM = """<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>ons-aws-prod-opendata</Name><Prefix>dataset/restricao_coff_eolica_tm/</Prefix>
  <IsTruncated>false</IsTruncated>
  <Contents><Key>dataset/restricao_coff_eolica_tm/RESTRICAO_COFF_EOLICA_2024_12.parquet</Key>
    <LastModified>2026-09-11T10:00:00.000Z</LastModified><ETag>"aaa"</ETag><Size>10</Size></Contents>
  <Contents><Key>dataset/restricao_coff_eolica_tm/RESTRICAO_COFF_EOLICA_2026_08.parquet</Key>
    <LastModified>2026-09-15T15:07:13.000Z</LastModified><ETag>"c72c"</ETag><Size>4419657</Size></Contents>
  <Contents><Key>dataset/restricao_coff_eolica_tm/DicionarioDados_RestricaoContrainedoff_UsiEolicas.pdf</Key>
    <LastModified>2026-09-08T12:00:00.000Z</LastModified><ETag>"bbb"</ETag><Size>500</Size></Contents>
</ListBucketResult>"""


def fonte(nome: str):
    return next(f for f in FONTES if f.nome == nome)


def test_listagem_e_interpretada() -> None:
    objetos, proximo = interpretar_listagem(LISTAGEM)
    assert proximo is None
    assert [o.nome for o in objetos] == [
        "RESTRICAO_COFF_EOLICA_2024_12.parquet",
        "RESTRICAO_COFF_EOLICA_2026_08.parquet",
        "DicionarioDados_RestricaoContrainedoff_UsiEolicas.pdf",
    ]
    assert objetos[1].tamanho == 4419657
    assert objetos[1].etag == "c72c"
    assert objetos[1].modificado_em.year == 2026


def test_corte_eolico_aceita_2025_em_diante_e_o_dicionario() -> None:
    objetos, _ = interpretar_listagem(LISTAGEM)
    nomes = [o.nome for o in selecionar(fonte("corte_eolica"), objetos)]
    assert nomes == [
        "RESTRICAO_COFF_EOLICA_2026_08.parquet",
        "DicionarioDados_RestricaoContrainedoff_UsiEolicas.pdf",
    ]


def test_padroes_das_outras_fontes() -> None:
    assert fonte("corte_solar").aceita("RESTRICAO_COFF_FOTOVOLTAICA_2025_09.parquet")
    assert not fonte("corte_solar").aceita("RESTRICAO_COFF_FOTOVOLTAICA_2024_09.parquet")
    assert fonte("cmo").aceita("CMO_SEMIHORARIO_2026.parquet")
    assert not fonte("cmo").aceita("CMO_SEMIHORARIO_2024.parquet")
    assert fonte("linhas").aceita("LINHA_TRANSMISSAO.parquet")
    assert fonte("comandos_eolica").aceita("COFF_USI_EOLICAS_INTRASEMIHORA_2026_01.parquet")
    assert not fonte("comandos_eolica").obrigatoria


def test_nome_local_achata_a_pasta() -> None:
    assert (
        nome_local("dataset/restricao_coff_eolica_tm/RESTRICAO_COFF_EOLICA_2026_08.parquet")
        == "restricao_coff_eolica_tm__RESTRICAO_COFF_EOLICA_2026_08.parquet"
    )
