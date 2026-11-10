"""Pipeline ETL dos Microdados do ENEM 2025 (INEP).

Este módulo concentra as etapas reutilizáveis do projeto:

1. **Extração**: leitura em blocos dos arquivos ``RESULTADOS_2025.csv`` e
   ``PARTICIPANTES_2025.csv`` (codificação Latin-1, separador ``;``), com
   seleção de colunas e tipagem explícita para reduzir o uso de memória.
2. **Transformação**: rotulagem das categorias segundo o dicionário oficial,
   tratamento de valores ausentes e criação de métricas derivadas
   (médias, indicadores de presença, renda familiar *per capita* estimada).
3. **Carga**: persistência em formatos abertos (Parquet e CSV comprimido) em
   ``data/processed/``.

As bases de participantes e de resultados **não possuem chave de ligação**
(decisão do INEP para atender à LGPD). Por isso, a integração entre elas é
feita apenas de forma agregada, pelo município de aplicação da prova
(``CO_MUNICIPIO_PROVA``).

Uso (a partir da raiz do repositório)::

    python -m src.etl                      # lê de data/raw/
    python -m src.etl --raw-dir C:/dados   # lê de outro diretório

O pipeline é determinístico: não há amostragem aleatória, e a mesma entrada
produz sempre a mesma saída.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuração geral
# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parents[1]
DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"

ENCODING = "latin-1"  # os CSVs do INEP não estão em UTF-8
SEPARADOR = ";"
TAMANHO_BLOCO = 500_000  # linhas por bloco na leitura incremental

SALARIO_MINIMO_2025 = 1518.00  # R$, referência das faixas de renda (Q007)

log = logging.getLogger("etl")

# ---------------------------------------------------------------------------
# Rótulos (extraídos do Dicionário de Dados do ENEM 2025)
# ---------------------------------------------------------------------------

REGIOES = {1: "Norte", 2: "Nordeste", 3: "Sudeste", 4: "Sul", 5: "Centro-Oeste"}

REDES = {1: "Federal", 2: "Estadual", 3: "Municipal", 4: "Privada"}
ORDEM_REDES = ["Federal", "Estadual", "Municipal", "Privada"]

LOCALIZACAO = {1: "Urbana", 2: "Rural"}

AREAS = {
    "CN": "Ciências da Natureza",
    "CH": "Ciências Humanas",
    "LC": "Linguagens e Códigos",
    "MT": "Matemática",
}

# Ponto médio (R$) de cada faixa de renda familiar mensal da questão Q007.
# A faixa aberta "Acima de R$ 30.360,00" recebe o limite inferior acrescido
# de 25%, convenção usual para classes abertas.
PONTO_MEDIO_RENDA_Q007 = {
    "A": 0.00,
    "B": 1518.00 / 2,
    "C": (1518.01 + 2277.00) / 2,
    "D": (2277.01 + 3036.00) / 2,
    "E": (3036.01 + 3795.00) / 2,
    "F": (3795.01 + 4554.00) / 2,
    "G": (4554.01 + 6072.00) / 2,
    "H": (6072.01 + 7590.00) / 2,
    "I": (7590.01 + 9108.00) / 2,
    "J": (9108.01 + 10626.00) / 2,
    "K": (10626.01 + 12144.00) / 2,
    "L": (12144.01 + 13662.00) / 2,
    "M": (13662.01 + 15180.00) / 2,
    "N": (15180.01 + 18216.00) / 2,
    "O": (18216.01 + 22770.00) / 2,
    "P": (22770.01 + 30360.00) / 2,
    "Q": 30360.00 * 1.25,
}

# ---------------------------------------------------------------------------
# Esquemas de leitura (colunas selecionadas e tipos primitivos)
# ---------------------------------------------------------------------------

COLUNAS_RESULTADOS: dict[str, str] = {
    "SG_UF_ESC": "string",
    "TP_DEPENDENCIA_ADM_ESC": "float32",  # ausente para não concluintes
    "TP_LOCALIZACAO_ESC": "float32",
    "CO_MUNICIPIO_PROVA": "int32",
    "NO_MUNICIPIO_PROVA": "string",
    "CO_UF_PROVA": "int8",
    "SG_UF_PROVA": "string",
    "TP_PRESENCA_CN": "int8",
    "TP_PRESENCA_CH": "int8",
    "TP_PRESENCA_LC": "int8",
    "TP_PRESENCA_MT": "int8",
    "NU_NOTA_CN": "float32",
    "NU_NOTA_CH": "float32",
    "NU_NOTA_LC": "float32",
    "NU_NOTA_MT": "float32",
    "TP_STATUS_REDACAO": "float32",
    "NU_NOTA_COMP1": "float32",
    "NU_NOTA_COMP2": "float32",
    "NU_NOTA_COMP3": "float32",
    "NU_NOTA_COMP4": "float32",
    "NU_NOTA_COMP5": "float32",
    "NU_NOTA_REDACAO": "float32",
}

COLUNAS_PARTICIPANTES: dict[str, str] = {
    "TP_FAIXA_ETARIA": "int8",
    "TP_SEXO": "string",
    "TP_COR_RACA": "int8",
    "TP_ST_CONCLUSAO": "int8",
    "IN_TREINEIRO": "int8",
    "CO_MUNICIPIO_PROVA": "int32",
    "SG_UF_PROVA": "string",
    "Q002": "string",  # escolaridade da mãe
    "Q005": "int8",  # pessoas na residência
    "Q007": "string",  # renda familiar mensal (faixas)
    "Q020": "string",  # internet wi-fi em casa
    "Q021": "string",  # computador/notebook em casa
    "Q023": "string",  # tipo de escola no ensino médio
}


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------


def ler_csv_inep(caminho: Path, colunas: dict[str, str],
                 tamanho_bloco: int = TAMANHO_BLOCO) -> pd.DataFrame:
    """Lê um CSV dos microdados do INEP em blocos, apenas com as colunas pedidas.

    A leitura incremental (``chunksize``) mantém o consumo de memória
    previsível mesmo para o arquivo de resultados (~2 GB). Campos vazios são
    interpretados como ausentes (``NaN``).
    """
    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho}. Execute data/raw/download_dados.py "
            "ou informe --raw-dir."
        )
    log.info("Lendo %s (%.0f MB)", caminho.name, caminho.stat().st_size / 1e6)
    blocos = []
    leitor = pd.read_csv(
        caminho,
        sep=SEPARADOR,
        encoding=ENCODING,
        usecols=list(colunas),
        dtype=colunas,
        na_values=[""],
        keep_default_na=False,
        chunksize=tamanho_bloco,
    )
    for i, bloco in enumerate(leitor, start=1):
        blocos.append(bloco)
        log.info("  bloco %d: %d linhas acumuladas", i, sum(len(b) for b in blocos))
    return pd.concat(blocos, ignore_index=True)


# ---------------------------------------------------------------------------
# Transformação: resultados
# ---------------------------------------------------------------------------


def regiao_da_uf(codigo_uf: pd.Series) -> pd.Series:
    """Converte o código IBGE da UF (ex.: 35) no nome da região (1º dígito)."""
    return (codigo_uf // 10).map(REGIOES).astype("category")


def transformar_resultados(df: pd.DataFrame) -> pd.DataFrame:
    """Rotula categorias e cria as métricas derivadas da base de resultados.

    Regras de presença (dicionário INEP: 0 = faltou, 1 = presente,
    2 = eliminado). As provas de LC e CH (e a redação) são aplicadas no
    1º dia; CN e MT, no 2º dia.

    Métricas criadas:
        IN_FALTOU_DIA1, IN_FALTOU_DIA2: faltou às duas provas do dia.
        IN_AUSENTE_TOTAL: faltou aos dois dias.
        IN_ELIMINADO: eliminado em pelo menos uma prova.
        IN_VALIDO: presente nas quatro provas objetivas e com nota de redação.
        NU_MEDIA_OBJETIVAS: média simples das quatro provas objetivas.
        NU_MEDIA_GERAL: média simples das quatro objetivas e da redação.
    """
    out = df.copy()
    pres = out[[f"TP_PRESENCA_{a}" for a in AREAS]]

    out["IN_FALTOU_DIA1"] = (out["TP_PRESENCA_LC"] == 0) & (out["TP_PRESENCA_CH"] == 0)
    out["IN_FALTOU_DIA2"] = (out["TP_PRESENCA_CN"] == 0) & (out["TP_PRESENCA_MT"] == 0)
    out["IN_AUSENTE_TOTAL"] = out["IN_FALTOU_DIA1"] & out["IN_FALTOU_DIA2"]
    out["IN_ELIMINADO"] = (pres == 2).any(axis=1)
    out["IN_VALIDO"] = (pres == 1).all(axis=1) & out["NU_NOTA_REDACAO"].notna()

    notas_obj = out[[f"NU_NOTA_{a}" for a in AREAS]]
    out["NU_MEDIA_OBJETIVAS"] = notas_obj.mean(axis=1).where(out["IN_VALIDO"]).astype("float32")
    out["NU_MEDIA_GERAL"] = (
        pd.concat([notas_obj, out["NU_NOTA_REDACAO"]], axis=1)
        .mean(axis=1)
        .where(out["IN_VALIDO"])
        .astype("float32")
    )

    out["NO_REDE"] = pd.Categorical(
        out["TP_DEPENDENCIA_ADM_ESC"].map(REDES), categories=ORDEM_REDES, ordered=True
    )
    out["NO_REDE_AGRUPADA"] = pd.Categorical(
        np.select(
            [out["NO_REDE"] == "Privada", out["NO_REDE"].notna()],
            ["Privada", "Pública"],
            default=None,
        ),
        categories=["Pública", "Privada"],
    )
    out["NO_LOCALIZACAO"] = pd.Categorical(
        out["TP_LOCALIZACAO_ESC"].map(LOCALIZACAO), categories=["Urbana", "Rural"]
    )
    out["NO_REGIAO_PROVA"] = regiao_da_uf(out["CO_UF_PROVA"])

    for col in ["SG_UF_ESC", "SG_UF_PROVA", "NO_MUNICIPIO_PROVA"]:
        out[col] = out[col].astype("category")

    return out.drop(columns=["TP_DEPENDENCIA_ADM_ESC", "TP_LOCALIZACAO_ESC"])


# ---------------------------------------------------------------------------
# Transformação: participantes
# ---------------------------------------------------------------------------


def renda_per_capita_estimada(q007: pd.Series, q005: pd.Series) -> pd.Series:
    """Estima a renda familiar *per capita* pelo ponto médio da faixa (Q007).

    ``renda_pc = ponto_medio(Q007) / Q005``, em que Q005 é o número de
    moradores da residência (incluindo o participante).
    """
    return (q007.map(PONTO_MEDIO_RENDA_Q007) / q005.where(q005 > 0)).astype("float32")


def transformar_participantes(df: pd.DataFrame) -> pd.DataFrame:
    """Cria indicadores socioeconômicos binários no nível do participante.

    Respostas do tipo "Não sei" ou "Não declarado" viram ``NaN`` no
    indicador correspondente, para não distorcer as proporções.
    """
    out = df.copy()
    out["NU_RENDA_PC"] = renda_per_capita_estimada(out["Q007"], out["Q005"])
    out["IN_BAIXA_RENDA"] = out["NU_RENDA_PC"] <= SALARIO_MINIMO_2025 / 2

    # Mãe sem ensino médio completo (A-D); "H" = não sei -> ausente.
    out["IN_MAE_SEM_EM"] = out["Q002"].isin(list("ABCD")).astype("float32")
    out.loc[out["Q002"] == "H", "IN_MAE_SEM_EM"] = np.nan

    out["IN_SEM_INTERNET"] = out["Q020"] == "A"
    out["IN_SEM_COMPUTADOR"] = out["Q021"] == "A"

    # Somente escola pública (A); "F" = não frequentou o EM -> ausente.
    out["IN_ESCOLA_PUBLICA"] = (out["Q023"] == "A").astype("float32")
    out.loc[out["Q023"] == "F", "IN_ESCOLA_PUBLICA"] = np.nan

    # Pretos, pardos e indígenas (2, 3, 5); 0 e 6 = sem declaração -> ausente.
    out["IN_PPI"] = out["TP_COR_RACA"].isin([2, 3, 5]).astype("float32")
    out.loc[out["TP_COR_RACA"].isin([0, 6]), "IN_PPI"] = np.nan

    out["IN_TREINEIRO"] = out["IN_TREINEIRO"] == 1
    out["IN_CONCLUINTE_2025"] = out["TP_ST_CONCLUSAO"] == 2

    for col in ["TP_SEXO", "SG_UF_PROVA", "Q002", "Q007", "Q020", "Q021", "Q023"]:
        out[col] = out[col].astype("category")
    return out


# ---------------------------------------------------------------------------
# Agregações por município (chave de integração ecológica)
# ---------------------------------------------------------------------------


def agregar_resultados_municipio(res: pd.DataFrame) -> pd.DataFrame:
    """Indicadores de desempenho e abstenção por município de prova."""
    g = res.groupby("CO_MUNICIPIO_PROVA", observed=True)
    agg = g.agg(
        NO_MUNICIPIO=("NO_MUNICIPIO_PROVA", "first"),
        SG_UF=("SG_UF_PROVA", "first"),
        CO_UF=("CO_UF_PROVA", "first"),
        N_INSCRITOS_RES=("TP_PRESENCA_LC", "size"),
        N_VALIDOS=("IN_VALIDO", "sum"),
        TX_ABSTENCAO_TOTAL=("IN_AUSENTE_TOTAL", "mean"),
        TX_FALTA_DIA1=("IN_FALTOU_DIA1", "mean"),
        TX_FALTA_DIA2=("IN_FALTOU_DIA2", "mean"),
        MEDIA_OBJETIVAS=("NU_MEDIA_OBJETIVAS", "mean"),
        MEDIA_GERAL=("NU_MEDIA_GERAL", "mean"),
        MEDIA_MT=("NU_NOTA_MT", "mean"),
    )
    agg["MEDIA_REDACAO"] = res.loc[res["IN_VALIDO"]].groupby(
        "CO_MUNICIPIO_PROVA", observed=True)["NU_NOTA_REDACAO"].mean()
    agg["NO_REGIAO"] = regiao_da_uf(agg["CO_UF"].astype(int))
    for col in ["NO_MUNICIPIO", "SG_UF"]:
        agg[col] = agg[col].astype(str)
    return agg.reset_index()


def agregar_participantes_municipio(part: pd.DataFrame) -> pd.DataFrame:
    """Perfil socioeconômico agregado por município de prova."""
    g = part.groupby("CO_MUNICIPIO_PROVA", observed=True)
    agg = g.agg(
        N_INSCRITOS_PART=("Q007", "size"),
        RENDA_PC_MEDIANA=("NU_RENDA_PC", "median"),
        PCT_BAIXA_RENDA=("IN_BAIXA_RENDA", "mean"),
        PCT_MAE_SEM_EM=("IN_MAE_SEM_EM", "mean"),
        PCT_SEM_INTERNET=("IN_SEM_INTERNET", "mean"),
        PCT_SEM_COMPUTADOR=("IN_SEM_COMPUTADOR", "mean"),
        PCT_ESCOLA_PUBLICA=("IN_ESCOLA_PUBLICA", "mean"),
        PCT_PPI=("IN_PPI", "mean"),
        PCT_TREINEIROS=("IN_TREINEIRO", "mean"),
    )
    return agg.reset_index()


def integrar_municipios(res_mun: pd.DataFrame, part_mun: pd.DataFrame) -> pd.DataFrame:
    """Junta as duas bases agregadas pelo código IBGE do município de prova.

    A junção é validada como 1:1. Também é calculada a razão entre o número
    de inscritos nas duas bases, como verificação de consistência.
    """
    mun = res_mun.merge(part_mun, on="CO_MUNICIPIO_PROVA", how="inner", validate="one_to_one")
    mun["RAZAO_INSCRITOS"] = mun["N_INSCRITOS_RES"] / mun["N_INSCRITOS_PART"]
    return mun


# ---------------------------------------------------------------------------
# Métricas estatísticas reutilizáveis
# ---------------------------------------------------------------------------


def resumo_descritivo(serie: pd.Series) -> dict[str, float]:
    """Medidas de posição, dispersão e forma de uma variável numérica."""
    s = serie.dropna().astype("float64")
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    return {
        "n": int(s.size),
        "media": s.mean(),
        "dp": s.std(),
        "cv": s.std() / s.mean() if s.mean() else np.nan,
        "min": s.min(),
        "p10": s.quantile(0.10),
        "q1": q1,
        "mediana": s.median(),
        "q3": q3,
        "p90": s.quantile(0.90),
        "max": s.max(),
        "iqr": iqr,
        "assimetria": s.skew(),
        "pct_outliers_iqr": ((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).mean(),
    }


def d_de_cohen(a: pd.Series, b: pd.Series) -> float:
    """Tamanho de efeito (d de Cohen, desvio-padrão combinado) entre dois grupos."""
    a, b = a.dropna().astype("float64"), b.dropna().astype("float64")
    na, nb = len(a), len(b)
    dp = np.sqrt(((na - 1) * a.var() + (nb - 1) * b.var()) / (na + nb - 2))
    return (a.mean() - b.mean()) / dp


# ---------------------------------------------------------------------------
# Carga e orquestração
# ---------------------------------------------------------------------------


def executar(raw_dir: Path = DIR_RAW, out_dir: Path = DIR_PROCESSED) -> dict[str, Path]:
    """Executa o pipeline completo e devolve os caminhos gerados."""
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    res = transformar_resultados(ler_csv_inep(raw_dir / "RESULTADOS_2025.csv", COLUNAS_RESULTADOS))
    log.info("Resultados: %d linhas, %d válidos", len(res), int(res["IN_VALIDO"].sum()))

    part = transformar_participantes(
        ler_csv_inep(raw_dir / "PARTICIPANTES_2025.csv", COLUNAS_PARTICIPANTES)
    )
    log.info("Participantes: %d linhas", len(part))

    mun = integrar_municipios(agregar_resultados_municipio(res), agregar_participantes_municipio(part))
    log.info("Municípios integrados: %d", len(mun))

    caminhos = {
        "resultados": out_dir / "resultados_2025.parquet",
        "participantes": out_dir / "participantes_2025.parquet",
        "municipios": out_dir / "municipios_2025.csv.gz",
    }
    res.to_parquet(caminhos["resultados"], compression="zstd", index=False)
    part.drop(columns=["Q005"]).to_parquet(caminhos["participantes"], compression="zstd", index=False)
    mun.to_csv(caminhos["municipios"], index=False, compression="gzip", float_format="%.6f")

    for nome, cam in caminhos.items():
        log.info("Gravado %s: %s (%.1f MB)", nome, cam.name, cam.stat().st_size / 1e6)
    log.info("Pipeline concluído em %.0f s", time.perf_counter() - t0)
    return caminhos


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL dos Microdados do ENEM 2025")
    parser.add_argument("--raw-dir", type=Path, default=DIR_RAW,
                        help="Diretório com RESULTADOS_2025.csv e PARTICIPANTES_2025.csv")
    parser.add_argument("--out-dir", type=Path, default=DIR_PROCESSED)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar(args.raw_dir, args.out_dir)


if __name__ == "__main__":
    main()
