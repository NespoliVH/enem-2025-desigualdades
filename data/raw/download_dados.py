"""Baixa os Microdados do ENEM 2025 do portal oficial do INEP.

Autor: Victor Hugo Nespoli · Bacharelado em Sistemas de Informação, Centro Universitário La Salle do Rio de Janeiro (UNILASALLE-RJ)
Disciplina: Linguagem de Programação (Análise e Visualização de Dados com Python) · 6º Período · 2026/2
Licença: MIT · Repositório: https://github.com/NespoliVH/enem-2025-desigualdades

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
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://download.inep.gov.br/microdados/microdados_enem_2025.zip"
DESTINO = Path(__file__).resolve().parent
ARQUIVOS = ("RESULTADOS_2025.csv", "PARTICIPANTES_2025.csv", "ITENS_PROVA_2025.csv")
DEFLATE64 = 9  # código do método de compressão no cabeçalho ZIP


def baixar(url: str, destino: Path) -> Path:
    """Faz o download em fluxo (streaming), exibindo o progresso."""
    zip_path = destino / "microdados_enem_2025.zip"
    if zip_path.exists():
        print(f"Zip já existe: {zip_path.name}")
        return zip_path
    print(f"Baixando {url} (~1 GB)")
    parcial = zip_path.with_suffix(".zip.part")  # evita reaproveitar zip incompleto
    with urllib.request.urlopen(url) as resp, open(parcial, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        baixado = 0
        while bloco := resp.read(1 << 20):
            f.write(bloco)
            baixado += len(bloco)
            print(f"\r  {baixado / 1e6:,.0f}" + (f" / {total / 1e6:,.0f}" if total else "") + " MB",
                  end="")
    print()
    parcial.replace(zip_path)
    return zip_path


def extrator_externo() -> list[str] | None:
    """Localiza o 7-Zip ou o unzip, que suportam o método Deflate64."""
    candidatos = [shutil.which("7z"), r"C:\Program Files\7-Zip\7z.exe"]
    for exe in candidatos:
        if exe and Path(exe).exists():
            return [exe, "e", "-y", "-bd"]  # 7z e <zip> -o<dir> <membro>
    unzip = shutil.which("unzip")
    return [unzip, "-o", "-j"] if unzip else None


def extrair_externo(zip_path: Path, membro: str, destino: Path) -> None:
    """Extrai um membro do zip com 7-Zip ou unzip."""
    cmd = extrator_externo()
    if cmd is None:
        raise SystemExit(
            f"'{Path(membro).name}' usa compressão Deflate64, que o Python não lê. "
            "Instale o 7-Zip (Windows) ou o unzip (Linux/macOS) e rode o script de novo, "
            f"ou extraia manualmente o arquivo de {zip_path.name} para {destino}."
        )
    if Path(cmd[0]).stem.lower() == "7z":
        args = [*cmd, str(zip_path), f"-o{destino}", membro]
    else:
        args = [*cmd, str(zip_path), membro, "-d", str(destino)]
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def extrair(zip_path: Path, destino: Path) -> None:
    """Extrai apenas os três CSVs de dados, ignorando provas e documentos.

    O INEP compacta ``RESULTADOS_2025.csv`` (2,1 GB) com o método Deflate64
    (código 9), não suportado pelo módulo ``zipfile``. Nesse caso, recorre-se
    ao 7-Zip ou ao unzip.
    """
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            nome = Path(info.filename).name
            if nome not in ARQUIVOS:
                continue
            print(f"Extraindo {nome}")
            if info.compress_type == DEFLATE64:
                extrair_externo(zip_path, info.filename, destino)
            else:
                with zf.open(info) as src, open(destino / nome, "wb") as dst:
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
