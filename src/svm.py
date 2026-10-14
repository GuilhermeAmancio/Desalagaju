"""
Pessoa 4 - SVM (Desalagaju)

Treina um SVC (Support Vector Classifier) para prever `alagamento` (0/1).
Avalia a necessidade de padronizar as variaveis comparando, com a mesma
validacao cruzada, o mesmo modelo COM e SEM StandardScaler. A escolha e feita
apenas pela validacao cruzada no treino (o teste nao participa da decisao).
Exporta metricas, predicoes e a comparacao de padronizacao.

Uso (a partir da raiz do repositorio):
    python src/svm.py
    python src/svm.py --divisao estratificada
    python src/svm.py --grade rapida            # grade reduzida, para testar
    python src/svm.py --padronizacao sim        # forca StandardScaler

A base data/processed/base_integrada.csv precisa conter:
    - alvo `alagamento` (0 = sem alagamento; 1 = alagamento)
    - atributos ambientais definidos em --atributos
    - `datahora_utc` ou `datahora` para divisao temporal (padrao)
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    make_scorer,
    precision_score,
    recall_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    StratifiedKFold,
    TimeSeriesSplit,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

RAIZ = Path(__file__).resolve().parent.parent
PASTA_PROCESSADOS = RAIZ / "data" / "processed"
ARQUIVO_ENTRADA = PASTA_PROCESSADOS / "base_integrada.csv"
ARQUIVO_METRICAS = PASTA_PROCESSADOS / "metricas_svm.json"
ARQUIVO_PREDICOES = PASTA_PROCESSADOS / "predicoes_svm.csv"

ALVO = "alagamento"
COL_JANELA_VALIDA = "janela_3h_valida"
COLUNAS_TEMPO = ["datahora_utc", "datahora"]
COLUNAS_ID = ["codEstacao"]
ATRIBUTOS_PADRAO = ["chuva_acumulada_3h_mm", "nivel_mare", "n_medicoes_3h"]
SEMENTE = 42

# Limite de iteracoes do solver. Sem padronizacao, o kernel linear com C alto
# quase nao converge (o problema fica mal condicionado); sem este teto o
# GridSearchCV pode rodar por muito tempo. Com padronizacao converge bem antes.
MAX_ITER = 500_000

# Grade completa: kernel linear (interpretavel) e RBF (nao linear).
# O prefixo "svm__" e o nome do passo dentro do Pipeline.
GRADE_COMPLETA = [
    {
        "svm__kernel": ["linear"],
        "svm__C": [0.01, 0.1, 1.0, 10.0],
        "svm__class_weight": ["balanced", None],
    },
    {
        "svm__kernel": ["rbf"],
        "svm__C": [0.1, 1.0, 10.0, 100.0],
        "svm__gamma": ["scale", 0.01, 0.1, 1.0],
        "svm__class_weight": ["balanced", None],
    },
]

# Grade reduzida, so para testar o fluxo rapidamente.
GRADE_RAPIDA = [
    {
        "svm__kernel": ["linear"],
        "svm__C": [1.0],
        "svm__class_weight": ["balanced"],
    },
    {
        "svm__kernel": ["rbf"],
        "svm__C": [1.0, 10.0],
        "svm__gamma": ["scale"],
        "svm__class_weight": ["balanced"],
    },
]

# Se o modelo sem padronizacao nao superar o com padronizacao por pelo menos
# esta margem no score de CV, mantemos a padronizacao (mais robusta).
MARGEM_PADRONIZACAO = 0.01


def parse_args():
    p = argparse.ArgumentParser(description="SVM - Desalagaju")
    p.add_argument("--entrada", type=Path, default=ARQUIVO_ENTRADA)
    p.add_argument(
        "--divisao",
        choices=["temporal", "estratificada"],
        default="temporal",
        help="temporal (padrao): teste = periodo mais recente",
    )
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument(
        "--metrica",
        choices=["f1", "recall"],
        default="f1",
        help="Metrica usada para escolher o melhor modelo no GridSearchCV",
    )
    p.add_argument("--cv-folds", type=int, default=5)
    p.add_argument("--atributos", nargs="+", default=ATRIBUTOS_PADRAO)
    p.add_argument("--semente", type=int, default=SEMENTE)
    p.add_argument(
        "--padronizacao",
        choices=["auto", "sim", "nao"],
        default="auto",
        help="auto (padrao): compara com/sem StandardScaler pela CV e escolhe.",
    )
    p.add_argument(
        "--grade",
        choices=["completa", "rapida"],
        default="completa",
        help="rapida: grade reduzida, util para testar o fluxo.",
    )
    return p.parse_args()


# --------------------------------------------------------------------------
# Carga e preparacao 
# --------------------------------------------------------------------------
def carregar_base(caminho, atributos, usar_tempo):
    if not caminho.exists():
        raise FileNotFoundError(
            f"Base integrada nao encontrada: {caminho}\n"
            "Gere/obtenha data/processed/base_integrada.csv antes de rodar."
        )

    df = pd.read_csv(caminho, sep=None, engine="python", encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    total_inicial = len(df)

    if ALVO not in df.columns:
        raise ValueError(
            f"A coluna alvo '{ALVO}' nao existe em {caminho.name}. "
            "Os rotulos de alagamento ainda precisam ser integrados a base."
        )
    faltantes = [c for c in atributos if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"Colunas ausentes em {caminho.name}: {faltantes}. "
            "Use --atributos para informar as colunas disponiveis."
        )

    # So janelas de 3h com cobertura valida.
    if COL_JANELA_VALIDA in df.columns:
        valida = (
            df[COL_JANELA_VALIDA].astype(str).str.strip().str.lower()
            .isin(["true", "1", "1.0"])
        )
        df = df[valida].copy()
        print(f"Filtro {COL_JANELA_VALIDA}: {total_inicial} -> {len(df)} linhas")
    else:
        print(f"Aviso: coluna {COL_JANELA_VALIDA} ausente; filtro nao aplicado.")

    col_tempo = next((c for c in COLUNAS_TEMPO if c in df.columns), None)
    if col_tempo:
        df[col_tempo] = pd.to_datetime(df[col_tempo], errors="coerce", utc=True)
    elif usar_tempo:
        raise ValueError(
            "Divisao temporal requer 'datahora_utc' ou 'datahora' na base. "
            "Use --divisao estratificada ou inclua a coluna."
        )

    # Rotulos ausentes sao descartados, nunca convertidos em zero.
    df[ALVO] = pd.to_numeric(df[ALVO], errors="coerce")
    for c in atributos:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    obrigatorias = [ALVO, *atributos] + ([col_tempo] if usar_tempo else [])
    antes = len(df)
    df = df.dropna(subset=obrigatorias).copy()
    if antes != len(df):
        print(f"Removidas {antes - len(df)} linhas com alvo/atributo/tempo ausente.")

    invalidos = set(df[ALVO].unique()) - {0, 1}
    if invalidos:
        raise ValueError(f"'{ALVO}' deve ser binario (0/1). Valores: {sorted(invalidos)}")
    df[ALVO] = df[ALVO].astype(int)

    if df[ALVO].nunique() < 2:
        raise ValueError("A base nao contem as duas classes apos os filtros.")

    if usar_tempo:
        df = df.sort_values(col_tempo, kind="stable")
    return df.reset_index(drop=True), col_tempo


def dividir(df, atributos, col_tempo, args):
    if not 0 < args.test_size < 1:
        raise ValueError("--test-size precisa estar entre 0 e 1")
    if args.cv_folds < 2:
        raise ValueError("--cv-folds precisa ser pelo menos 2")

    if args.divisao == "temporal":
        # O mesmo instante nunca fica nos dois lados.
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
        raise ValueError("A divisao gerou um conjunto de treino ou teste vazio.")
    if treino[ALVO].nunique() < 2 or teste[ALVO].nunique() < 2:
        raise ValueError(
            "Treino ou teste ficou com apenas uma classe. Com poucos alagamentos "
            "a divisao temporal pode causar isso; avalie --divisao estratificada "
            "ou ajuste --test-size (e alinhe a escolha com o grupo)."
        )
    if (treino[ALVO] == 1).sum() < args.cv_folds:
        raise ValueError(
            f"Poucos positivos no treino ({int((treino[ALVO] == 1).sum())}) "
            f"para {args.cv_folds} folds. Reduza --cv-folds."
        )

    # Folds de validacao sem positivos geram F1/recall = 0 artificial.
    Xt, yt = treino[atributos], treino[ALVO]
    for i, (_, val) in enumerate(cv.split(Xt, yt), start=1):
        if yt.iloc[val].sum() == 0:
            print(f"Aviso: fold {i} da validacao cruzada nao tem positivos.")

    return treino, teste, cv


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------
def montar_pipeline(padronizar, semente):
    """
    SVM e sensivel a escala: no kernel RBF a distancia entre pontos domina o
    resultado, e atributos em unidades grandes (mm de chuva, numero de
    medicoes) "engolem" os de escala pequena (nivel da mare em metros).
    Por isso o StandardScaler fica DENTRO do Pipeline (ajustado so no treino
    de cada fold, sem vazamento). A variante sem padronizacao existe para
    documentar empiricamente a necessidade do passo.
    """
    return Pipeline(
        steps=[
            ("padronizacao", StandardScaler() if padronizar else "passthrough"),
            (
                "svm",
                # Sem probability=True
                # as probabilidades sao calibradas a parte, so para exportar.
                SVC(cache_size=500, max_iter=MAX_ITER, random_state=semente),
            ),
        ]
    )


def treinar_variante(treino, atributos, cv, args, padronizar):
    grade = GRADE_COMPLETA if args.grade == "completa" else GRADE_RAPIDA
    busca = GridSearchCV(
        estimator=montar_pipeline(padronizar, args.semente),
        param_grid=grade,
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
    inicio = time.perf_counter()
    busca.fit(treino[atributos], treino[ALVO])
    return busca, time.perf_counter() - inicio


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


def resumo_variante(busca, tempo, X_teste, y_teste):
    """Resumo de CV (e teste, so para registro) de uma variante."""
    i = busca.best_index_
    r = busca.cv_results_
    return {
        "melhores_hiperparametros": busca.best_params_,
        "score_cv_metrica_selecao": float(busca.best_score_),
        "cv_f1_medio": float(r["mean_test_f1"][i]),
        "cv_recall_medio": float(r["mean_test_recall"][i]),
        "cv_precisao_media": float(r["mean_test_precision"][i]),
        "tempo_busca_s": round(tempo, 2),
        "teste": calcular_metricas(y_teste, busca.best_estimator_.predict(X_teste)),
    }


def escolher_variante(args, busca_com, busca_sem):
    """A decisao usa apenas o score de CV no treino; o teste nao entra."""
    if args.padronizacao == "sim":
        return True, "forcado pelo usuario (--padronizacao sim)"
    if args.padronizacao == "nao":
        return False, "forcado pelo usuario (--padronizacao nao)"
    sc, ss = busca_com.best_score_, busca_sem.best_score_
    if ss > sc + MARGEM_PADRONIZACAO:
        return False, (
            f"sem padronizacao superou por mais de {MARGEM_PADRONIZACAO} "
            f"no CV ({ss:.4f} vs {sc:.4f})"
        )
    return True, (
        f"com padronizacao: CV {sc:.4f} vs {ss:.4f} sem padronizacao "
        f"(margem minima para dispensar: {MARGEM_PADRONIZACAO})"
    )


def main():
    args = parse_args()
    atributos = list(args.atributos)
    usar_tempo = args.divisao == "temporal"

    df, col_tempo = carregar_base(args.entrada, atributos, usar_tempo)
    print(f"Base para modelagem: {len(df)} linhas | positivos: {int(df[ALVO].sum())}")

    treino, teste, cv = dividir(df, atributos, col_tempo, args)
    print(
        f"Treino: {len(treino)} ({int(treino[ALVO].sum())} positivos) | "
        f"Teste: {len(teste)} ({int(teste[ALVO].sum())} positivos)"
    )

    X_teste, y_teste = teste[atributos], teste[ALVO].to_numpy()

    # Roda a variante de padronizacao necessarias.
    buscas, tempos = {}, {}
    variantes = {"auto": [True, False], "sim": [True], "nao": [False]}[args.padronizacao]
    for padronizar in variantes:
        nome = "com_padronizacao" if padronizar else "sem_padronizacao"
        print(f"Buscando hiperparametros ({nome})...")
        buscas[padronizar], tempos[padronizar] = treinar_variante(
            treino, atributos, cv, args, padronizar
        )

    usar_padronizacao, motivo = escolher_variante(
        args, buscas.get(True), buscas.get(False)
    )
    busca = buscas[usar_padronizacao]
    print(f"Escolha: {'COM' if usar_padronizacao else 'SEM'} padronizacao -> {motivo}")

    # Modelo final = melhor pipeline, ja reajustado em todo o treino (refit).
    # As classes previstas vem dele diretamente, sem calibracao.
    modelo = busca.best_estimator_
    y_prev = modelo.predict(X_teste)
    score_decisao = modelo.decision_function(X_teste)

    # Probabilidades (Platt scaling) so para comparar com as Pessoas 2 e 3 e
    # para curvas ROC/PR. O calibrador e ajustado apenas com dados de treino e
    # NAO altera y_previsto.
    calibrador = CalibratedClassifierCV(
        clone(modelo), method="sigmoid", cv=min(3, args.cv_folds), ensemble=False
    )
    calibrador.fit(treino[atributos], treino[ALVO])
    idx_pos = list(calibrador.classes_).index(1)
    prob = calibrador.predict_proba(X_teste)[:, idx_pos]

    svm = modelo.named_steps["svm"]
    importancia = permutation_importance(
        modelo,
        X_teste,
        y_teste,
        scoring=make_scorer(f1_score, zero_division=0),
        n_repeats=10,
        random_state=args.semente,
        n_jobs=-1,
    )

    avaliacao_padronizacao = {
        "criterio": "score de CV no treino (metrica de selecao); teste so registrado",
        "decisao": "com_padronizacao" if usar_padronizacao else "sem_padronizacao",
        "motivo": motivo,
    }
    for padronizar, b in buscas.items():
        nome = "com_padronizacao" if padronizar else "sem_padronizacao"
        avaliacao_padronizacao[nome] = resumo_variante(
            b, tempos[padronizar], X_teste, y_teste
        )

    metricas = {
        "modelo": "SVC",
        "protocolo": {
            "divisao": args.divisao,
            "test_size": args.test_size,
            "cv_folds": args.cv_folds,
            "metrica_selecao": args.metrica,
            "semente": args.semente,
            "grade": args.grade,
            "filtro_janela_3h_valida": COL_JANELA_VALIDA in df.columns,
            "padronizacao": (
                "StandardScaler dentro de Pipeline"
                if usar_padronizacao
                else "nenhuma"
            ),
            "max_iter_svm": MAX_ITER,
            "probabilidades": (
                "Platt scaling via CalibratedClassifierCV (sigmoid, ensemble=False), "
                "ajustado so no treino; y_previsto vem do SVC sem calibracao"
            ),
        },
        "atributos": atributos,
        "n_treino": int(len(treino)),
        "n_teste": int(len(teste)),
        "positivos_treino": int(treino[ALVO].sum()),
        "positivos_teste": int(teste[ALVO].sum()),
        "melhores_hiperparametros": busca.best_params_,
        "validacao_cruzada_melhor": {
            "f1_medio": float(busca.cv_results_["mean_test_f1"][busca.best_index_]),
            "recall_medio": float(busca.cv_results_["mean_test_recall"][busca.best_index_]),
            "precisao_media": float(busca.cv_results_["mean_test_precision"][busca.best_index_]),
        },
        "n_vetores_suporte": int(svm.n_support_.sum()),
        "importancia_permutacao_f1_teste": {
            a: {"media": float(m), "desvio": float(s)}
            for a, m, s in zip(
                atributos, importancia.importances_mean, importancia.importances_std
            )
        },
        "avaliacao_padronizacao": avaliacao_padronizacao,
        "teste": calcular_metricas(y_teste, y_prev),
    }

    # Kernel linear permite ler coeficientes (na escala padronizada, se houver).
    if svm.kernel == "linear":
        metricas["intercepto"] = float(svm.intercept_[0])
        metricas["coeficientes"] = {
            a: float(c) for a, c in zip(atributos, svm.coef_[0])
        }

    # Predicoes alinhadas ao teste (mesma ordem), para testes pareados.
    pred = pd.DataFrame({"indice_base": teste.index.to_numpy()})
    for c in COLUNAS_ID:
        if c in teste.columns:
            pred[c] = teste[c].to_numpy()
    if col_tempo:
        pred[col_tempo] = teste[col_tempo].to_numpy()
    pred["y_teste"] = y_teste
    pred["y_previsto"] = y_prev
    pred["prob_alagamento"] = prob
    pred["score_decisao"] = score_decisao
    pred["acerto"] = (pred["y_teste"] == pred["y_previsto"]).astype(int)

    PASTA_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_METRICAS, "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    pred.to_csv(ARQUIVO_PREDICOES, index=False, encoding="utf-8-sig")

    t = metricas["teste"]
    print("\n" + "=" * 65)
    print("SVM - RESUMO")
    print("=" * 65)
    print("Melhores hiperparametros:", busca.best_params_)
    print(f"CV ({args.metrica}): {busca.best_score_:.4f}")
    for nome in ("com_padronizacao", "sem_padronizacao"):
        if nome in avaliacao_padronizacao:
            v = avaliacao_padronizacao[nome]
            print(
                f"  {nome}: CV {v['score_cv_metrica_selecao']:.4f} | "
                f"teste F1 {v['teste']['f1_score']:.4f} | {v['tempo_busca_s']}s"
            )
    print(
        f"Teste -> acuracia {t['acuracia']:.4f} | precisao {t['precisao']:.4f} | "
        f"recall {t['recall']:.4f} | F1 {t['f1_score']:.4f}"
    )
    print("Matriz de confusao [[TN, FP], [FN, TP]]:", t["matriz_confusao"]["matriz"])
    print("Arquivos criados:")
    for a in (ARQUIVO_METRICAS, ARQUIVO_PREDICOES):
        print(" -", a.relative_to(RAIZ))


if __name__ == "__main__":
    main()
