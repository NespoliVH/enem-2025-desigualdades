"""Análises e visualizações das perguntas de pesquisa (RQ1 a RQ3).

Autor: Victor Hugo Nespoli · Bacharelado em Sistemas de Informação, Centro Universitário La Salle do Rio de Janeiro (UNILASALLE-RJ)
Disciplina: Linguagem de Programação (Análise e Visualização de Dados com Python) · 6º Período · 2026/2
Licença: MIT · Repositório: https://github.com/NespoliVH/enem-2025-desigualdades

Lê os dados tratados por ``src.etl`` e gera:

* tabelas-resumo em ``data/processed/tabelas/`` (CSV);
* métricas-chave em ``docs/assets/metricas.json`` (citadas no artigo);
* gráficos interativos Plotly em ``docs/assets/*.html`` (embutidos via iframe);
* uma figura estática de alta resolução (Matplotlib) em ``docs/assets/``.

Uso::

    python -m src.visualizacao
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from scipy import stats  # noqa: E402

from src.etl import AREAS, DIR_PROCESSED, RAIZ, d_de_cohen, resumo_descritivo  # noqa: E402

log = logging.getLogger("visualizacao")

DIR_ASSETS = RAIZ / "docs" / "assets"
DIR_TABELAS = DIR_PROCESSED / "tabelas"
MIN_VALIDOS_MUNICIPIO = 100  # municípios menores têm médias instáveis

# ---------------------------------------------------------------------------
# Identidade visual: cores fixas por entidade (paleta categórica validada
# para daltonismo nos pares adjacentes) e tipografia do artigo.
# ---------------------------------------------------------------------------

COR_REDE = {
    "Estadual": "#2a78d6",
    "Municipal": "#eda100",
    "Federal": "#1baf7a",
    "Privada": "#eb6834",
}
ORDEM_EXIBICAO_REDES = ["Estadual", "Municipal", "Federal", "Privada"]  # média crescente
COR_PRINCIPAL = "#2a78d6"
COR_SEM_VINCULO = "#898781"
TINTA = "#0b0b0b"
TINTA_SEC = "#52514e"
GRADE = "#e1e0d9"
FONTE = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

ROTULO_AREA = {**AREAS, "REDACAO": "Redação"}

ROTULOS_INDICADORES = {
    "MEDIA_GERAL": "Média geral",
    "MEDIA_REDACAO": "Média em redação",
    "TX_ABSTENCAO_TOTAL": "Abstenção",
    "RENDA_PC_MEDIANA": "Renda per capita (mediana)",
    "PCT_BAIXA_RENDA": "% baixa renda",
    "PCT_MAE_SEM_EM": "% mãe sem ensino médio",
    "PCT_SEM_INTERNET": "% sem internet",
    "PCT_SEM_COMPUTADOR": "% sem computador",
    "PCT_ESCOLA_PUBLICA": "% só escola pública",
    "PCT_PPI": "% pretos, pardos e indígenas",
    "PCT_TREINEIROS": "% treineiros",
}


def layout_base(titulo: str, **kwargs) -> dict:
    """Layout padrão: grade discreta, separadores decimais pt-BR, sem moldura.

    O título não é desenhado no gráfico, porque o artigo traz a legenda
    (``Figura N``) de cada figura. Ele fica registrado em ``layout.meta``.
    """
    return dict(
        meta={"titulo": titulo},
        font=dict(family=FONTE, size=12, color=TINTA_SEC),
        separators=",.",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=60, r=20, t=40, b=50),
        hoverlabel=dict(bgcolor="#ffffff", font=dict(family=FONTE, color=TINTA)),
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, xanchor="left"),
        **kwargs,
    )


def eixo(**kwargs) -> dict:
    return dict(gridcolor=GRADE, linecolor="#c3c2b7", zeroline=False, **kwargs)


def salvar_html(fig: go.Figure, nome: str) -> Path:
    """Grava a figura como HTML autocontido; o plotly.js fica em docs/assets/.

    O ``div_id`` fixo (em vez do UUID aleatório padrão do Plotly) torna o
    arquivo idêntico byte a byte entre execuções.
    """
    caminho = DIR_ASSETS / f"{nome}.html"
    fig.write_html(
        caminho,
        include_plotlyjs="directory",
        full_html=True,
        div_id=nome,
        config={"displaylogo": False, "responsive": True, "locale": "pt-BR",
                "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
    )
    log.info("Figura gravada: %s", caminho.name)
    return caminho


# ---------------------------------------------------------------------------
# RQ1: rede de ensino e território
# ---------------------------------------------------------------------------


def tabela_por_rede(validos: pd.DataFrame) -> pd.DataFrame:
    """Estatística descritiva da média geral por dependência administrativa."""
    linhas = {rede: resumo_descritivo(g["NU_MEDIA_GERAL"])
              for rede, g in validos.groupby("NO_REDE", observed=True)}
    return pd.DataFrame(linhas).T.loc[ORDEM_EXIBICAO_REDES]


def figura_box_rede(tab: pd.DataFrame) -> go.Figure:
    """Boxplot a partir de quartis pré-calculados (evita enviar milhões de pontos)."""
    fig = go.Figure()
    for rede, r in tab.iterrows():
        fig.add_trace(go.Box(
            name=rede, x=[rede],
            q1=[r.q1], median=[r.mediana], q3=[r.q3], mean=[r.media], sd=[r.dp],
            lowerfence=[max(r["min"], r.q1 - 1.5 * r.iqr)],
            upperfence=[min(r["max"], r.q3 + 1.5 * r.iqr)],
            marker_color=COR_REDE[rede], line=dict(width=2), fillcolor=COR_REDE[rede] + "33",
            boxmean="sd",
            hovertemplate=f"<b>{rede}</b><br>n = {int(r.n):,}".replace(",", ".")
            + "<extra></extra>",
        ))
    fig.update_layout(**layout_base("Média geral por rede da escola de conclusão (concluintes 2025)"),
                      showlegend=False, yaxis=eixo(title="Média geral (pontos)", range=[200, 900]),
                      xaxis=eixo(title=None, showgrid=False))
    return fig


def figura_areas_rede(validos: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Médias por área do conhecimento e redação, agrupadas por rede."""
    cols = [f"NU_NOTA_{a}" for a in [*AREAS, "REDACAO"]]
    medias = validos.groupby("NO_REDE", observed=True)[cols].mean().loc[ORDEM_EXIBICAO_REDES]
    medias.columns = [ROTULO_AREA[c.removeprefix("NU_NOTA_")] for c in cols]
    fig = go.Figure()
    for rede in ORDEM_EXIBICAO_REDES:
        fig.add_trace(go.Bar(
            name=rede, x=medias.columns, y=medias.loc[rede], marker_color=COR_REDE[rede],
            marker_line=dict(color="#ffffff", width=2),
            hovertemplate=f"<b>{rede}</b><br>%{{x}}: %{{y:.1f}}<extra></extra>",
        ))
    fig.update_layout(**layout_base("Média por área do conhecimento e rede"),
                      barmode="group", bargap=0.25,
                      yaxis=eixo(title="Média (pontos)", range=[0, 800]),
                      xaxis=eixo(showgrid=False))
    return fig, medias


