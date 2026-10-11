# Desalagaju — Previsão de Alagamentos em Aracaju

## 1. Sobre o projeto

O **Desalagaju** é um projeto de análise de dados e aprendizado de máquina que busca investigar a relação entre precipitação, nível da maré e ocorrência de alagamentos em Aracaju, Sergipe.

O objetivo é preparar uma base de dados ambientais e avaliar modelos de classificação capazes de estimar a ocorrência de alagamentos a partir de variáveis relacionadas às condições ambientais.

O projeto utiliza dados de precipitação do Centro Nacional de Monitoramento e Alertas de Desastres Naturais (CEMADEN), dados de maré e registros de ocorrências de alagamentos.

### Objetivos específicos

- Organizar e processar os dados de precipitação.
- Calcular atributos relacionados à chuva acumulada nas três horas anteriores.
- Investigar a relação entre precipitação, maré e alagamentos.
- Integrar as diferentes fontes de dados em uma base comum.
- Implementar e comparar modelos de classificação.
- Avaliar os resultados utilizando métricas estatísticas.
- Documentar as limitações dos dados e dos modelos.

## 2. Estrutura do repositório

A estrutura atual do projeto é:

```text
Desalagaju/
├── data/
│   ├── raw/
│   │   └── cemaden/
│   │       ├── 2025/
│   │       └── 2026/
│   └── processed/
├── notebooks/
├── src/
│   └── engenharia_atributos.py
├── tests/
├── .gitignore
├── README.md
└── requirements.txt
```

### Descrição dos diretórios e arquivos

| Diretório/arquivo | Finalidade |
|---|---|
| `data/raw/` | Armazenar os dados originais. |
| `data/raw/cemaden/` | Armazenar os arquivos mensais de precipitação do CEMADEN. |
| `data/processed/` | Armazenar os dados gerados pelo processamento. |
| `notebooks/` | Desenvolver análises exploratórias e experimentos. |
| `src/` | Armazenar os scripts do projeto. |
| `src/engenharia_atributos.py` | Processar os dados de precipitação e calcular atributos de chuva acumulada. |
| `tests/` | Organizar testes automatizados, à medida que forem implementados. |
| `.gitignore` | Definir arquivos e diretórios que não devem ser versionados. |
| `requirements.txt` | Registrar as dependências Python. |

Os diretórios `notebooks/`, `tests/` e `data/processed/` podem estar vazios em um clone novo do repositório. Os arquivos de dados e os resultados gerados localmente não são versionados pelas regras atuais do `.gitignore`.

## 3. Fontes de dados

### 3.1. Dados de precipitação — CEMADEN

Os dados atualmente processados foram obtidos do CEMADEN e estão organizados em arquivos CSV mensais referentes a 2025 e 2026.

O conjunto utilizado contém registros de três estações pluviométricas:

- `280030801A`
- `280030802A`
- `280030803A`

Os arquivos originais utilizam ponto e vírgula como separador de campos e vírgula como separador decimal.

As principais colunas são:

| Coluna | Descrição |
|---|---|
| `municipio` | Município da estação. |
| `codEstacao` | Código identificador da estação. |
| `uf` | Unidade federativa. |
| `nomeEstacao` | Nome da estação. |
| `latitude` | Latitude da estação. |
| `longitude` | Longitude da estação. |
| `datahora` | Data e hora informadas no arquivo original. |
| `valorMedida` | Valor informado pelo sistema de monitoramento. |

A interpretação de `valorMedida`, incluindo sua semântica temporal e a forma adequada de calcular acumulações, deve ser confirmada na documentação da fonte. A implementação atual utiliza uma regra de acumulação e validação que ainda precisa de avaliação metodológica.

### 3.2. Dados de maré

Os dados de maré serão utilizados para investigar a possível associação entre o nível da água e a ocorrência de alagamentos.

A fonte, a frequência das medições, o período de cobertura e os procedimentos de integração deverão ser documentados quando essa etapa for concluída.

### 3.3. Registros de alagamentos

Os registros de alagamentos serão utilizados para construir a variável-alvo dos modelos de classificação.

A identificação das ocorrências deverá se apoiar em fontes verificáveis, como registros oficiais, notícias ou outras bases confiáveis.

A ausência de uma notícia ou de um registro localizado não comprova, por si só, que não ocorreu alagamento. Os casos negativos deverão ser definidos por um procedimento confiável de rotulagem.

## 4. Engenharia de atributos

### 4.1. Script atual

O processamento da precipitação está implementado em:

```text
src/engenharia_atributos.py
```

