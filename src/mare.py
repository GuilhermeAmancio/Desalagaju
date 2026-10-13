"""
Maré — Desalagaju

Extrai as tábuas de maré (DHN / Capitania dos Portos de Sergipe) dos PDFs em
data/raw/mare/, valida a extração e interpola o nível de maré para qualquer
instante (preamares e baixa-mares -> nível contínuo).

Saídas:
    data/processed/mare_extremos.csv   (um registro por preamar/baixa-mar)
    data/processed/base_ambiental.csv  (chuva 3h + nivel_mare, SEM rótulo de
                                         alagamento; só é gerada se existir
                                         data/processed/chuva_acumulada_3h.csv)

Uso (a partir da raiz do repositório):
    python src/mare.py

Atenção: a tábua traz a maré ASTRONÔMICA PREVISTA, não a medida. Efeitos
meteorológicos (ressaca, vento, pressão) não estão incluídos.
"""

import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pdfplumber

# A tábua informa "Fuso UTC -03.0 horas". America/Maceio é UTC-3 sem horário
# de verão, o mesmo fuso usado em engenharia_atributos.py.
FUSO_LOCAL = "America/Maceio"

RAIZ = Path(__file__).resolve().parent.parent
PASTA_MARE = RAIZ / "data" / "raw" / "mare"
PASTA_PROCESSADOS = RAIZ / "data" / "processed"
ARQUIVO_EXTREMOS = PASTA_PROCESSADOS / "mare_extremos.csv"
ARQUIVO_CHUVA = PASTA_PROCESSADOS / "chuva_acumulada_3h.csv"
ARQUIVO_AMBIENTAL = PASTA_PROCESSADOS / "base_ambiental.csv"

MESES = {
    "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4,
    "Maio": 5, "Junho": 6, "Julho": 7, "Agosto": 8,
    "Setembro": 9, "Outubro": 10, "Novembro": 11, "Dezembro": 12,
}
# Intervalo máximo plausível entre duas extremidades consecutivas (horas).
# Maré semidiurna: ~6h12min. Acima disso há dado faltando.
GAP_MAXIMO_H = 9.0


# --------------------------------------------------------------------------
# Extração dos PDFs
# --------------------------------------------------------------------------
def _agrupar_posicoes(valores, tolerancia=5.0):
    grupos = []
    for v in sorted(valores):
        if grupos and v - grupos[-1][-1] <= tolerancia:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return [float(np.mean(g)) for g in grupos]


def _palavras(pagina, gap_maximo=1.2, tolerancia_linha=1.0):
    """
    Reconstrói as "palavras" a partir dos caracteres. O extract_words padrão
    do pdfplumber quebra alguns números (ex.: "0917" -> "091" + "7") quando os
    caracteres vêm fora de ordem no PDF; aqui eles são reordenados por posição.
    """
    palavras = []
    for negrito in (True, False):
        chars = [
            c for c in pagina.chars
            if c["text"].strip() and ("Bold" in c["fontname"]) == negrito
        ]
        chars.sort(key=lambda c: c["top"])
        linhas, atual = [], []
        for c in chars:
            if atual and c["top"] - atual[0]["top"] > tolerancia_linha:
                linhas.append(atual)
                atual = []
            atual.append(c)
        if atual:
            linhas.append(atual)

        for linha in linhas:
            linha.sort(key=lambda c: c["x0"])
            token = [linha[0]]
            for c in linha[1:]:
                if c["x0"] - token[-1]["x1"] > gap_maximo:
                    palavras.append(_montar(token, negrito))
                    token = []
                token.append(c)
            palavras.append(_montar(token, negrito))
    return palavras


def _montar(chars, negrito):
    return {
        "text": "".join(c["text"] for c in chars),
        "x0": min(c["x0"] for c in chars),
        "top": float(np.mean([c["top"] for c in chars])),
        "fontname": "Bold" if negrito else "Roman",
    }