def tabela_gap_uf(validos: pd.DataFrame) -> pd.DataFrame:
    """Diferença privada − estadual da média geral, por UF da escola."""
    sub = validos[validos["NO_REDE"].isin(["Estadual", "Privada"])]
    tab = (sub.groupby(["SG_UF_ESC", "NO_REDE"], observed=True)["NU_MEDIA_GERAL"]
           .mean().unstack()[["Estadual", "Privada"]])
    tab["GAP"] = tab["Privada"] - tab["Estadual"]
    return tab.sort_values("GAP")


def figura_gap_uf(tab: pd.DataFrame) -> go.Figure:
    """Gráfico de halteres (dumbbell): um par de pontos por UF."""
    ufs = tab.index.astype(str).tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=np.ravel(np.column_stack([tab["Estadual"], tab["Privada"], np.full(len(tab), np.nan)])),
        y=np.ravel(np.column_stack([ufs, ufs, [None] * len(ufs)])),
        mode="lines", line=dict(color="#c3c2b7", width=2), hoverinfo="skip", showlegend=False,
    ))
    for rede in ["Estadual", "Privada"]:
        fig.add_trace(go.Scatter(
            x=tab[rede], y=ufs, mode="markers", name=rede,
            marker=dict(color=COR_REDE[rede], size=10, line=dict(color="#ffffff", width=2)),
            customdata=tab["GAP"],
            hovertemplate=f"<b>%{{y}}</b> · {rede}: %{{x:.1f}}<br>Diferença: %{{customdata:.1f}}"
            "<extra></extra>",
        ))
    fig.update_layout(**layout_base("Diferença entre escolas privadas e estaduais por UF"),
                      height=720, xaxis=eixo(title="Média geral (pontos)"),
                      yaxis=eixo(title=None, showgrid=False, categoryorder="array",
                                 categoryarray=ufs))
    return fig


