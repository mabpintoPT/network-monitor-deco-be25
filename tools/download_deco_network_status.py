import os
import httpx
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("DECO_HOST", "192.168.68.1")
BASE = f"https://{HOST}"

FILES = [
    "/webpages/modules/advanced/network/networkStatus/controllers.js",
    "/webpages/modules/advanced/network/networkStatus/models.js",
    "/webpages/modules/advanced/network/networkStatus/view.html",
]

with httpx.Client(verify=False, timeout=10) as client:
    for path in FILES:
        print(f"\n===== {path} =====")
        r = client.get(BASE + path)
        print("HTTP:", r.status_code)
        print("SIZE:", len(r.text))

        if r.status_code == 200:
            name = path.rsplit("/", 1)[-1]
            with open(f".\\tools\\{name}", "w", encoding="utf-8") as f:
                f.write(r.text)
            print("GUARDADO")