"""Gera e executa notebooks/analise_exploratoria.ipynb (uso interno do projeto).

    python notebooks/_gerar_notebook.py
"""

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

AQUI = Path(__file__).resolve().parent
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

celulas = [
    md("""# Análise exploratória — Microdados do ENEM 2025

Caderno de **exploração preliminar, prototipação e validação** do projeto
*Desigualdades no ENEM 2025: rede de ensino, território e perfil socioeconômico*.

O pipeline definitivo está em `src/etl.py`, e as figuras do artigo, em
`src/visualizacao.py`. Este caderno parte dos dados já processados
(`python -m src.etl`) e documenta as verificações que sustentam as decisões
metodológicas."""),
    code("""import sys
from pathlib import Path

RAIZ = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RAIZ))

import pandas as pd
from src.etl import DIR_PROCESSED, d_de_cohen, resumo_descritivo

pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
res = pd.read_parquet(DIR_PROCESSED / "resultados_2025.parquet")
part = pd.read_parquet(DIR_PROCESSED / "participantes_2025.parquet")
mun = pd.read_csv(DIR_PROCESSED / "municipios_2025.csv.gz")
print(f"Resultados: {res.shape} | Participantes: {part.shape} | Municípios: {mun.shape}")"""),
    md("""## 1. Integridade e consistência

As bases não têm chave comum. Por isso, verificamos se os totais batem e se a
agregação por município de prova é consistente (razão de inscritos = 1)."""),
    code("""assert len(res) == len(part), "As bases deveriam ter o mesmo número de inscritos"
print("Inscritos (ambas as bases):", f"{len(res):,}".replace(",", "."))
print("Razão de inscritos por município: min =", mun["RAZAO_INSCRITOS"].min(),
      "| max =", mun["RAZAO_INSCRITOS"].max())
res.memory_usage(deep=True).sum() / 1e6"""),
    md("## 2. Valores ausentes"),
    code("""ausentes = res.isna().mean().sort_values(ascending=False)
ausentes[ausentes > 0].to_frame("proporção ausente")"""),
    md("""A ausência das notas coincide com a falta ou a eliminação, como confirma o
cruzamento abaixo. A ausência da rede (`NO_REDE`) corresponde aos inscritos sem
escola vinculada no Censo Escolar 2025 (egressos e treineiros). Por isso,
**nenhum valor foi imputado**."""),
    code("""pd.crosstab(res["TP_PRESENCA_MT"], res["NU_NOTA_MT"].isna(),
            rownames=["presença MT"], colnames=["nota MT ausente"])"""),
    md("## 3. Distribuição da média geral e valores atípicos"),
    code("""validos = res[res["IN_VALIDO"]]
pd.Series(resumo_descritivo(validos["NU_MEDIA_GERAL"]), name="média geral").to_frame()"""),
    code("""ax = validos["NU_MEDIA_GERAL"].plot.hist(bins=80, figsize=(8, 3.5), color="#2a78d6")
ax.set_xlabel("Média geral (pontos)"); ax.set_ylabel("Participantes");"""),
    md("""A segunda concentração em torno de 330–340 pontos corresponde às redações
com nota zero (status diferente de "sem problemas"):"""),
    code("""validos.groupby(validos["NU_NOTA_REDACAO"] == 0)["NU_MEDIA_GERAL"].describe()"""),
    md("## 4. RQ1 — Rede e localização (protótipo)"),
    code("""com_rede = validos[validos["NO_REDE"].notna()]
com_rede.groupby("NO_REDE", observed=True)["NU_MEDIA_GERAL"].agg(["size", "mean", "median", "std"])"""),
    code("""print("d (Privada × Estadual):", round(d_de_cohen(
    com_rede.loc[com_rede.NO_REDE == "Privada", "NU_MEDIA_GERAL"],
    com_rede.loc[com_rede.NO_REDE == "Estadual", "NU_MEDIA_GERAL"]), 3))
com_rede.groupby("NO_LOCALIZACAO", observed=True)["NU_MEDIA_GERAL"].agg(["size", "mean", "median"])"""),
    md("## 5. RQ2 — Correlações municipais (protótipo)"),
    code("""m = mun[mun["N_VALIDOS"] >= 100]
print(len(m), "municípios;", f"{m['N_VALIDOS'].sum() / mun['N_VALIDOS'].sum():.2%}", "dos válidos")
cols = ["RENDA_PC_MEDIANA", "PCT_BAIXA_RENDA", "PCT_MAE_SEM_EM", "PCT_SEM_INTERNET",
        "PCT_SEM_COMPUTADOR", "PCT_ESCOLA_PUBLICA", "PCT_PPI", "PCT_TREINEIROS"]
m[cols + ["MEDIA_GERAL", "TX_ABSTENCAO_TOTAL"]].corr("spearman")[["MEDIA_GERAL", "TX_ABSTENCAO_TOTAL"]].loc[cols]"""),
    md("## 6. RQ3 — Abstenção (protótipo)"),
    code("""res[["IN_FALTOU_DIA1", "IN_FALTOU_DIA2", "IN_AUSENTE_TOTAL", "IN_ELIMINADO"]].mean().to_frame("proporção")"""),
    code("""(res.groupby(res["NO_REDE"].astype("string").fillna("Sem escola vinculada"))["IN_AUSENTE_TOTAL"]
   .mean().sort_values().to_frame("abstenção"))"""),
    md("""## 7. Perfil socioeconômico nacional dos inscritos"""),
    code("""perfil = part[["IN_BAIXA_RENDA", "IN_MAE_SEM_EM", "IN_SEM_INTERNET", "IN_SEM_COMPUTADOR",
               "IN_ESCOLA_PUBLICA", "IN_PPI", "IN_TREINEIRO", "IN_CONCLUINTE_2025"]].astype(float).mean()
print("Renda per capita mediana estimada: R$", round(part["NU_RENDA_PC"].median(), 2))
perfil.to_frame("proporção")"""),
    md("""## Conclusões da exploração

- As duas bases são consistentes em contagem total e por município, o que
  valida a integração ecológica.
- Nota ausente significa falta ou eliminação, e não erro de coleta. Sem imputação.
- Os resultados preliminares de RQ1–RQ3 foram consolidados em
  `src/visualizacao.py` e discutidos no artigo (`docs/index.html`)."""),
]

nb = nbf.v4.new_notebook(cells=celulas, metadata={
    "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
    "language_info": {"name": "python"},
})
NotebookClient(nb, timeout=600, kernel_name="python3", resources={"metadata": {"path": str(AQUI)}}).execute()
nbf.write(nb, AQUI / "analise_exploratoria.ipynb")
print("Notebook gerado e executado.")
