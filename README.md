# Alagaju — Predição de Alagamentos em Aracaju

## 1. Sobre o projeto

O **Alagaju** é um projeto de análise de dados e aprendizado de máquina que busca investigar a relação entre as condições meteorológicas, o nível da maré e a ocorrência de alagamentos em Aracaju, Sergipe.

A proposta é construir e comparar modelos de classificação capazes de estimar a ocorrência de alagamentos a partir de variáveis observadas, especialmente:

- Precipitação acumulada nas três horas anteriores;
- Condições da maré;
- Registros históricos de alagamentos;
- Outras variáveis que possam ser incorporadas futuramente, desde que haja dados disponíveis e justificativa metodológica.

O projeto utiliza dados históricos para treinar e avaliar modelos. Portanto, seu objetivo inicial é identificar padrões associados aos alagamentos, e não afirmar que já existe um sistema operacional de previsão em tempo real.

## 2. Objetivos

### Objetivo geral

Investigar a viabilidade de utilizar dados de chuva e maré para classificar situações associadas à ocorrência de alagamentos em Aracaju, comparando diferentes algoritmos de aprendizado de máquina.

### Objetivos específicos

1. Coletar e organizar os dados históricos de precipitação.
2. Construir atributos temporais, especialmente a chuva acumulada nas três horas anteriores.
3. Obter e preparar os dados de maré.
4. Organizar notícias e outros registros documentais sobre alagamentos.
5. Construir uma base integrada com atributos e rótulos verificáveis.
6. Treinar modelos de regressão logística, árvore de decisão e máquina de vetores de suporte (SVM).
7. Avaliar e comparar os modelos utilizando métricas adequadas.
8. Documentar limitações, qualidade dos dados e possibilidades de melhoria.

## 3. Organização do repositório

A estrutura atual do projeto é:

```text
Alagaju/
├── .venv/
├── .gitignore
├── README.md
├── requirements.txt
├── data/
│   ├── raw/
│   │   └── cemaden/
│   │       ├── 2025/
│   │       └── 2026/
│   └── processed/
├── notebooks/
├── src/
│   ├── carregar_cemaden.py
│   └── engenharia_atributos.py
└── tests/
```

### Diretórios e arquivos

| Caminho | Finalidade |
|---|---|
| `data/raw/` | Armazenar os dados originais, sem alterações. |
| `data/raw/cemaden/` | Armazenar os CSVs de precipitação obtidos do CEMADEN. |
| `data/processed/` | Armazenar os dados derivados das etapas de processamento. |
| `src/` | Contém os scripts de processamento e engenharia de atributos. |
| `notebooks/` | Exploração dos dados, experimentos e visualizações. |
| `tests/` | Testes automatizados para verificar o comportamento do código. |
| `requirements.txt` | Lista das dependências Python do projeto. |
| `.gitignore` | Define arquivos e diretórios que não devem ser versionados. |

**Organização futura sugerida:** à medida que o projeto evoluir, poderão ser adicionados diretórios específicos para dados de maré, registros de alagamentos, modelos treinados, relatórios e resultados dos experimentos. Essa expansão deve acompanhar a implementação real, sem criar diretórios vazios apenas para aparentar que etapas já foram concluídas.

## 4. Fontes de dados

### 4.1. Precipitação — CEMADEN

A base atual contém arquivos mensais de precipitação do Centro Nacional de Monitoramento e Alertas de Desastres Naturais (CEMADEN).

Resumo da base processada:

- **21 arquivos mensais:** janeiro de 2025 a setembro de 2026;
- **32.757 registros** no conjunto analisado;
- **3 estações pluviométricas**;
- Período dos registros em UTC: de 1º de janeiro de 2025 a 26 de setembro de 2026;
- Estações identificadas pelos códigos `280030801A`, `280030802A` e `280030803A`.

Os arquivos possuem as seguintes colunas originais:

| Coluna | Descrição |
|---|---|
| `municipio` | Município da estação. |
| `codEstacao` | Identificador da estação pluviométrica. |
| `uf` | Unidade federativa. |
| `nomeEstacao` | Nome da estação. |
| `latitude` | Latitude da estação. |
| `longitude` | Longitude da estação. |
| `datahora` | Data e hora do registro. |
| `valorMedida` | Valor de precipitação informado na fonte. |

Os arquivos utilizam ponto e vírgula como separador e vírgula como separador decimal. A leitura deve respeitar essa formatação e a codificação dos arquivos.

