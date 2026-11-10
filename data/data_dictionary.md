# Dicionário de dados

Metadados das bases **processadas** pelo pipeline (`python -m src.etl`). As
variáveis de origem seguem a nomenclatura do *Dicionário de Dados dos
Microdados do ENEM 2025* (INEP), e as variáveis derivadas criadas neste projeto
estão marcadas como **(derivada)**.

- **Fonte:** INEP. *Microdados do Enem 2025*. Brasília: Inep, 2026.
  <https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem>
- **Licença dos dados processados:** CC BY 4.0
- **Cobertura:** 4.810.772 inscritos no ENEM 2025, em 1.805 municípios de aplicação.
- **Convenções:** prefixos do INEP — `NU_` número/medida, `TP_` código
  categórico, `IN_` indicador binário, `CO_` código, `NO_` nome, `SG_` sigla,
  `Q0xx` questão do questionário socioeconômico. `NaN`/vazio = ausente.

---

## 1. `data/processed/resultados_2025.parquet`

**Granularidade:** uma linha por inscrito (4.810.772 linhas). Formato Apache
Parquet com compressão Zstandard. **Não** possui chave de ligação com a base de
participantes (LGPD).

| Variável | Significado | Tipo | Formato / domínio |
|---|---|---|---|
| `SG_UF_ESC` | UF da escola de conclusão do ensino médio | categórico | sigla (ex.: `SP`); ausente para não concluintes |
| `CO_MUNICIPIO_PROVA` | Município de aplicação da prova | inteiro (int32) | código IBGE de 7 dígitos |
| `NO_MUNICIPIO_PROVA` | Nome do município de aplicação | categórico | texto |
| `CO_UF_PROVA` | UF de aplicação | inteiro (int8) | código IBGE de 2 dígitos (1º dígito = região) |
| `SG_UF_PROVA` | UF de aplicação | categórico | sigla |
| `TP_PRESENCA_CN`, `_CH`, `_LC`, `_MT` | Presença em cada prova objetiva | inteiro (int8) | 0 = faltou; 1 = presente; 2 = eliminado |
| `NU_NOTA_CN`, `_CH`, `_LC`, `_MT` | Nota na prova objetiva (escala TRI) | real (float32) | pontos; ausente se não presente |
| `TP_STATUS_REDACAO` | Situação da redação | real (float32) | 1 = sem problemas; 2 = anulada; 3 = cópia do texto motivador; 4 = em branco; 6 = fuga ao tema; 7 = não atendimento ao tipo textual; 8 = texto insuficiente; 9 = parte desconectada |
| `NU_NOTA_COMP1` … `NU_NOTA_COMP5` | Nota final em cada competência da redação | real (float32) | 0 a 200 |
| `NU_NOTA_REDACAO` | Nota final da redação | real (float32) | 0 a 1000 |
| `IN_FALTOU_DIA1` **(derivada)** | Faltou às duas provas do 1º dia (LC e CH) | booleano | `True`/`False` |
| `IN_FALTOU_DIA2` **(derivada)** | Faltou às duas provas do 2º dia (CN e MT) | booleano | `True`/`False` |
| `IN_AUSENTE_TOTAL` **(derivada)** | Faltou aos dois dias (abstenção total) | booleano | `True`/`False` |
| `IN_ELIMINADO` **(derivada)** | Eliminado em ao menos uma prova | booleano | `True`/`False` |
| `IN_VALIDO` **(derivada)** | Presente nas 4 objetivas **e** com nota de redação | booleano | `True`/`False` |
| `NU_MEDIA_OBJETIVAS` **(derivada)** | Média simples das 4 provas objetivas | real (float32) | pontos; só para `IN_VALIDO` |
| `NU_MEDIA_GERAL` **(derivada)** | Média simples das 4 objetivas e da redação | real (float32) | pontos; só para `IN_VALIDO` |
| `NO_REDE` **(derivada)** | Dependência administrativa da escola (de `TP_DEPENDENCIA_ADM_ESC`) | categórico ordenado | Federal, Estadual, Municipal, Privada; ausente para não concluintes |
| `NO_REDE_AGRUPADA` **(derivada)** | Rede agrupada | categórico | Pública (federal + estadual + municipal), Privada |
| `NO_LOCALIZACAO` **(derivada)** | Localização da escola (de `TP_LOCALIZACAO_ESC`) | categórico | Urbana, Rural |
| `NO_REGIAO_PROVA` **(derivada)** | Região do município de aplicação | categórico | Norte, Nordeste, Sudeste, Sul, Centro-Oeste |

> A escola de conclusão só está disponível para os inscritos identificados no
> Censo Escolar 2025 como possíveis concluintes do ensino médio (39,7% dos
> participantes válidos). Egressos e treineiros não têm escola vinculada.

## 2. `data/processed/participantes_2025.parquet`

**Granularidade:** uma linha por inscrito (4.810.772 linhas). Formato Parquet (Zstandard).