O script procura arquivos CSV dentro de `data/raw/cemaden/` e de suas subpastas, lê os registros, organiza as observações por estação e calcula atributos de precipitação acumulada.

O resultado é salvo em:

```text
data/processed/chuva_acumulada_3h.csv
```

O script utiliza caminhos relativos à raiz do projeto, evitando depender de um caminho específico do computador de quem executa o código.

### 4.2. Chuva acumulada em três horas

O atributo de precipitação acumulada considera a janela temporal:

\[
(t-3h,\ t]
\]

Isso significa que são considerados os registros posteriores ao limite inicial da janela até o instante final, incluindo o instante final.

O processamento é realizado separadamente para cada estação, respeitando a ordem temporal dos registros.

O script também cria indicadores para avaliar a cobertura temporal das observações utilizadas no cálculo.

### 4.3. Colunas produzidas

O arquivo processado contém as colunas originais e atributos adicionais.

| Coluna | Finalidade |
|---|---|
| `chuva_acumulada_3h_mm` | Estimativa da precipitação acumulada na janela de três horas, em milímetros. |
| `janela_3h_valida` | Indica se a janela atende aos critérios de validade implementados. |
| `n_medicoes_3h` | Quantidade de medições consideradas na janela. |
| `maior_intervalo_min_3h` | Maior intervalo temporal entre medições na janela, em minutos. |
| `datahora_utc` | Data e hora interpretadas em UTC pelo processamento. |
| `datahora_local` | Data e hora convertidas para o fuso local de Aracaju. |
| `arquivo_origem` | Identificação do arquivo de origem do registro. |

### 4.4. Critérios atuais de validação

A implementação utiliza critérios provisórios para identificar janelas com cobertura temporal insuficiente:

- Quando há registros de precipitação positiva na janela, os intervalos entre observações relevantes devem respeitar o limite de dez minutos.
- Quando todos os valores da janela são zero, é permitido um intervalo de até sessenta minutos.
- As janelas que não atendem aos critérios são marcadas como inválidas, e a acumulação correspondente recebe valor ausente.

Esses critérios são decisões metodológicas em avaliação. Eles não garantem, por si só, que todos os valores acumulados correspondam perfeitamente à precipitação real.

**Importante:** uma janela inválida não significa que não houve chuva. Valores ausentes não devem ser substituídos automaticamente por zero.

## 5. Resultados atuais do processamento

Na execução verificada, o script reuniu **32.757 registros**, referentes a três estações pluviométricas.

Segundo os critérios de validação atualmente implementados, os resultados foram:

| Resultado | Quantidade | Proporção |
|---|---:|---:|
| Janelas válidas | 22.536 | 68,80% |
| Janelas inválidas | 10.221 | 31,20% |
| Total | 32.757 | 100% |

### Cobertura por estação

| Estação | Registros | Janelas válidas | Proporção válida |
|---|---:|---:|---:|
| `280030801A` | 12.232 | 8.461 | 69,17% |
| `280030802A` | 17.487 | 12.758 | 72,96% |
| `280030803A` | 3.038 | 1.317 | 43,35% |

A estação `280030802A` apresenta a maior proporção de janelas válidas, enquanto a estação `280030803A` apresenta a menor.

Essa diferença de cobertura deve ser investigada antes da construção da base final. Os resultados representam a validade segundo os critérios atuais, e não a proporção de períodos com chuva ou alagamento.

Esses números correspondem à execução verificada e poderão mudar se os arquivos de entrada ou os critérios de validação forem modificados.

## 6. Requisitos e execução

### 6.1. Requisitos

- Python instalado.
- Git, caso o repositório seja obtido por clonagem.
- Dependências registradas em `requirements.txt`.
- Arquivos CSV do CEMADEN disponíveis nos diretórios esperados pelo script.

### 6.2. Abrir o projeto

Abra o terminal na raiz do repositório, isto é, na pasta que contém `README.md`, `requirements.txt` e o diretório `src/`.

Os comandos abaixo são para o PowerShell do Windows.

### 6.3. Criar o ambiente virtual

```powershell
python -m venv .venv
```

Ative o ambiente:

```powershell
.venv\Scripts\Activate.ps1
```

Se o ambiente já estiver ativado, não é necessário ativá-lo novamente.

### 6.4. Instalar as dependências

```powershell
python -m pip install -r requirements.txt
```

Para verificar se existem dependências incompatíveis:

```powershell
python -m pip check
```

### 6.5. Executar a engenharia de atributos

```powershell
python src\engenharia_atributos.py
```