**Cuidado metodológico:** antes de interpretar `valorMedida` como uma quantidade diretamente somável em qualquer situação, é necessário confirmar sua semântica na documentação da fonte. O tratamento dos intervalos de transmissão, dos registros ausentes e da cobertura temporal influencia o significado do acumulado calculado.

### 4.2. Maré

A variável `mare_atual` está prevista na metodologia, mas a integração dos dados de maré ainda precisa ser realizada.

Essa etapa deverá definir:

- A fonte dos dados e sua documentação;
- A unidade de medida;
- O referencial utilizado para representar o nível da maré;
- O fuso horário e a resolução temporal;
- O procedimento para associar a maré ao horário de cada observação;
- O tratamento de valores ausentes.

É importante verificar se os valores representam previsões de maré, observações reais ou outro tipo de medida. Essas informações não devem ser tratadas como equivalentes.

### 4.3. Registros de alagamentos

O projeto dispõe de notícias sobre episódios de alagamento como fontes potenciais para construir a variável-alvo.

Cada ocorrência deverá ser documentada, sempre que possível, com:

- Data e horário do evento;
- Bairro, rua ou localização descrita;
- Fonte e endereço da notícia;
- Evidência explícita da ocorrência de alagamento;
- Horário de publicação, quando disponível;
- Grau de confiança na identificação do evento;
- Observações sobre a precisão temporal e espacial.

Uma notícia publicada depois de um evento não necessariamente informa o horário exato em que o alagamento começou. O horário da publicação não deve ser usado automaticamente como horário da ocorrência.

Além disso, a ausência de notícias sobre um local ou período não prova que não houve alagamento. Para criar exemplos negativos, será necessário estabelecer uma metodologia de rotulagem defensável.

## 5. Engenharia de atributos

A engenharia de atributos é a etapa responsável por transformar os registros originais em variáveis adequadas para os modelos de aprendizado de máquina.

O script atualmente implementado é:

`src/engenharia_atributos.py`

Ele lê os arquivos de precipitação, organiza os registros por estação, processa os horários e calcula uma estimativa de chuva acumulada nas três horas anteriores.

### 5.1. Tratamento inicial

O processamento contempla as seguintes operações:

1. Leitura dos CSVs de origem;
2. Conversão dos horários para datas reconhecidas pelo pandas;
3. Interpretação dos horários como UTC;
4. Conversão de `valorMedida` para um tipo numérico;
5. Identificação e tratamento de registros inválidos;
6. Ordenação cronológica dos registros;
7. Verificação de duplicidades por estação e horário;
8. Conversão dos horários para o fuso `America/Maceio`;
9. Cálculo da chuva acumulada;
10. Avaliação da cobertura temporal das janelas.

O processamento preserva os arquivos originais. As transformações são realizadas em memória e o resultado é escrito em um novo arquivo.

### 5.2. Chuva acumulada em três horas

A variável calculada é:

`chuva_acumulada_3h_mm`

A intenção é representar a precipitação acumulada na janela de três horas que termina no horário de cada observação.

Conceitualmente, para uma estação e um horário `t`, considera-se o intervalo:

`(t - 3 horas, t]`

A implementação utiliza os registros disponíveis dentro dessa janela e soma os valores de precipitação considerados válidos.

O cálculo é feito separadamente para cada estação. Não se deve somar diretamente as medições de estações diferentes, pois elas representam locais distintos.

**Limitação importante:** o resultado é uma estimativa condicionada aos registros disponíveis e às regras de validade adotadas. Não se deve interpretá-lo como uma medição perfeita da precipitação real quando existem lacunas temporais ou dúvidas sobre a semântica do campo original.

### 5.3. Validade da janela

O script também produz informações auxiliares para avaliar a qualidade temporal dos acumulados.

| Atributo | Finalidade |
|---|---|
| `janela_3h_valida` | Indica se a janela foi aceita segundo os critérios implementados. |
| `n_medicoes_3h` | Registra a quantidade de medições consideradas na janela. |
| `maior_intervalo_min_3h` | Registra o maior intervalo entre observações relevantes para a avaliação temporal. |

Na versão atual, a regra é conservadora:

- Quando existe chuva na janela, os intervalos precisam respeitar o limite de dez minutos;
- Quando todos os valores considerados são zero, admite-se um intervalo de até 60 minutos;
- Janelas que não satisfazem as verificações ficam com o acumulado como `NaN`.