def figura_hist_estatica(validos: pd.DataFrame) -> Path:
    """Histogramas sobrepostos (densidade) de rede pública × privada, em PNG 200 dpi."""
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 10,
                         "axes.edgecolor": "#c3c2b7", "axes.labelcolor": TINTA_SEC,
                         "xtick.color": TINTA_SEC, "ytick.color": TINTA_SEC})
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
    bins = np.arange(250, 860, 10)
    for grupo, cor in [("Pública", COR_REDE["Estadual"]), ("Privada", COR_REDE["Privada"])]:
        notas = validos.loc[validos["NO_REDE_AGRUPADA"] == grupo, "NU_MEDIA_GERAL"]
        ax.hist(notas, bins=bins, density=True, histtype="stepfilled", alpha=0.25, color=cor)
        ax.hist(notas, bins=bins, density=True, histtype="step", linewidth=2, color=cor,
                label=f"{grupo} (n = {len(notas):,})".replace(",", "."))
        ax.axvline(notas.median(), color=cor, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Média geral (pontos)")
    ax.set_ylabel("Densidade")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.3f}".replace(".", ",")))
    ax.grid(axis="y", color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ["top", "right"]:
        ax.spines[lado].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    ax.set_title("Distribuição da média geral: rede pública × privada (linhas tracejadas = medianas)",
                 loc="left", fontsize=11, color=TINTA)
    fig.tight_layout()
    caminho = DIR_ASSETS / "fig_hist_publica_privada.png"
    fig.savefig(caminho)
    plt.close(fig)
    return caminho


# ---------------------------------------------------------------------------
# RQ2: perfil socioeconômico × desempenho (nível municipal)
# ---------------------------------------------------------------------------


def figura_dispersao_renda(mun: pd.DataFrame) -> tuple[go.Figure, dict]:
    """Dispersão municipal: % de baixa renda × média geral, com reta de MQO."""
    reg = stats.linregress(mun["PCT_BAIXA_RENDA"], mun["MEDIA_GERAL"])
    rho, _ = stats.spearmanr(mun["PCT_BAIXA_RENDA"], mun["MEDIA_GERAL"])
    xs = np.array([mun["PCT_BAIXA_RENDA"].min(), mun["PCT_BAIXA_RENDA"].max()])
    tamanho = np.clip(np.sqrt(mun["N_VALIDOS"]) / 4, 4, 30)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=mun["PCT_BAIXA_RENDA"], y=mun["MEDIA_GERAL"], mode="markers", name="Município",
        marker=dict(color=COR_PRINCIPAL, size=tamanho, opacity=0.55,
                    line=dict(color="#ffffff", width=1)),
        customdata=np.column_stack([mun["NO_MUNICIPIO"], mun["SG_UF"], mun["N_VALIDOS"],
                                    mun["NO_REGIAO"]]),
        hovertemplate="<b>%{customdata[0]} (%{customdata[1]})</b> · %{customdata[3]}<br>"
        "Baixa renda: %{x:.1%}<br>Média geral: %{y:.1f}<br>Participantes válidos: "
        "%{customdata[2]:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=xs, y=reg.intercept + reg.slope * xs, mode="lines", name="Reta de regressão (MQO)",
        line=dict(color=TINTA, width=2, dash="dash"), hoverinfo="skip",
    ))
    fig.update_layout(**layout_base(
        f"Municípios: proporção de baixa renda × média geral (ρ de Spearman = {rho:.2f})"
        .replace(".", ",")),
        xaxis=eixo(title="Inscritos com renda per capita até ½ salário mínimo", tickformat=".0%"),
        yaxis=eixo(title="Média geral (pontos)"))
    resumo = {"inclinacao": reg.slope, "intercepto": reg.intercept, "r2": reg.rvalue ** 2,
              "pearson": reg.rvalue, "spearman": rho, "n_municipios": len(mun)}
    return fig, resumo