def _extrair_pagina(pagina, ano, arquivo):
    palavras = _palavras(pagina)
    negrito = [w for w in palavras if "Bold" in w["fontname"]]

    cabecalhos = sorted(
        (w for w in negrito if w["text"] in MESES), key=lambda w: w["x0"]
    )
    if not cabecalhos:
        return []

    topo_dados = cabecalhos[0]["top"] + 10
    dias = [
        w for w in negrito
        if re.fullmatch(r"\d{2}", w["text"]) and w["top"] > topo_dados
    ]
    colunas = _agrupar_posicoes([w["x0"] for w in dias])
    if len(colunas) != 2 * len(cabecalhos):
        raise ValueError(
            f"{arquivo}: layout inesperado ({len(colunas)} colunas de dias "
            f"para {len(cabecalhos)} meses)."
        )

    horas = [w for w in palavras if re.fullmatch(r"\d{4}", w["text"])]
    alturas = [w for w in palavras if re.fullmatch(r"-?\d+\.\d{2}", w["text"])]

    registros = []
    for idx_col, x_col in enumerate(colunas):
        mes = MESES[cabecalhos[idx_col // 2]["text"]]
        do_col = sorted(
            (w for w in dias if abs(w["x0"] - x_col) <= 5.0),
            key=lambda w: w["top"],
        )
        for i, dia in enumerate(do_col):
            t0 = dia["top"] - 1
            t1 = do_col[i + 1]["top"] - 1 if i + 1 < len(do_col) else 1e9
            for h in horas:
                if not (t0 <= h["top"] < t1):
                    continue
                if not (x_col + 10 <= h["x0"] <= x_col + 30):
                    continue
                alt = [
                    a for a in alturas
                    if abs(a["top"] - h["top"]) < 1.5
                    and x_col + 30 < a["x0"] < x_col + 60
                ]
                if len(alt) != 1:
                    raise ValueError(
                        f"{arquivo}: altura não encontrada para "
                        f"{ano}-{mes:02d}-{dia['text']} {h['text']}."
                    )
                hh, mm = int(h["text"][:2]), int(h["text"][2:])
                registros.append(
                    {
                        "datahora_local_naive": datetime(
                            ano, mes, int(dia["text"]), hh, mm
                        ),
                        "altura_m": float(alt[0]["text"]),
                        "arquivo_origem": arquivo,
                    }
                )
    return registros


def extrair_tabuas(pdfs):
    registros = []
    for pdf_path in pdfs:
        print(f"Lendo: {pdf_path.name}")
        with pdfplumber.open(pdf_path) as pdf:
            for pagina in pdf.pages:
                m = re.search(
                    r"\(ESTADO DE SERGIPE\)\s*-\s*(\d{4})",
                    pagina.extract_text() or "",
                )
                if not m:
                    raise ValueError(f"Ano não encontrado em {pdf_path.name}.")
                registros += _extrair_pagina(pagina, int(m.group(1)), pdf_path.name)

    df = pd.DataFrame(registros)
    if df.empty:
        raise ValueError("Nenhuma maré extraída dos PDFs.")

    df = df.sort_values("datahora_local_naive").reset_index(drop=True)
    local = pd.DatetimeIndex(df["datahora_local_naive"]).tz_localize(FUSO_LOCAL)
    df["datahora_local"] = local
    df["datahora_utc"] = local.tz_convert("UTC")
    return df.drop(columns="datahora_local_naive")


def validar_extremos(df):
    """Falha se a extração for inconsistente; devolve um resumo."""
    problemas = []

    if df["datahora_utc"].duplicated().any():
        problemas.append("horários duplicados")

    # Dias esperados vs encontrados, por mês.
    datas = pd.DatetimeIndex(df["datahora_local"]).tz_localize(None).normalize()
    esperado = pd.date_range(datas.min(), datas.max(), freq="D")
    faltam = esperado.difference(datas.unique())
    if len(faltam):
        problemas.append(f"{len(faltam)} dia(s) sem registro: {list(faltam[:5].date)}")

    por_dia = pd.Series(datas).value_counts()
    fora = por_dia[~por_dia.isin([3, 4])]
    if len(fora):
        problemas.append(f"{len(fora)} dia(s) com nº de marés diferente de 3/4")

    # Preamares e baixa-mares devem se alternar.
    sinais = np.sign(np.diff(df["altura_m"].to_numpy()))
    n_nao_alterna = int((sinais[1:] == sinais[:-1]).sum())
    if n_nao_alterna:
        problemas.append(f"{n_nao_alterna} ponto(s) sem alternância preamar/baixa-mar")

    gaps_h = df["datahora_utc"].diff().dt.total_seconds().dropna() / 3600
    if (gaps_h > GAP_MAXIMO_H).any() or (gaps_h < 3).any():
        problemas.append(
            f"intervalos fora de 3–{GAP_MAXIMO_H:.0f} h "
            f"(mín {gaps_h.min():.2f} h, máx {gaps_h.max():.2f} h)"
        )

    if problemas:
        raise ValueError("Extração de maré inconsistente: " + "; ".join(problemas))

    return {
        "registros": int(len(df)),
        "inicio_local": str(df["datahora_local"].min()),
        "fim_local": str(df["datahora_local"].max()),
        "altura_min_m": float(df["altura_m"].min()),
        "altura_max_m": float(df["altura_m"].max()),
        "intervalo_min_h": float(gaps_h.min()),
        "intervalo_max_h": float(gaps_h.max()),
    }


# --------------------------------------------------------------------------
# Interpolação
# --------------------------------------------------------------------------
def interpolar_nivel_mare(instantes_utc, extremos):
    """
    Nível de maré (m) nos instantes dados, por interpolação em cosseno entre
    preamares e baixa-mares consecutivas (aproximação padrão para maré
    semidiurna). Fora da cobertura da tábua, ou onde houver um intervalo
    maior que GAP_MAXIMO_H entre extremos, o resultado é NaN.
    """
    ext = extremos.sort_values("datahora_utc")
    t_ext = pd.DatetimeIndex(ext["datahora_utc"]).as_unit("ns").asi8
    h_ext = ext["altura_m"].to_numpy(dtype=float)

    t = pd.DatetimeIndex(pd.to_datetime(instantes_utc, utc=True)).as_unit("ns").asi8
    pos = np.searchsorted(t_ext, t, side="right") - 1
    valido = (pos >= 0) & (pos < len(t_ext) - 1)

    i = np.clip(pos, 0, len(t_ext) - 2)
    t1, t2 = t_ext[i], t_ext[i + 1]
    h1, h2 = h_ext[i], h_ext[i + 1]

    valido &= (t2 - t1) <= GAP_MAXIMO_H * 3600 * 1e9
    frac = np.where(valido, (t - t1) / np.where(t2 > t1, t2 - t1, 1), np.nan)
    nivel = h1 + (h2 - h1) * (1 - np.cos(np.pi * frac)) / 2
    return np.where(valido, nivel, np.nan)


def main():
    pdfs = sorted(PASTA_MARE.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"Nenhum PDF de maré em: {PASTA_MARE}")

    extremos = extrair_tabuas(pdfs)
    resumo = validar_extremos(extremos)

    PASTA_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    extremos.to_csv(ARQUIVO_EXTREMOS, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 65)
    print("MARÉ — RESUMO")
    print("=" * 65)
    for k, v in resumo.items():
        print(f"{k}: {v}")
    print("Arquivo criado:", ARQUIVO_EXTREMOS)

    if ARQUIVO_CHUVA.exists():
        chuva = pd.read_csv(ARQUIVO_CHUVA, encoding="utf-8-sig")
        chuva["datahora_utc"] = pd.to_datetime(chuva["datahora_utc"], utc=True)
        chuva["nivel_mare"] = interpolar_nivel_mare(chuva["datahora_utc"], extremos)
        sem_mare = int(chuva["nivel_mare"].isna().sum())
        chuva.to_csv(ARQUIVO_AMBIENTAL, index=False, encoding="utf-8-sig")
        print(f"Registros com nivel_mare: {len(chuva) - sem_mare} de {len(chuva)}")
        print("Arquivo criado:", ARQUIVO_AMBIENTAL)
        print("Obs.: sem a coluna 'alagamento'; os rótulos ainda precisam ser unidos.")
    else:
        print(f"{ARQUIVO_CHUVA.name} não encontrado; base_ambiental não gerada.")


if __name__ == "__main__":
    main()