O script deverá processar os arquivos encontrados e gerar:

```text
data/processed/chuva_acumulada_3h.csv
```

A execução depende da presença dos arquivos de entrada e das dependências necessárias.

### 6.6. Conferir o arquivo gerado

Para verificar se o arquivo existe:

```powershell
Test-Path "data\processed\chuva_acumulada_3h.csv"
```

Para conferir as dimensões e as colunas do arquivo:

```powershell
python -c "import pandas as pd; d = pd.read_csv('data/processed/chuva_acumulada_3h.csv'); print('Dimensões:', d.shape); print('Colunas:', d.columns.tolist())"
```

Esses comandos permitem verificar a existência e a estrutura do resultado, mas não substituem a validação metodológica dos cálculos.

## 7. Divisão de responsabilidades

O projeto está dividido entre cinco integrantes.

### Integrante 1 — Engenharia de atributos e preparação dos dados

Responsável pelo processamento e pela preparação dos dados ambientais.

Tarefas:

- Organizar os dados brutos do CEMADEN.
- Calcular a precipitação acumulada em três horas.
- Documentar e revisar os critérios de validade das janelas.
- Investigar lacunas e diferenças de cobertura entre as estações.
- Obter e integrar os dados de maré.
- Participar da construção da base integrada.
- Documentar as decisões metodológicas e as limitações da preparação dos dados.

**Entrega esperada:** dados ambientais processados, documentação da metodologia e base preparada para integração com a variável-alvo.

### Integrante 2 — Regressão logística

Tarefas:

- Implementar o classificador de regressão logística.
- Definir o pré-processamento necessário.
- Treinar o modelo com a base integrada.
- Registrar os parâmetros e as configurações utilizadas.
- Gerar previsões e disponibilizar os resultados para comparação.

**Entrega esperada:** implementação reproduzível da regressão logística e resultados de avaliação.

### Integrante 3 — Árvore de decisão

Tarefas:

- Implementar o classificador de árvore de decisão.
- Avaliar parâmetros como profundidade máxima e critérios de divisão.
- Treinar e avaliar o modelo.
- Registrar as configurações utilizadas.
- Disponibilizar previsões e resultados para comparação.

**Entrega esperada:** implementação reproduzível da árvore de decisão e resultados de avaliação.

### Integrante 4 — Máquina de vetores de suporte (SVM)

Tarefas:

- Implementar o classificador SVM.
- Definir o pré-processamento necessário, incluindo padronização quando apropriada.
- Avaliar configurações de kernel e hiperparâmetros.
- Treinar e avaliar o modelo.
- Disponibilizar previsões e resultados para comparação.

**Entrega esperada:** implementação reproduzível do SVM e resultados de avaliação.

### Integrante 5 — Métricas e comparação estatística

Tarefas:

- Definir um protocolo comum de avaliação.
- Calcular métricas de desempenho para os modelos.
- Organizar tabelas e gráficos comparativos.
- Analisar as diferenças entre os resultados.
- Aplicar procedimentos estatísticos de comparação quando forem adequados ao desenho experimental.
- Documentar resultados, limitações e conclusões.

**Entrega esperada:** relatório comparativo dos modelos, com métricas, análises e conclusões fundamentadas.

## 8. Construção da base integrada

A base final deverá reunir atributos ambientais e uma variável-alvo que indique a ocorrência de alagamento.

Entre os atributos candidatos estão:

- Precipitação acumulada nas três horas anteriores.
- Nível da maré no instante correspondente.
- Outras variáveis ambientais ou temporais, caso existam dados confiáveis e justificativa metodológica.

A variável-alvo deverá seguir critérios documentados:

- `alagamento = 1`: ocorrência confirmada segundo o procedimento de rotulagem definido pelo grupo.
- `alagamento = 0`: ausência de ocorrência estabelecida com base em fonte ou procedimento confiável.

Casos sem evidência suficiente deverão permanecer sem rótulo ou ser tratados conforme um procedimento de análise previamente definido.

### Alinhamento temporal

A integração deverá considerar a data e hora dos registros, a localização das estações e a resolução temporal das fontes.

O grupo deverá documentar:

- Qual instante representa cada observação.
- Qual intervalo temporal será usado para associar as variáveis aos eventos.
- Como serão tratados atrasos entre chuva, maré e ocorrência de alagamento.
- Como serão tratados valores ausentes e registros duplicados.
- Como será evitado o uso de informações futuras no momento da previsão.

## 9. Treinamento e avaliação dos modelos

