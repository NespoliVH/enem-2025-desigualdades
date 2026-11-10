"""Baixa os Microdados do ENEM 2025 do portal oficial do INEP.

Os arquivos brutos (~2,5 GB descompactados) excedem o limite de 100 MB por
arquivo do GitHub e, por isso, não são versionados. Este script reproduz a
aquisição sem autenticação nem credenciais:

    python data/raw/download_dados.py

Ao final, ``data/raw/`` conterá:

    RESULTADOS_2025.csv     notas, presença e escola de conclusão
    PARTICIPANTES_2025.csv  perfil e questionário socioeconômico
    ITENS_PROVA_2025.csv    itens das provas e parâmetros da TRI

Fonte: INEP — https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem
"""

from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://download.inep.gov.br/microdados/microdados_enem_2025.zip"
DESTINO = Path(__file__).resolve().parent
ARQUIVOS = ("RESULTADOS_2025.csv", "PARTICIPANTES_2025.csv", "ITENS_PROVA_2025.csv")


def baixar(url: str, destino: Path) -> Path:
    """Faz o download em fluxo (streaming), exibindo o progresso."""
    zip_path = destino / "microdados_enem_2025.zip"
    if zip_path.exists():
        print(f"Zip já existe: {zip_path.name}")
        return zip_path
    print(f"Baixando {url}")
    with urllib.request.urlopen(url) as resp, open(zip_path, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        baixado = 0
        while bloco := resp.read(1 << 20):
            f.write(bloco)
            baixado += len(bloco)
            if total:
                print(f"\r  {baixado / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="")
    print()
    return zip_path


def extrair(zip_path: Path, destino: Path) -> None:
    """Extrai apenas os três CSVs de dados, ignorando provas e documentos."""
    with zipfile.ZipFile(zip_path) as zf:
        for membro in zf.namelist():
            nome = Path(membro).name
            if nome in ARQUIVOS:
                print(f"Extraindo {nome}")
                with zf.open(membro) as src, open(destino / nome, "wb") as dst:
                    shutil.copyfileobj(src, dst)


def main() -> int:
    if all((DESTINO / a).exists() for a in ARQUIVOS):
        print("Arquivos brutos já presentes em data/raw/.")
        return 0
    extrair(baixar(URL, DESTINO), DESTINO)
    faltando = [a for a in ARQUIVOS if not (DESTINO / a).exists()]
    if faltando:
        print(f"Arquivos não encontrados no zip: {faltando}", file=sys.stderr)
        return 1
    print("Concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
