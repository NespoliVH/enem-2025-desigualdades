# Desigualdades no ENEM 2025: Rede de Ensino, Território e Perfil Socioeconômico

![Dados](https://img.shields.io/badge/dados-INEP%20%C2%B7%20ENEM%202025-1e3a8a)
![Python](https://img.shields.io/badge/python-3.14-3776ab)
![Código](https://img.shields.io/badge/c%C3%B3digo-MIT-green)
![Texto e dados](https://img.shields.io/badge/texto%20e%20dados-CC%20BY%204.0-lightgrey)
![FAIR](https://img.shields.io/badge/FAIR-F%20%C2%B7%20A%20%C2%B7%20I%20%C2%B7%20R-2563eb)

**Artigo publicado:** <https://nespolivh.github.io/enem-2025-desigualdades/>

| | |
|---|---|
| **Autor** | Victor Hugo Nespoli |
| **Instituição** | Centro Universitário La Salle do Rio de Janeiro (UNILASALLE-RJ) — Bacharelado em Sistemas de Informação |
| **Disciplina** | Linguagem de Programação (Análise e Visualização de Dados com Python) — 6º Período |
| **Semestre** | 2026/2 |
| **Fonte dos dados** | INEP, *Microdados do Enem 2025* — <https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem> |
| **Palavras-chave** | ENEM 2025; Desigualdade educacional; Microdados do INEP; Análise exploratória de dados; Python; Princípios FAIR |

## Resumo executivo

Este projeto analisa os **Microdados do ENEM 2025** (4.810.772 inscritos) com um
pipeline determinístico em Python, para responder a três perguntas de pesquisa:

- **RQ1:** Como o desempenho varia entre as redes de ensino (federal, estadual,
  municipal e privada), entre escolas urbanas e rurais e entre as UFs?
- **RQ2:** Qual é a associação, no nível municipal, entre o perfil
  socioeconômico dos inscritos e o desempenho médio?
- **RQ3:** Onde se concentra a abstenção e como ela se relaciona com o vínculo
  escolar e com o perfil dos municípios?

**Principais achados**

- A média geral da rede privada (610,5) supera a da estadual (497,1) em
  **113 pontos** (*d* de Cohen = 1,36). A maior distância está na redação
  (197 pontos), e entre as UFs ela varia de 88 (PR e SP) a 147 pontos (PI).
- A proporção de inscritos de baixa renda explica **71%** da variação da média
  geral entre municípios (ρ de Spearman = −0,86).
- **27,7%** dos inscritos faltaram aos dois dias, com 40,0% no Amazonas e 26,0%
  entre concluintes da rede estadual, contra 5,5% na rede privada.

> As bases `PARTICIPANTES` e `RESULTADOS` **não têm chave de ligação** (LGPD).
> Por isso, elas são integradas apenas de forma agregada, pelo município de
> aplicação da prova. As correlações resultantes são ecológicas.

## Estrutura do repositório

```
enem-2025-desigualdades/
├── README.md
├── LICENSE                         # MIT (código) + CC BY 4.0 (texto e dados)
├── requirements.txt                # dependências congeladas (pip freeze)
├── .gitignore
├── data/
│   ├── raw/download_dados.py       # baixa os microdados do INEP (~2,5 GB)
│   ├── processed/                  # Parquet e CSV.gz gerados pelo ETL
│   │   └── tabelas/                # tabelas-resumo das RQs
│   └── data_dictionary.md          # dicionário de variáveis (FAIR)
├── notebooks/
│   └── analise_exploratoria.ipynb  # exploração e validação
├── src/
│   ├── __init__.py
│   ├── etl.py                      # extração, limpeza, métricas e agregações
│   └── visualizacao.py             # análises e figuras das RQs
└── docs/                           # artigo publicado no GitHub Pages
    ├── index.html
    └── assets/                     # gráficos Plotly, figura PNG e métricas
```

## Como reproduzir

Pré-requisitos: Python 3.14 e cerca de 5 GB livres em disco.

```bash
# 1. Clonar o repositório
git clone https://github.com/NespoliVH/enem-2025-desigualdades.git
cd enem-2025-desigualdades

# 2. Ambiente virtual e dependências
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Dados brutos (portal do INEP, sem autenticação)
python data/raw/download_dados.py

# 4. Pipeline ETL -> data/processed/
python -m src.etl

# 5. Tabelas, métricas e figuras -> data/processed/tabelas/ e docs/assets/
python -m src.visualizacao
```

Se os CSVs já estiverem em outra pasta, use `python -m src.etl --raw-dir CAMINHO`.
O ETL completo leva cerca de 20 segundos em um computador com SSD e 16 GB de RAM.
Para visualizar o artigo localmente, rode `python -m http.server --directory docs`
e acesse <http://localhost:8000>.

## Decisões metodológicas

| Tema | Decisão |
|---|---|
| Leitura | `latin-1`, separador `;`, leitura em blocos de 500 mil linhas, 22 de 70 colunas, tipos explícitos |
| Valores ausentes | Nota ausente = falta ou eliminação. Não há imputação. "Não sei" e "não declarado" são tratados como ausentes nos indicadores |
| Participante válido | Presente nas 4 provas objetivas e com nota de redação (3.244.348) |
| Média geral | Média simples das 4 objetivas e da redação |
| Renda *per capita* | Ponto médio da faixa Q007 ÷ moradores (Q005). Baixa renda = até ½ salário mínimo (R$ 759) |
| Integração | Agregação por `CO_MUNICIPIO_PROVA`, junção 1:1 validada. Análise com municípios com ≥ 100 válidos |
| Inferência | Tamanho de efeito (*d* de Cohen) e correlações, em vez de valores-p (n de milhões) |

## Licença e citação

- Código: [MIT](LICENSE). Texto, dicionário e dados processados: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt_BR).
- Dados originais: INSTITUTO NACIONAL DE ESTUDOS E PESQUISAS EDUCACIONAIS
  ANÍSIO TEIXEIRA (INEP). *Microdados do Enem 2025*. Brasília: Inep, 2026.
