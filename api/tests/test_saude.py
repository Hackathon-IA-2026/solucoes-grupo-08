from fastapi.testclient import TestClient

from arco_api.main import app
from arco_motor import METODO_VERSAO


def test_saude_responde_com_a_versao_do_metodo() -> None:
    resposta = TestClient(app).get("/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "metodo_versao": METODO_VERSAO}