Essa regra busca evitar que lacunas durante episódios de chuva sejam interpretadas como se não houvesse medições faltantes. Entretanto, ela também pode descartar janelas de chuva real quando há falhas de transmissão.

O critério é uma decisão metodológica do projeto e deve ser avaliado com base na documentação da fonte e na distribuição dos dados.

### 5.4. Resultado atual do processamento

Na execução mais recente, o script processou 32.757 registros e gerou o arquivo:

`data/processed/chuva_acumulada_3h.csv`

Resumo das janelas:

| Indicador | Resultado |
|---|---:|
| Registros de saída | 32.757 |
| Janelas válidas | 22.536 |
| Janelas inválidas | 10.221 |
| Proporção de janelas válidas | 68,80% |
| Proporção de janelas inválidas | 31,20% |

A validade por estação foi:

| Estação | Registros | Janelas válidas | Proporção válida |
|---|---:|---:|---:|
| `280030801A` | 12.232 | 8.461 | 69,17% |
| `280030802A` | 17.487 | 12.758 | 72,96% |
| `280030803A` | 3.038 | 1.317 | 43,35% |

A terceira estação possui uma proporção de janelas válidas consideravelmente menor. Isso deve ser investigado antes de decidir se seus dados serão utilizados, filtrados ou tratados de outra forma.

Na versão atual, o maior acumulado aceito foi de 84 mm em três horas, registrado na estação `280030801A` em 4 de maio de 2025, às 07:10 UTC. Valores elevados não devem ser removidos automaticamente: precisam ser investigados com base na sequência das medições, na documentação da fonte e, quando possível, em registros independentes.

Esses resultados descrevem a execução atual e podem mudar quando os critérios de validade forem revisados.

## 6. Como executar o projeto

Os comandos abaixo pressupõem um ambiente Windows com o Prompt de Comando (CMD), executados a partir da raiz do repositório.

### 6.1. Acessar o repositório

Abra o terminal na pasta do projeto:

```cmd
cd caminho\para\Alagaju
```

Substitua `caminho\para\Alagaju` pelo caminho em que o repositório foi clonado.

### 6.2. Criar e ativar o ambiente virtual

Se o ambiente virtual ainda não existir:

```cmd
python -m venv .venv
```

Ative-o:

```cmd
.venv\Scripts\activate
```

### 6.3. Instalar as dependências

Com o ambiente virtual ativado:

```cmd
python -m pip install -r requirements.txt
```

### 6.4. Executar a engenharia de atributos

Na raiz do repositório, execute:

```cmd
python src\engenharia_atributos.py
```

O script deverá processar os arquivos de precipitação e gerar:

`data/processed/chuva_acumulada_3h.csv`

### 6.5. Conferir os resultados

Para verificar a quantidade de janelas válidas e inválidas por estação:

```cmd
python -c "import pandas as pd; d=pd.read_csv('data/processed/chuva_acumulada_3h.csv'); print(d['janela_3h_valida'].value_counts()); print(d.groupby('codEstacao')['janela_3h_valida'].agg(['count','sum','mean']))"
```

A coluna `mean` representa a proporção de janelas válidas por estação, considerando que `True` equivale a 1 e `False` equivale a 0.

As janelas inválidas possuem `NaN` no acumulado de chuva. Esses valores não devem ser substituídos automaticamente por zero, pois representam insuficiência de cobertura temporal segundo os critérios atuais.

## 7. Modelagem de aprendizado de máquina

O plano do projeto prevê a comparação de três algoritmos de classificação.

### 7.1. Regressão logística

Responsável: **Integrante 2**

A regressão logística será utilizada como modelo de referência para classificação binária.

Atividades:

- Preparar os atributos de entrada;
- Tratar os valores ausentes de maneira documentada;
- Ajustar a regressão logística apenas com os dados de treinamento;
- Avaliar o modelo no conjunto de teste;
- Registrar os parâmetros e os resultados obtidos.

A regressão logística pode servir como baseline para avaliar se modelos mais complexos oferecem ganhos reais.

### 7.2. Árvore de decisão

Responsável: **Integrante 3**

A árvore de decisão será treinada para identificar combinações de atributos associadas à classe positiva.

Atividades:

- Preparar os dados utilizando a mesma definição de atributos e alvo;
- Treinar o modelo;
- Controlar a complexidade da árvore para reduzir o risco de sobreajuste;
- Avaliar seu desempenho no conjunto de teste;
- Registrar os parâmetros e os resultados.

A interpretabilidade da árvore pode ajudar a investigar como os atributos influenciam as classificações, mas não demonstra causalidade.

### 7.3. Máquina de vetores de suporte (SVM)

Responsável: **Integrante 4**

A SVM será utilizada como terceiro classificador para comparação.

Atividades:

- Preparar os mesmos atributos e rótulos utilizados pelos demais modelos;
- Ajustar a escala das variáveis numéricas quando necessário;
- Construir o pipeline de pré-processamento e treinamento;
- Ajustar os hiperparâmetros usando apenas os dados de treinamento;
- Avaliar o resultado no conjunto de teste.

A normalização deve ser ajustada exclusivamente nos dados de treinamento e depois aplicada aos dados de validação e teste, evitando vazamento de informação.

## 8. Avaliação e comparação dos modelos

Responsável: **Integrante 5**

O quinto integrante deverá organizar a avaliação dos modelos e a comparação estatística de seus resultados.

As atividades incluem:

1. Definir uma estratégia de divisão temporal dos dados;
2. Garantir que os modelos sejam avaliados sobre as mesmas observações;
3. Calcular as métricas;
4. Comparar os resultados;
5. Documentar as limitações da avaliação;
6. Produzir tabelas e visualizações para o relatório final.

### Métricas recomendadas

| Métrica | O que informa |
|---|---|
| Acurácia | Proporção total de classificações corretas. |
| Precisão | Entre os casos classificados como alagamento, quantos eram positivos. |
| Revocação (recall) | Entre os casos positivos reais, quantos foram identificados. |
| F1-score | Equilíbrio entre precisão e recall. |
| Matriz de confusão | Quantidade de verdadeiros e falsos positivos e negativos. |
| ROC-AUC | Capacidade de discriminar as classes em diferentes limiares. |
| PR-AUC | Desempenho relacionado à precisão e à revocação, especialmente útil quando há poucos casos positivos. |

A acurácia não deve ser analisada isoladamente. Se a maioria das observações corresponder à ausência de alagamento, um modelo que quase sempre prevê a classe negativa pode apresentar acurácia alta e ainda assim falhar em identificar os eventos importantes.

A comparação estatística deve considerar o número de eventos, a dependência temporal entre observações e a incerteza das métricas. Não basta comparar valores pontuais e declarar que um modelo é superior.

## 9. Responsabilidades da equipe

O projeto está dividido em cinco responsabilidades principais.

### Integrante 1 — Engenharia de atributos e preparação dos dados

Responsável pela preparação dos dados e construção das variáveis de entrada.

Atividades:

- Manter o processamento dos arquivos do CEMADEN;
- Documentar a semântica de `valorMedida`;
- Calcular e validar `chuva_acumulada_3h_mm`;
- Investigar a cobertura temporal das estações;
- Preparar a variável `mare_atual` quando os dados estiverem disponíveis;
- Organizar os dados de alagamentos recebidos da equipe;
- Preparar a base integrada para a modelagem;
- Documentar decisões de limpeza, filtragem e tratamento de valores ausentes.

**Entregáveis:** scripts de processamento, dados derivados documentados, relatório de qualidade e base preparada para os modelos.

### Integrante 2 — Regressão logística

Atividades:

- Implementar a regressão logística;
- Definir o pipeline de treinamento;
- Ajustar o modelo utilizando somente os dados de treinamento;
- Registrar os resultados e parâmetros;
- Disponibilizar as previsões e métricas para comparação.

**Entregável:** implementação reproduzível e resultados da regressão logística.

### Integrante 3 — Árvore de decisão

Atividades:

- Implementar a árvore de decisão;
- Ajustar a complexidade do modelo;
- Avaliar o risco de sobreajuste;
- Registrar os parâmetros e resultados;
- Disponibilizar as previsões e métricas para comparação.

**Entregável:** implementação reproduzível e resultados da árvore de decisão.

### Integrante 4 — SVM

Atividades:

- Implementar a SVM;
- Preparar o escalonamento das variáveis;
- Ajustar os hiperparâmetros sem utilizar o conjunto de teste;
- Registrar os parâmetros e resultados;
- Disponibilizar as previsões e métricas para comparação.

