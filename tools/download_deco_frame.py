import os
import httpx
from dotenv import load_dotenv

load_dotenv()

HOST = os.getenv("DECO_HOST", "192.168.68.1")
BASE = f"https://{HOST}"

path = "/webpages/js/su/frame.js"

with httpx.Client(verify=False, timeout=30) as client:
    r = client.get(BASE + path)

print("HTTP:", r.status_code)
print("SIZE:", len(r.text))

if r.status_code == 200:
    with open(".\\tools\\frame.js", "w", encoding="utf-8") as f:
        f.write(r.text)
    print("GUARDADO: .\\tools\\frame.js")