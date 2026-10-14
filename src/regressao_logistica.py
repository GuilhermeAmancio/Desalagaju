"""
Pessoa 2 — Regressão Logística (Desalagaju)

Treina um modelo de regressão logística para prever `alagamento` (0/1),
usa padronização dentro de um Pipeline, busca hiperparâmetros com GridSearchCV
e exporta métricas e predições.

Uso (a partir da raiz do repositório):
    python src/regressao_logistica.py
    python src/regressao_logistica.py --divisao estratificada

A base data/processed/base_integrada.csv precisa conter:
    - alvo `alagamento` (0 = sem alagamento; 1 = alagamento)
    - atributos ambientais definidos em --atributos
    - `datahora_utc` ou `datahora` para divisão temporal (padrão)
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    make_scorer,
    precision_score,
    recall_score
)
from sklearn.model_selection import (
    GridSearchCV,
    StratifiedKFold,
    TimeSeriesSplit,
    train_test_split
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parent.parent
PASTA_PROCESSADOS = RAIZ / "data" / "processed"
ARQUIVO_ENTRADA = PASTA_PROCESSADOS / "base_integrada.csv"
ARQUIVO_METRICAS = PASTA_PROCESSADOS / "metricas_regressao_logistica.json"
ARQUIVO_PREDICOES = PASTA_PROCESSADOS / "predicoes_regressao_logistica.csv"

ALVO = "alagamento"
COL_JANELA_VALIDA = "janela_3h_valida"
COLUNAS_TEMPO = ["datahora_utc", "datahora"]
COLUNAS_ID = ["codEstacao"]
ATRIBUTOS_PADRAO = ["chuva_acumulada_3h_mm", "nivel_mare", "n_medicoes_3h"]
SEMENTE = 42

# O StandardScaler fica dentro do Pipeline para ser ajustado somente nos dados
# de treino de cada fold, evitando vazamento de informação.
GRANDE_HIPERPARAMETROS = {
    "classificador__C": [0.01, 0.1, 1.0, 10.0, 100.0],
    "classificador__class_weight": ["balanced", None]
}

def parse_args():
    p = argparse.ArgumentParser(description="Regressão Logística - Desalagaju")
    p.add_argument("--entrada", type=Path, default=ARQUIVO_ENTRADA)
    p.add_argument(
        "--divisao",
        choices=["temporal", "estratificada"],
        default="temporal",
        help="temporal (padrão): teste = período mais recente"
    )
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument(
        "--metrica",
        choices=["f1", "recall"],
        default="f1",
        help="Métrica usada para escolher o melhor modelo no GridSearchCV"
    )
    p.add_argument("--cv-folds", type=int, default=5)
    p.add_argument("--atributos", nargs="+", default=ATRIBUTOS_PADRAO)
    p.add_argument("--semente", type=int, default=SEMENTE)
    return p.parse_args()

def carregar_base(caminho, atributos, usar_tempo):
    if not caminho.exists():
        raise FileNotFoundError(
            f"Base integrada nao encontrada: {caminho}\n"
            "Gere/obtenha data/processed/base_integrada.csv antes de rodar"
        )
    
    df = pd.read_csv(caminho, sep=None, engine="python", encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    total_inicial = len(df)

    if ALVO not in df.columns:
        raise ValueError(
            f"A coluna alvo '{ALVO}' nao existe em {caminho.name}"
            "Os rotulos de alagamento ainda precisam ser integrados à base"
        )
    faltantes = [c for c in atributos if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"Colunas ausentes em {caminho.name}: {faltantes}"
            "Use --atributos para informar as colunas disponíveis"
        )
    
    # Só usar janelas com cobertura válida, quando a coluna existir.
    if COL_JANELA_VALIDA in df.columns:
        valida = (
            df[COL_JANELA_VALIDA].astype(str).str.strip().str.lower()
            .isin(["true", "1", "1.0"])
        )
        df = df[valida].copy()
        print(f"Filtro {COL_JANELA_VALIDA}: {total_inicial} -> {len(df)} linhas")
    else:
        print(f"Aviso: coluna {COL_JANELA_VALIDA} ausente; filtro nao aplicado")

    col_tempo = next((c for c in COLUNAS_TEMPO if c in df.columns), None)
    if col_tempo:
        df[col_tempo] = pd.to_datetime(df[col_tempo], errors="coerce", utc=True)
    elif usar_tempo:
        raise ValueError(
            "Divisao temporal requer 'datahora_utc' ou 'datahora' na base"
            "Use --divisao estratificada ou inclua a coluna"
        )
    
    # Rótulos ausentes/duvidosos são descartados, não convertidos em zero.
    df[ALVO] = pd.to_numeric(df[ALVO], errors="coerce")
    for c in atributos:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    obrigatorias = [ALVO, *atributos] + ([col_tempo] if usar_tempo else [])
    antes = len(df)
    df = df.dropna(subset=obrigatorias).copy()
    if antes != len(df):
        print(f"Removidas {antes - len(df)} linhas com alvo/atributo/tempo ausente")

    invalidos = set(df[ALVO].unique()) - {0, 1}
    if invalidos:
        raise ValueError(
            f"'{ALVO}' deve ser binario (0 ou 1). Valores: {sorted(invalidos)}"
        )
    df[ALVO] = df[ALVO].astype(int)

    if df[ALVO].nunique() < 2:
        raise ValueError("A base nao contem as duas classes apos os filtros")
    
    if usar_tempo:
        df = df.sort_values(col_tempo, kind="stable")
    return df.reset_index(drop=True), col_tempo

def dividir(df, atributos, col_tempo, args):
    if not 0 < args.test_size < 1:
        raise ValueError("--test-size precisa estar entre 0 e 1")
    if args.cv_folds < 2:
        raise ValueError("--cv-folds precisa ser pelo menos 2")
    
    if args.divisao == "temporal":
        # O mesmo instante não pode aparecer simultaneamente em treino e teste.
        posicao = min(int(len(df) * (1 - args.test_size)), len(df) - 1)
        corte = df[col_tempo].iloc[posicao]
        treino = df[df[col_tempo] < corte]
        teste = df[df[col_tempo] >= corte]
        print(f"Corte temporal em {corte} (teste = periodo mais recente)")
        cv = TimeSeriesSplit(n_splits=args.cv_folds)
    else:
        treino, teste = train_test_split(
            df,
            test_size=args.test_size,
            stratify=df[ALVO],
            random_state=args.semente,
        )
        cv = StratifiedKFold(
            n_splits=args.cv_folds, shuffle=True, random_state=args.semente
        )

    if treino.empty or teste.empty:
        raise ValueError("A divisao gerou um conjunto de treino ou teste vazio")
    if treino[ALVO].nunique() < 2 or teste[ALVO].nunique() < 2:
        raise ValueError(
            "Treino ou teste ficou com apenas uma classe. Com poucos alagamentos,"
            "a divisao temporal pode causar isso; cheque --divisao estratificada"
            "ou altere --test-size"
        )
    if (treino[ALVO] == 1).sum() < args.cv_folds:
        raise ValueError(
            f"Poucos positivos no treino ({int((treino[ALVO] == 1).sum())})"
            f"para {args.cv_folds} folds. Diminua --cv-folds"
        )
    
    Xt, yt = treino[atributos], treino[ALVO]
    for i,(_, val) in enumerate(cv.split(Xt, yt), start=1):
        if yt.iloc[val].sum() == 0:
            print(f"Aviso: fold {i} da validacao cruzada nao tem positivos")

    return treino, teste, cv

def treinar(treino, atributos, cv, args):
    pipeline = Pipeline(
        steps=[
            ("padronizacao", StandardScaler()),
            (
                "classificador",
                LogisticRegression(
                    solver="lbfgs",
                    max_iter=2000,
                    random_state=args.semente,
                )
            )
        ]
    )
    busca = GridSearchCV(
        estimator=pipeline,
        param_grid=GRANDE_HIPERPARAMETROS,
        scoring={
            "f1": make_scorer(f1_score, zero_division=0),
            "recall": make_scorer(recall_score, zero_division=0),
            "precision": make_scorer(precision_score, zero_division=0),
        },
        refit=args.metrica,
        cv=cv,
        n_jobs=-1,
        error_score=0.0,
    )
    busca.fit(treino[atributos], treino[ALVO])
    return busca

def calcular_metricas(y_teste, y_prev):
    cm = confusion_matrix(y_teste, y_prev, labels=[0, 1])
    tn, fp, fn, tp = (int(v) for v in cm.ravel())
    return {
        "acuracia": float(accuracy_score(y_teste, y_prev)),
        "precisao": float(precision_score(y_teste, y_prev, zero_division=0)),
        "recall": float(recall_score(y_teste, y_prev, zero_division=0)),
        "f1_score": float(f1_score(y_teste, y_prev, zero_division=0)),
        "matriz_confusao": {
            "rotulos": [0, 1],
            "matriz": cm.tolist(),
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
        },
    }

def main():
    args = parse_args()
    atributos = list(args.atributos)
    usar_tempo = args.divisao == "temporal"

    df, col_tempo = carregar_base(args.entrada, atributos, usar_tempo)
    print(f"Base pra modelagem: {len(df)} linhas | positivos: {int(df[ALVO].sum())}")

    treino, teste, cv = dividir(df, atributos, col_tempo, args)
    print(
        f"Treino: {len(treino)} ({int(treino[ALVO].sum())} positivos) | "
        f"Teste: {len(teste)} ({int(teste[ALVO].sum())} positivos)"
    )

    busca = treinar(treino, atributos, cv, args)
    modelo = busca.best_estimator_

    X_teste, y_teste = teste[atributos], teste[ALVO].to_numpy()
    y_prev = modelo.predict(X_teste)
    prob = modelo.predict_proba(X_teste)[:, list(modelo.classes_).index(1)]

    melhor = busca.best_index_
    resultados_cv = busca.cv_results_
    classificador = modelo.named_steps["classificador"]

    metricas = {
        "modelo": "LogisticRegression",
        "protocolo": {
            "divisao": args.divisao,
            "test_size": args.test_size,
            "cv_folds": args.cv_folds,
            "metrica_selecao": args.metrica,
            "semente": args.semente,
            "filtro_janela_3h_valida": COL_JANELA_VALIDA in df.columns,
            "padronizacao": "StandardScaler dentro de Pipeline",
        },
        "atributos": atributos,
        "n_treino": int(len(treino)),
        "n_teste": int(len(teste)),
        "positivos_treino": int(treino[ALVO].sum()),
        "positivos_teste": int(teste[ALVO].sum()),
        "melhores_hiperparametros": busca.best_params_,
        "validacao_cruzada_melhor": {
            "f1_medio": float(resultados_cv["mean_test_f1"][melhor]),
            "recall_medio": float(resultados_cv["mean_test_recall"][melhor]),
            "precisao_media": float(resultados_cv["mean_test_precision"][melhor]),
        },
        "intercepto": float(classificador.intercept_[0]),
        "coeficientes": {
            atributo: float(coef)
            for atributo, coef in zip(atributos, classificador.coef_[0])
        },
        "teste": calcular_metricas(y_teste, y_prev),
    }

    # Predições na mesma ordem do conjunto de teste para comparação pareada.
    pred = pd.DataFrame({"indice_base": teste.index.to_numpy()})
    for c in COLUNAS_ID:
        if c in teste.columns:
            pred[c] = teste[c].to_numpy()
    if col_tempo:
        pred[col_tempo] = teste[col_tempo].to_numpy()
    pred["y_teste"] = y_teste
    pred["y_previsto"] = y_prev
    pred["prob_alagamento"] = prob
    pred["acerto"] = (pred["y_teste"] == pred["y_previsto"]).astype(int)

    PASTA_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_METRICAS, "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    pred.to_csv(ARQUIVO_PREDICOES, index=False, encoding="utf-8-sig")

    t = metricas["teste"]
    print("\n" + "=" * 65)
    print("REGRESSAO LOGISTICA - RESUMO")
    print("=" * 65)
    print("Melhores hiperparametros:", busca.best_params_)
    print(f"CV ({args.metrica}): {busca.best_score_:.4f}")
    print(
        f"Teste -> acuracia {t['acuracia']:.4f} | precisao {t['precisao']:.4f} | "
        f"recall {t['recall']:.4f} | F1 {t['f1_score']:.4f}"
    )
    print("Matriz de confusao [[TN, FP], [FN, TP]]:", t["matriz_confusao"]["matriz"])
    print("Arquvios criados:")
    for arquivo in (ARQUIVO_METRICAS, ARQUIVO_PREDICOES):
        print(" -", arquivo.relative_to(RAIZ))

if __name__ == "__main__":
    main()

