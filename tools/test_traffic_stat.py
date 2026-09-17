import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("DECO_HOST", "192.168.68.1")
BASE_URL = f"https://{HOST}"

# ATENÇÃO:
# Este teste assume que a autenticação do DecoClient já está implementada.
from network_monitor.collectors.deco.client import DecoClient


def main():
    client = DecoClient()

    print("A autenticar na Deco...")

    if not client.authenticate():
        print("ERRO: autenticação falhou.")
        return

    print("Autenticação OK.")
    print(f"stok: {'OK' if client.stok else 'NÃO'}")
    print()

    url = client._url("/admin/client?form=traffic_stat")

    payload = {
        "operation": "list"
    }

    print("A consultar:")
    print(url)
    print()
    print("Payload:")
    print(json.dumps(payload, indent=2))
    print()

    response = client._post(url, payload)

    print("HTTP:", response.status_code)
    print()
    print("Resposta:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()