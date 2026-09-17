import os
import ssl
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False


load_dotenv()

HOST = os.getenv("DECO_HOST", "192.168.68.1")
BASE_URL = f"https://{HOST}/webpages/"

# Caminhos que já sabemos que existem e diretórios prováveis
PATHS = [
    "",
    "config/",
    "modules/",
    "modules/networkMap/",
    "modules/networkMap/mapClients/",
    "modules/networkMap/mapRouter/",
    "modules/advanced/",
    "modules/advanced/network/",
    "modules/advanced/network/networkStatus/",
    "modules/advanced/system/",
]


def main():
    print(f"DECO: {BASE_URL}")
    print()

    context = ssl._create_unverified_context()

    for path in PATHS:
        url = urljoin(BASE_URL, path)

        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})

            with urlopen(req, context=context, timeout=10) as r:
                content = r.read()
                status = getattr(r, "status", 200)

            print(
                f"{status:3} "
                f"{len(content):7} bytes  "
                f"/webpages/{path}"
            )

        except Exception as exc:
            print(f"ERR  /webpages/{path}  {exc}")


if __name__ == "__main__":
    main()