**Entregável:** implementação reproduzível e resultados da SVM.

### Integrante 5 — Avaliação e comparação

Atividades:

- Definir o protocolo de avaliação em conjunto com a equipe;
- Garantir a utilização dos mesmos dados de teste;
- Calcular as métricas de cada modelo;
- Comparar os resultados de forma justa;
- Produzir tabelas e gráficos;
- Investigar a incerteza das métricas;
- Consolidar os resultados e as limitações no relatório final.

**Entregável:** avaliação comparativa dos modelos e síntese dos resultados.

### Responsabilidades compartilhadas

Todos os integrantes devem:

- Documentar as decisões tomadas;
- Versionar o código;
- Evitar modificar diretamente os arquivos brutos;
- Registrar dependências e parâmetros relevantes;
- Comunicar alterações que afetem a interface entre as etapas;
- Executar os testes disponíveis;
- Revisar os resultados antes da integração.

A divisão de tarefas não elimina a necessidade de decisões conjuntas. A definição do alvo, o protocolo de avaliação e a divisão temporal devem ser acordados por toda a equipe.

## 10. Construção da variável-alvo `alagamento`

A variável-alvo representa o resultado que os modelos tentarão classificar.

A definição planejada é binária:

- `alagamento = 1`: há evidência suficiente de que ocorreu um alagamento no local e período definidos;
- `alagamento = 0`: há evidência suficiente de que não ocorreu alagamento no local e período definidos.

O valor zero não deve ser atribuído simplesmente porque nenhuma notícia foi encontrada.

### Procedimento proposto

1. Reunir notícias, registros oficiais e outras fontes verificáveis.
2. Extrair as datas e os locais dos eventos.
3. Identificar a precisão temporal e espacial de cada registro.
4. Definir uma unidade de análise consistente, como estação/local e intervalo de tempo.
5. Associar os registros de alagamento às observações de chuva e maré.
6. Definir critérios explícitos para positivos, negativos e observações indeterminadas.
7. Excluir ou tratar separadamente as observações sem evidência suficiente.
8. Documentar as incertezas de cada decisão.

A unidade de análise precisa ser definida antes do treinamento. Uma notícia sobre um alagamento em um bairro não pode ser automaticamente atribuída a todas as estações ou a todos os bairros da cidade.

Também será necessário considerar a diferença entre o horário da chuva, o horário do alagamento e o horário em que o evento foi noticiado.

## 11. Integração dos dados

A base final deverá combinar os atributos de entrada e a variável-alvo de forma temporalmente consistente.

Uma estrutura futura possível é:

| Campo | Descrição |
|---|---|
| `datahora` | Horário de referência da observação. |
| `codEstacao` | Identificador da estação, quando aplicável. |
| `chuva_acumulada_3h_mm` | Precipitação estimada nas três horas anteriores. |
| `janela_3h_valida` | Indicador de validade temporal do acumulado. |
| `mare_atual` | Valor da maré associado ao horário, conforme a fonte adotada. |
| `alagamento` | Rótulo binário definido segundo os critérios do projeto. |

Essa tabela é uma proposta de integração, não uma declaração de que todos esses campos já estejam disponíveis em um único arquivo.

Antes da modelagem, a equipe deverá definir:

- A unidade de análise;
- A tolerância temporal entre chuva, maré e ocorrência;
- A política para valores ausentes;
- O tratamento das observações sem rótulo confiável;
- A prevenção de duplicidades;
- A estratégia de divisão entre treino, validação e teste.

## 12. Metodologia de treinamento e prevenção de vazamento de dados

Os dados meteorológicos possuem dependência temporal: observações próximas podem compartilhar praticamente as mesmas condições ambientais.

Por isso, recomenda-se uma divisão cronológica, com períodos anteriores para treinamento e períodos posteriores para teste, em vez de uma divisão aleatória simples de linhas.

A estratégia exata deve ser definida considerando a quantidade de eventos positivos e a distribuição temporal dos registros.

A equipe também deverá evitar:

- Usar informações posteriores ao horário de previsão como atributos;
- Ajustar transformações usando o conjunto de teste;
- Selecionar hiperparâmetros com base nos resultados finais do teste;
- Distribuir versões praticamente idênticas do mesmo evento entre treino e teste sem considerar essa dependência;
- Tratar dados ausentes como zeros sem justificativa.