def figura_correlacao(mun: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Mapa de calor da correlação de Spearman entre os indicadores municipais."""
    corr = mun[list(ROTULOS_INDICADORES)].corr(method="spearman")
    rot = [ROTULOS_INDICADORES[c] for c in corr.columns]
    escala = [[0.0, "#d03b3b"], [0.25, "#ec9a9a"], [0.5, "#f0efec"],
              [0.75, "#86b6ef"], [1.0, "#1c5cab"]]
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=rot, y=rot, zmin=-1, zmax=1, colorscale=escala,
        text=np.vectorize(lambda v: f"{v:.2f}".replace(".", ","))(corr.values),
        texttemplate="%{text}", textfont=dict(size=10),
        xgap=2, ygap=2, colorbar=dict(title="ρ", thickness=12),
        hovertemplate="%{y} × %{x}<br>ρ = %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(**layout_base("Correlação de Spearman entre indicadores municipais"),
                      height=640, xaxis=dict(tickangle=-40, showgrid=False),
                      yaxis=dict(autorange="reversed", showgrid=False))
    fig.update_layout(margin=dict(l=190, b=170, t=20))
    return fig, corr


def correlacao_por_regiao(mun: pd.DataFrame) -> pd.DataFrame:
    """Spearman (% baixa renda × média geral) dentro de cada região."""
    linhas = []
    for regiao, g in mun.groupby("NO_REGIAO", observed=True):
        rho, p = stats.spearmanr(g["PCT_BAIXA_RENDA"], g["MEDIA_GERAL"])
        linhas.append({"regiao": regiao, "n_municipios": len(g), "spearman": rho, "p_valor": p,
                       "media_geral_mediana": g["MEDIA_GERAL"].median(),
                       "pct_baixa_renda_mediana": g["PCT_BAIXA_RENDA"].median()})
    return pd.DataFrame(linhas).set_index("regiao")


# ---------------------------------------------------------------------------
# RQ3: abstenção
# ---------------------------------------------------------------------------


def figura_abstencao_uf(res: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Taxa de abstenção total (faltou aos dois dias) por UF de aplicação."""
    tab = (res.groupby("SG_UF_PROVA", observed=True)
           .agg(abstencao=("IN_AUSENTE_TOTAL", "mean"), falta_dia1=("IN_FALTOU_DIA1", "mean"),
                falta_dia2=("IN_FALTOU_DIA2", "mean"), inscritos=("IN_AUSENTE_TOTAL", "size"),
                regiao=("NO_REGIAO_PROVA", "first"))
           .sort_values("abstencao"))
    nacional = res["IN_AUSENTE_TOTAL"].mean()
    fig = go.Figure(go.Bar(
        x=tab.index.astype(str), y=tab["abstencao"], marker_color=COR_PRINCIPAL,
        marker_line=dict(color="#ffffff", width=2),
        customdata=np.column_stack([tab["falta_dia1"], tab["falta_dia2"], tab["inscritos"],
                                    tab["regiao"].astype(str)]),
        hovertemplate="<b>%{x}</b> · %{customdata[3]}<br>Abstenção total: %{y:.1%}<br>"
        "Faltou no 1º dia: %{customdata[0]:.1%}<br>Faltou no 2º dia: %{customdata[1]:.1%}<br>"
        "Inscritos: %{customdata[2]:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=nacional, line=dict(color=TINTA, dash="dash", width=1.5),
                  annotation_text=f"Brasil: {nacional:.1%}".replace(".", ","),
                  annotation_position="top left")
    fig.update_layout(**layout_base("Abstenção total por UF de aplicação da prova"),
                      showlegend=False, xaxis=eixo(showgrid=False),
                      yaxis=eixo(title="Faltou aos dois dias", tickformat=".0%", range=[0, 0.45]))
    return fig, tab


def figura_abstencao_vinculo(res: pd.DataFrame) -> tuple[go.Figure, pd.DataFrame]:
    """Abstenção por rede da escola, incluindo inscritos sem escola vinculada."""
    vinculo = res["NO_REDE"].astype("string").fillna("Sem escola vinculada")
    tab = res.groupby(vinculo)["IN_AUSENTE_TOTAL"].agg(["mean", "size"])
    ordem = [*ORDEM_EXIBICAO_REDES, "Sem escola vinculada"]
    tab = tab.loc[ordem]
    cores = [COR_REDE.get(r, COR_SEM_VINCULO) for r in ordem]
    fig = go.Figure(go.Bar(
        x=ordem, y=tab["mean"], marker_color=cores, marker_line=dict(color="#ffffff", width=2),
        text=[f"{v:.1%}".replace(".", ",") for v in tab["mean"]], textposition="outside",
        customdata=tab["size"],
        hovertemplate="<b>%{x}</b><br>Abstenção: %{y:.1%}<br>Inscritos: %{customdata:,.0f}"
        "<extra></extra>",
    ))
    fig.update_layout(**layout_base("Abstenção total por vínculo escolar do inscrito"),
                      showlegend=False, xaxis=eixo(showgrid=False),
                      yaxis=eixo(title="Faltou aos dois dias", tickformat=".0%", range=[0, 0.4]))
    return fig, tab


def figura_abstencao_treineiros(mun: pd.DataFrame) -> tuple[go.Figure, float]:
    """Dispersão municipal: % de treineiros × abstenção."""
    rho, _ = stats.spearmanr(mun["PCT_TREINEIROS"], mun["TX_ABSTENCAO_TOTAL"])
    fig = go.Figure(go.Scatter(
        x=mun["PCT_TREINEIROS"], y=mun["TX_ABSTENCAO_TOTAL"], mode="markers",
        marker=dict(color=COR_PRINCIPAL, size=np.clip(np.sqrt(mun["N_VALIDOS"]) / 4, 4, 30),
                    opacity=0.55, line=dict(color="#ffffff", width=1)),
        customdata=np.column_stack([mun["NO_MUNICIPIO"], mun["SG_UF"]]),
        hovertemplate="<b>%{customdata[0]} (%{customdata[1]})</b><br>Treineiros: %{x:.1%}<br>"
        "Abstenção: %{y:.1%}<extra></extra>",
    ))
    fig.update_layout(**layout_base(
        f"Municípios: proporção de treineiros × abstenção (ρ = {rho:.2f})".replace(".", ",")),
        showlegend=False,
        xaxis=eixo(title="Inscritos treineiros", tickformat=".0%"),
        yaxis=eixo(title="Faltou aos dois dias", tickformat=".0%"))
    return fig, rho


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------


def _json_seguro(obj):
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, pd.Series):
        return obj.to_dict()
    raise TypeError(type(obj))


def executar() -> dict:
    DIR_ASSETS.mkdir(parents=True, exist_ok=True)
    DIR_TABELAS.mkdir(parents=True, exist_ok=True)

    res = pd.read_parquet(DIR_PROCESSED / "resultados_2025.parquet")
    part = pd.read_parquet(DIR_PROCESSED / "participantes_2025.parquet")
    mun_todos = pd.read_csv(DIR_PROCESSED / "municipios_2025.csv.gz")
    mun = mun_todos[mun_todos["N_VALIDOS"] >= MIN_VALIDOS_MUNICIPIO].copy()
    validos = res[res["IN_VALIDO"]]
    com_rede = validos[validos["NO_REDE"].notna()]

    # RQ1
    tab_rede = tabela_por_rede(com_rede)
    tab_rede.to_csv(DIR_TABELAS / "rq1_resumo_por_rede.csv", float_format="%.4f")
    salvar_html(figura_box_rede(tab_rede), "fig1_box_rede")
    fig, medias_area = figura_areas_rede(com_rede)
    medias_area.to_csv(DIR_TABELAS / "rq1_medias_area_rede.csv", float_format="%.2f")
    salvar_html(fig, "fig2_areas_rede")
    gap = tabela_gap_uf(com_rede)
    gap.to_csv(DIR_TABELAS / "rq1_gap_privada_estadual_uf.csv", float_format="%.2f")
    salvar_html(figura_gap_uf(gap), "fig3_gap_uf")
    figura_hist_estatica(com_rede)
    loc = com_rede.groupby("NO_LOCALIZACAO", observed=True)["NU_MEDIA_GERAL"].agg(
        ["mean", "median", "std", "size"])

    # RQ2
    fig, reg = figura_dispersao_renda(mun)
    salvar_html(fig, "fig4_dispersao_renda")
    fig, corr = figura_correlacao(mun)
    corr.to_csv(DIR_TABELAS / "rq2_correlacao_spearman.csv", float_format="%.4f")
    salvar_html(fig, "fig5_correlacao")
    por_regiao = correlacao_por_regiao(mun)
    por_regiao.to_csv(DIR_TABELAS / "rq2_correlacao_por_regiao.csv", float_format="%.4f")

    # RQ3
    fig, abst_uf = figura_abstencao_uf(res)
    abst_uf.to_csv(DIR_TABELAS / "rq3_abstencao_uf.csv", float_format="%.4f")
    salvar_html(fig, "fig6_abstencao_uf")
    fig, abst_vinc = figura_abstencao_vinculo(res)
    abst_vinc.to_csv(DIR_TABELAS / "rq3_abstencao_vinculo.csv", float_format="%.4f")
    salvar_html(fig, "fig7_abstencao_vinculo")
    fig, rho_trein = figura_abstencao_treineiros(mun)
    salvar_html(fig, "fig8_abstencao_treineiros")

    pub = com_rede.loc[com_rede["NO_REDE_AGRUPADA"] == "Pública", "NU_MEDIA_GERAL"]
    priv = com_rede.loc[com_rede["NO_REDE_AGRUPADA"] == "Privada", "NU_MEDIA_GERAL"]
    est = com_rede.loc[com_rede["NO_REDE"] == "Estadual", "NU_MEDIA_GERAL"]
    fed = com_rede.loc[com_rede["NO_REDE"] == "Federal", "NU_MEDIA_GERAL"]

    metricas = {
        "base": {
            "inscritos": len(res),
            "validos": int(res["IN_VALIDO"].sum()),
            "validos_com_rede": len(com_rede),
            "eliminados": int(res["IN_ELIMINADO"].sum()),
            "municipios": len(mun_todos),
            "municipios_analise": len(mun),
            "razao_inscritos_min": mun_todos["RAZAO_INSCRITOS"].min(),
            "razao_inscritos_max": mun_todos["RAZAO_INSCRITOS"].max(),
            "status_redacao": validos["TP_STATUS_REDACAO"].value_counts().to_dict(),
        },
        "geral": resumo_descritivo(validos["NU_MEDIA_GERAL"]),
        "rq1": {
            "por_rede": tab_rede[["n", "media", "mediana", "dp", "q1", "q3"]].to_dict("index"),
            "medias_area": medias_area.round(2).to_dict("index"),
            "localizacao": loc.to_dict("index"),
            "d_privada_estadual": d_de_cohen(priv, est),
            "d_federal_estadual": d_de_cohen(fed, est),
            "d_privada_publica": d_de_cohen(priv, pub),
            "d_urbana_rural": d_de_cohen(
                com_rede.loc[com_rede["NO_LOCALIZACAO"] == "Urbana", "NU_MEDIA_GERAL"],
                com_rede.loc[com_rede["NO_LOCALIZACAO"] == "Rural", "NU_MEDIA_GERAL"]),
            "gap_uf": gap.round(2).to_dict("index"),
        },
        "rq2": {
            "regressao": reg,
            "por_regiao": por_regiao.to_dict("index"),
            "corr_media_geral": corr["MEDIA_GERAL"].to_dict(),
            "perfil_nacional": part[["IN_BAIXA_RENDA", "IN_MAE_SEM_EM", "IN_SEM_INTERNET",
                                     "IN_SEM_COMPUTADOR", "IN_ESCOLA_PUBLICA", "IN_PPI",
                                     "IN_TREINEIRO", "IN_CONCLUINTE_2025"]]
            .astype("float64").mean().to_dict(),
            "renda_pc_mediana_nacional": float(part["NU_RENDA_PC"].median()),
        },
        "rq3": {
            "abstencao_total": res["IN_AUSENTE_TOTAL"].mean(),
            "falta_dia1": res["IN_FALTOU_DIA1"].mean(),
            "falta_dia2": res["IN_FALTOU_DIA2"].mean(),
            "por_uf": abst_uf[["abstencao", "falta_dia1", "falta_dia2"]].to_dict("index"),
            "por_vinculo": abst_vinc["mean"].to_dict(),
            "spearman_treineiros": rho_trein,
            "corr_abstencao": corr["TX_ABSTENCAO_TOTAL"].to_dict(),
        },
    }
    with open(DIR_ASSETS / "metricas.json", "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2, default=_json_seguro)
    log.info("Métricas gravadas em docs/assets/metricas.json")
    return metricas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    executar()
