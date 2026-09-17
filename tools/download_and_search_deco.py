import json
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

HOST = __import__("os").getenv("DECO_HOST", "192.168.68.1")
BASE_URL = f"https://{HOST}/webpages/"

ROOT = Path("tools/deco_web")
ROOT.mkdir(parents=True, exist_ok=True)

SEARCH_TERMS = re.compile(
    r"traffic|usage|statistics|statistic|byte|bytes|rx|tx|"
    r"download|upload|flow|counter|total",
    re.IGNORECASE,
)


def extract_paths(obj):
    paths = set()

    if isinstance(obj, dict):
        for value in obj.values():
            if isinstance(value, str):
                if value.startswith("./"):
                    paths.add(value[2:])
            else:
                paths.update(extract_paths(value))

    elif isinstance(obj, list):
        for item in obj:
            paths.update(extract_paths(item))

    return paths


def download_file(client, path):
    url = BASE_URL + path

    try:
        response = client.get(url)

        if response.status_code != 200:
            print(f"{response.status_code:3}  {path}")
            return None

        output = ROOT / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.content)

        print(f"200  {len(response.content):7}  {path}")

        return response.text

    except Exception as exc:
        print(f"ERR  {path} -> {exc}")
        return None


def main():
    files = set()

    for filename in ["tools/models.json", "tools/modules.json"]:
        path = Path(filename)

        if not path.exists():
            print(f"FALTA: {path}")
            continue

        print(f"\nA ler: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))

        found = extract_paths(data)

        print(f"  caminhos encontrados: {len(found)}")

        files.update(found)

    # Só ficheiros que nos interessam
    files = {
        p for p in files
        if p.endswith((".js", ".html", ".json"))
    }

    print(f"\nTOTAL DE FICHEIROS A TESTAR: {len(files)}\n")

    matches = []

    with httpx.Client(
        verify=False,
        timeout=10,
        follow_redirects=True,
    ) as client:

        for path in sorted(files):
            text = download_file(client, path)

            if not text:
                continue

            for match in SEARCH_TERMS.finditer(text):
                start = max(0, match.start() - 180)
                end = min(len(text), match.end() + 350)

                snippet = text[start:end].replace("\n", " ")

                matches.append(
                    (path, match.group(), snippet)
                )

    print("\n")
    print("=" * 80)
    print("RESULTADOS DA PESQUISA")
    print("=" * 80)

    if not matches:
        print("\nNenhuma referência encontrada.")
        return

    for path, term, snippet in matches:
        print(f"\n--- {path} | termo: {term} ---")
        print(snippet)

    report = ROOT / "traffic-search.txt"

    with report.open("w", encoding="utf-8") as f:
        for path, term, snippet in matches:
            f.write(f"\n--- {path} | termo: {term} ---\n")
            f.write(snippet)
            f.write("\n")

    print(f"\n\nRelatório guardado em: {report}")


if __name__ == "__main__":
    main()