Se o objetivo for prever alagamentos com antecedência, será necessário definir explicitamente o horizonte de previsão e garantir que os atributos estejam disponíveis antes do evento.

## 13. Pontos de melhoria prioritários

### Prioridade 1 — Validar a interpretação da precipitação

Confirmar a semântica de `valorMedida` na documentação da fonte e verificar se a soma das observações é adequada para o cálculo do acumulado de três horas.

### Prioridade 2 — Investigar a cobertura das estações

A estação `280030803A` apresenta uma taxa de janelas válidas menor que as demais. É necessário verificar a distribuição das lacunas por período e estação antes de decidir seu uso na análise.

### Prioridade 3 — Revisar o critério de validade

A regra atual é conservadora e reduz a quantidade de janelas aceitas. Devem ser avaliados os impactos sobre a quantidade de dados disponíveis, os eventos intensos e a representatividade temporal.

### Prioridade 4 — Integrar os dados de maré

Obter uma fonte documentada, padronizar o horário e a unidade e associar as medições aos horários de referência.

### Prioridade 5 — Construir e auditar os rótulos

Organizar os registros de alagamento, documentar as evidências e definir uma metodologia consistente para os exemplos positivos e negativos.

### Prioridade 6 — Criar testes automatizados

Testar, no mínimo:

- Leitura correta dos CSVs;
- Conversão de horário e fuso;
- Ausência de duplicidades;
- Comportamento da janela móvel;
- Tratamento das lacunas;
- Preservação dos registros originais;
- Tratamento de valores inválidos;
- Consistência entre os dados produzidos e os critérios documentados.

### Prioridade 7 — Reproduzir e comparar os experimentos

Garantir que os três modelos utilizem a mesma definição de atributos, a mesma variável-alvo e o mesmo protocolo de teste.

### Prioridade 8 — Avaliar a generalização

Verificar se o desempenho se mantém em períodos diferentes dos utilizados no treinamento. Os resultados devem ser interpretados considerando o número de eventos, a qualidade dos rótulos e a cobertura das estações.

## 14. Estado atual do projeto

### Implementado

- Organização inicial do repositório;
- Coleta e armazenamento dos CSVs de precipitação;
- Leitura e processamento dos arquivos do CEMADEN;
- Conversão dos horários para UTC e horário local;
- Verificação de duplicidades;
- Cálculo inicial de chuva acumulada em três horas;
- Critérios de validade temporal;
- Geração do arquivo `chuva_acumulada_3h.csv`;
- Inspeção inicial de eventos com precipitação intensa.

### Em andamento ou pendente

- Validação definitiva da semântica de `valorMedida`;
- Investigação das diferenças de cobertura entre as estações;
- Revisão dos critérios de validade das janelas;
- Obtenção e integração dos dados de maré;
- Organização das notícias e dos registros de alagamento;
- Definição da unidade de análise e da variável-alvo;
- Construção da base integrada;
- Implementação dos três classificadores;
- Avaliação e comparação dos modelos;
- Testes automatizados e documentação final dos experimentos.

## 15. Critérios para considerar o projeto concluído

O projeto poderá ser considerado tecnicamente concluído quando:

- As fontes de dados estiverem documentadas;
- O processamento puder ser reproduzido;
- Os atributos tiverem definições e critérios de qualidade explícitos;
- A variável-alvo tiver uma metodologia defensável;
- Os modelos estiverem implementados e avaliados;
- A comparação utilizar um protocolo comum;
- As métricas e limitações estiverem documentadas;
- Os resultados puderem ser reproduzidos a partir dos arquivos e scripts versionados.

A conclusão do projeto não significa que os modelos sejam necessariamente adequados para uso operacional. Essa conclusão depende da qualidade dos dados, da validação temporal e espacial e do desempenho observado em avaliações independentes.

## 16. Considerações finais

O Alagaju busca construir uma base metodologicamente consistente para investigar a relação entre chuva, maré e alagamentos em Aracaju.

O processamento inicial da precipitação já está implementado, mas a qualidade da variável de chuva, a integração da maré e a construção de rótulos confiáveis ainda são etapas essenciais.

A equipe deve priorizar a rastreabilidade dos dados, a reprodutibilidade dos experimentos e a interpretação cuidadosa dos resultados. Nenhum valor extremo deve ser descartado automaticamente, e nenhum modelo deve ser considerado eficaz apenas por apresentar uma métrica isolada elevada.