| Variável | Significado | Tipo | Formato / domínio |
|---|---|---|---|
| `TP_FAIXA_ETARIA` | Faixa etária | inteiro (int8) | 1 = menor de 17 anos; 2 a 10 = 17 a 25 anos; 11 a 20 = faixas quinquenais de 26–30 a maior de 70 |
| `TP_SEXO` | Sexo | categórico | M, F |
| `TP_COR_RACA` | Cor/raça autodeclarada | inteiro (int8) | 0 = não declarado; 1 = branca; 2 = preta; 3 = parda; 4 = amarela; 5 = indígena; 6 = não dispõe da informação |
| `TP_ST_CONCLUSAO` | Situação de conclusão do ensino médio | inteiro (int8) | 1 = já concluiu; 2 = conclui em 2025; 3 = conclui após 2025; 4 = não concluiu e não está cursando |
| `IN_TREINEIRO` | Fez a prova apenas para treinar | booleano | `True`/`False` |
| `CO_MUNICIPIO_PROVA` | Município de aplicação da prova | inteiro (int32) | código IBGE de 7 dígitos |
| `SG_UF_PROVA` | UF de aplicação | categórico | sigla |
| `Q002` | Escolaridade da mãe ou responsável | categórico | A = nunca estudou … G = pós-graduação; H = não sei |
| `Q007` | Renda mensal da família | categórico | A = nenhuma renda; B = até R$ 1.518,00; … Q = acima de R$ 30.360,00 (17 faixas) |
| `Q020` | Internet wi-fi em casa | categórico | A = não; B = sim |
| `Q021` | Computador/notebook em casa | categórico | A = não; B a E = um a quatro ou mais |
| `Q023` | Tipo de escola no ensino médio | categórico | A = somente pública; B a E = combinações com privada; F = não frequentou |
| `NU_RENDA_PC` **(derivada)** | Renda familiar *per capita* estimada | real (float32) | R$/mês = ponto médio da faixa Q007 ÷ moradores (Q005); faixa aberta = R$ 30.360 × 1,25 |
| `IN_BAIXA_RENDA` **(derivada)** | Renda *per capita* ≤ ½ salário mínimo (R$ 759,00) | booleano | `True`/`False` |
| `IN_MAE_SEM_EM` **(derivada)** | Mãe sem ensino médio completo (Q002 ∈ A–D) | real (0/1) | ausente se Q002 = H |
| `IN_SEM_INTERNET` **(derivada)** | Sem internet wi-fi (Q020 = A) | booleano | `True`/`False` |
| `IN_SEM_COMPUTADOR` **(derivada)** | Sem computador (Q021 = A) | booleano | `True`/`False` |
| `IN_ESCOLA_PUBLICA` **(derivada)** | Cursou o EM somente em escola pública (Q023 = A) | real (0/1) | ausente se Q023 = F |
| `IN_PPI` **(derivada)** | Autodeclarado preto, pardo ou indígena | real (0/1) | ausente se `TP_COR_RACA` ∈ {0, 6} |
| `IN_CONCLUINTE_2025` **(derivada)** | Conclui o ensino médio em 2025 | booleano | `True`/`False` |

## 3. `data/processed/municipios_2025.csv.gz`

**Granularidade:** um município de aplicação por linha (1.805 linhas). CSV
UTF-8, separador vírgula, decimal ponto, compressão gzip. Resulta da agregação
das duas bases acima por `CO_MUNICIPIO_PROVA` (junção 1:1 validada).

| Variável | Significado | Tipo | Formato |
|---|---|---|---|
| `CO_MUNICIPIO_PROVA` | Código IBGE do município | inteiro | 7 dígitos |
| `NO_MUNICIPIO`, `SG_UF`, `CO_UF`, `NO_REGIAO` | Identificação territorial | texto/inteiro | — |
| `N_INSCRITOS_RES` | Inscritos na base de resultados | inteiro | contagem |
| `N_INSCRITOS_PART` | Inscritos na base de participantes | inteiro | contagem |
| `RAZAO_INSCRITOS` | `N_INSCRITOS_RES / N_INSCRITOS_PART` (verificação de consistência) | real | 1,0 em todos os municípios |
| `N_VALIDOS` | Participantes válidos | inteiro | contagem |
| `TX_ABSTENCAO_TOTAL` | Proporção que faltou aos dois dias | real | 0 a 1 |
| `TX_FALTA_DIA1`, `TX_FALTA_DIA2` | Proporção que faltou em cada dia | real | 0 a 1 |
| `MEDIA_OBJETIVAS`, `MEDIA_GERAL`, `MEDIA_MT`, `MEDIA_REDACAO` | Médias dos participantes válidos | real | pontos |
| `RENDA_PC_MEDIANA` | Mediana da renda *per capita* estimada | real | R$/mês |
| `PCT_BAIXA_RENDA`, `PCT_MAE_SEM_EM`, `PCT_SEM_INTERNET`, `PCT_SEM_COMPUTADOR`, `PCT_ESCOLA_PUBLICA`, `PCT_PPI`, `PCT_TREINEIROS` | Proporção de inscritos com cada característica | real | 0 a 1 |

## 4. `data/processed/tabelas/*.csv`

Tabelas-resumo geradas por `python -m src.visualizacao`, usadas no artigo:

| Arquivo | Conteúdo |
|---|---|
| `rq1_resumo_por_rede.csv` | Estatística descritiva da média geral por rede |
| `rq1_medias_area_rede.csv` | Médias por área do conhecimento e rede |
| `rq1_gap_privada_estadual_uf.csv` | Médias estadual e privada e a diferença entre elas, por UF da escola |
| `rq2_correlacao_spearman.csv` | Matriz de correlação de Spearman (municípios com ≥ 100 válidos) |
| `rq2_correlacao_por_regiao.csv` | ρ (% baixa renda × média geral) por região |
| `rq3_abstencao_uf.csv` | Abstenção total e por dia, por UF de aplicação |
| `rq3_abstencao_vinculo.csv` | Abstenção por rede da escola / sem vínculo |