Os três classificadores deverão utilizar a mesma definição da variável-alvo, os mesmos atributos elegíveis e um protocolo de avaliação comparável.

### Cuidados metodológicos

- Evitar vazamento de dados entre treinamento e teste.
- Considerar uma separação temporal se o objetivo for estimar o desempenho em períodos futuros.
- Ajustar transformações e hiperparâmetros usando somente os dados de treinamento.
- Aplicar padronização nos modelos que necessitam dela, sem utilizar informações do conjunto de teste.
- Considerar o possível desequilíbrio entre as classes.
- Avaliar os modelos no mesmo conjunto de teste.

### Métricas sugeridas

| Métrica | Finalidade |
|---|---|
| Acurácia | Proporção total de classificações corretas. |
| Precisão | Proporção de previsões positivas que correspondem a ocorrências positivas. |
| Revocação (recall) | Proporção de ocorrências positivas identificadas. |
| F1-score | Média harmônica entre precisão e revocação. |
| Matriz de confusão | Quantifica verdadeiros e falsos positivos e negativos. |

A acurácia não deve ser usada isoladamente, especialmente se houver desequilíbrio entre as classes. A métrica prioritária deverá considerar o objetivo da previsão e o custo dos diferentes tipos de erro.

## 10. Controle de versão e arquivos ignorados

O `.gitignore` atual exclui:

```gitignore
.venv/
__pycache__/
*.py[cod]
.ipynb_checkpoints/
.env
data/raw/
data/processed/
```

Essas regras impedem que o ambiente virtual, arquivos temporários, configurações locais e dados brutos ou processados sejam incluídos automaticamente em novos commits.

Como os dados estão fora do controle de versão, cada integrante deverá obter os arquivos originais necessários para executar o processamento e gerar os resultados localmente.

Antes de alterar as regras de exclusão, o grupo deverá combinar como compartilhará os dados necessários para reproduzir os experimentos.

Boas práticas:

- Preservar os arquivos originais em `data/raw/`.
- Armazenar os resultados derivados em `data/processed/`.
- Não versionar ambientes virtuais.
- Registrar mudanças de código com mensagens claras.
- Manter o `requirements.txt` atualizado.
- Não incluir chaves de API, credenciais ou informações confidenciais no repositório.
- Documentar alterações nos critérios de processamento.

## 11. Estado atual e próximas etapas

### Implementado

- Organização dos arquivos brutos de precipitação do CEMADEN.
- Script de engenharia de atributos em `src/engenharia_atributos.py`.
- Cálculo de chuva acumulada em janelas de três horas.
- Indicadores de validade e cobertura temporal das janelas.
- Conversão dos horários para UTC e para o fuso local utilizado pelo processamento.
- Geração de `data/processed/chuva_acumulada_3h.csv`.
- Registro das dependências em `requirements.txt`.
- Regras de exclusão de arquivos locais no `.gitignore`.

### Pendente

- Confirmar a interpretação de `valorMedida` na documentação do CEMADEN.
- Revisar e justificar os critérios de validade das janelas de três horas.
- Investigar a cobertura reduzida da estação `280030803A`.
- Obter e processar os dados de maré.
- Organizar e verificar as fontes de registros de alagamentos.
- Definir um procedimento confiável de rotulagem positiva e negativa.
- Construir e validar a base integrada.
- Implementar os modelos de classificação.
- Definir o protocolo de avaliação.
- Realizar a comparação dos modelos.
- Documentar os resultados e as conclusões.

## 12. Limitações

A qualidade dos resultados depende da cobertura, da confiabilidade e da compatibilidade temporal das fontes utilizadas.

O conjunto de precipitação atualmente processado contém três estações, cuja cobertura válida varia consideravelmente. Isso limita a representação espacial e temporal das condições de chuva.

Além disso, os critérios de validação das janelas ainda precisam de confirmação metodológica. Os dados de maré e os rótulos de alagamento também precisam ser integrados e verificados.

Consequentemente, o desempenho dos modelos deverá ser interpretado considerando essas limitações. Os resultados experimentais não constituem, por si só, uma garantia de previsão operacional de alagamentos.

## 13. Resultado esperado

Ao final, espera-se obter:

- Uma base de dados ambientais integrada e documentada.
- Três modelos de classificação implementados e avaliados.
- Uma comparação de desempenho baseada em métricas adequadas.
- Uma análise das relações observadas entre precipitação, maré e alagamentos.
- Uma discussão das limitações dos dados e da capacidade de generalização dos modelos.

As conclusões deverão ser fundamentadas nos resultados efetivamente obtidos durante os experimentos.