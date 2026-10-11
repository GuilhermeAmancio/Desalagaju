from pathlib import Path

import numpy as np
import pandas as pd

# Aracaju utiliza UTC-3. America/Maceio representa o fuso local sem horário de verão.
FUSO_LOCAL = "America/Maceio"
JANELA = pd.Timedelta(hours=3)
INTERVALO_MAXIMO_MIN = 60

RAIZ = Path(__file__).resolve().parent.parent
PASTA_CEMADEN = RAIZ / "data" / "raw" / "cemaden"
PASTA_PROCESSADOS = RAIZ / "data" / "processed"
ARQUIVO_SAIDA = PASTA_PROCESSADOS / "chuva_acumulada_3h.csv"

COLUNAS_OBRIGATORIAS = ["codEstacao", "datahora", "valorMedida"]


def carregar_arquivos():
    """Lê e reúne todos os CSVs mensais do CEMADEN, preservando a origem."""
    arquivos = sorted(PASTA_CEMADEN.rglob("*.csv"))

    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum CSV foi encontrado em: {PASTA_CEMADEN}"
        )

    tabelas = []

    for arquivo in arquivos:
        print(f"Lendo: {arquivo.relative_to(RAIZ)}")

        df = pd.read_csv(
            arquivo,
            sep=None,
            engine="python",
            encoding="utf-8-sig",
            decimal=",",
        )
        df.columns = df.columns.str.strip()

        faltantes = [
            coluna
            for coluna in COLUNAS_OBRIGATORIAS
            if coluna not in df.columns
        ]
        if faltantes:
            raise ValueError(
                f"Colunas ausentes em {arquivo.name}: {faltantes}"
            )

        # O CEMADEN informa que seus dados são registrados em UTC.
        # utc=True interpreta os horários sem fuso do CSV como UTC.
        df["datahora_utc"] = pd.to_datetime(
            df["datahora"], errors="coerce", utc=True
        )
        df["valorMedida"] = pd.to_numeric(
            df["valorMedida"], errors="coerce"
        )
        df["arquivo_origem"] = arquivo.name

        tabelas.append(df)

    dados = pd.concat(tabelas, ignore_index=True)

    invalidos = dados[["codEstacao", "datahora_utc", "valorMedida"]].isna().any(axis=1)
    if invalidos.any():
        raise ValueError(
            f"Foram encontradas {int(invalidos.sum())} linhas com estação, "
            "data/hora ou medição inválida. Corrija/inspecione os CSVs antes "
            "de calcular os atributos; nenhuma linha foi descartada automaticamente."
        )

    duplicados = dados.duplicated(
        subset=["codEstacao", "datahora_utc"], keep=False
    )
    if duplicados.any():
        exemplos = dados.loc[
            duplicados, ["codEstacao", "datahora_utc", "arquivo_origem"]
        ].head(10)
        raise ValueError(
            "Há medições duplicadas para a mesma estação e horário. "
            "Inspecione estes exemplos antes de continuar:\n"
            + exemplos.to_string(index=False)
        )

    # Mantém a coluna datahora original, mas cria duas colunas explícitas
    # para evitar confundir UTC com o horário de Aracaju.
    dados["datahora_local"] = (
        dados["datahora_utc"].dt.tz_convert(FUSO_LOCAL)
    )

    return dados.sort_values(
        ["codEstacao", "datahora_utc"]
    ).reset_index(drop=True), len(arquivos)


def calcular_chuva_3h_por_estacao(grupo):
    """
    Soma as medições com horário em (t - 3h, t], separadamente por estação.

    A janela só é marcada como válida se houver observação antes/na borda
    inicial e nenhum intervalo entre observações necessário à janela exceder
    60 minutos. O limite de 60 min permite os registros horários de zero que
    o CEMADEN informa transmitir em períodos sem chuva.

    A validade é um controle conservador de cobertura temporal; não garante
    que uma falha de transmissão menor que 60 min não tenha ocorrido.
    """
    grupo = grupo.sort_values("datahora_utc").copy()
    tempos = pd.DatetimeIndex(grupo["datahora_utc"]).as_unit("ns")
    valores = grupo["valorMedida"].to_numpy(dtype=float)

    acumulada = np.full(len(grupo), np.nan, dtype=float)
    janela_valida = np.zeros(len(grupo), dtype=bool)
    n_medicoes = np.zeros(len(grupo), dtype=int)
    maior_intervalo = np.full(len(grupo), np.nan, dtype=float)

    limite_ns = pd.Timedelta(minutes=INTERVALO_MAXIMO_MIN).value
    tempos_ns = tempos.asi8
    janela_ns = JANELA.value

    for i, tempo_ns in enumerate(tempos_ns):
        inicio_ns = tempo_ns - janela_ns

        # Janela aberta à esquerda e fechada à direita: (t - 3h, t].
        inicio = np.searchsorted(tempos_ns, inicio_ns, side="right")
        n_medicoes[i] = i - inicio + 1

        if inicio > i:
            continue

        # O registro imediatamente anterior à primeira medição da janela
        # ajuda a verificar se a série cobre a borda inicial.
        if inicio == 0:
            continue

        intervalos_ns = np.diff(tempos_ns[inicio - 1 : i + 1])
        if len(intervalos_ns) == 0:
            continue

        maior_min = float(intervalos_ns.max() / 60_000_000_000)
        maior_intervalo[i] = maior_min

        tem_chuva = bool((valores[inicio : i + 1] > 0).any())

        limite_janela_ns = pd.Timedelta(
            minutes=10 if tem_chuva else 60
        ).value

        cobertura_borda = (
            (tempos_ns[inicio] - inicio_ns) <= limite_janela_ns
        )

        sem_lacunas_grandes = bool(
            (intervalos_ns <= limite_janela_ns).all()
        )

        if cobertura_borda and sem_lacunas_grandes:
            janela_valida[i] = True
            acumulada[i] = valores[inicio : i + 1].sum()

    grupo["chuva_acumulada_3h_mm"] = acumulada
    grupo["janela_3h_valida"] = janela_valida
    grupo["n_medicoes_3h"] = n_medicoes
    grupo["maior_intervalo_min_3h"] = maior_intervalo

    return grupo


def main():
    dados, quantidade_arquivos = carregar_arquivos()

    grupos = []
    for _, grupo in dados.groupby("codEstacao", sort=False):
        grupos.append(calcular_chuva_3h_por_estacao(grupo))

    resultado = pd.concat(grupos, ignore_index=True)
    resultado = resultado.sort_values(
        ["codEstacao", "datahora_utc"]
    ).reset_index(drop=True)

    PASTA_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(ARQUIVO_SAIDA, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 65)
    print("ENGENHARIA DE ATRIBUTOS — RESUMO")
    print("=" * 65)
    print(f"Arquivos lidos: {quantidade_arquivos}")
    print(f"Registros de saída: {len(resultado)}")
    print(f"Estações: {resultado['codEstacao'].nunique()}")
    print("Período UTC:", resultado["datahora_utc"].min(), "a", resultado["datahora_utc"].max())
    print("Período local:", resultado["datahora_local"].min(), "a", resultado["datahora_local"].max())
    print(
        "Janelas de 3h válidas:",
        int(resultado["janela_3h_valida"].sum()),
        f"({resultado['janela_3h_valida'].mean() * 100:.2f}%)",
    )
    print(
        "Janelas inválidas:",
        int((~resultado["janela_3h_valida"]).sum()),
    )
    print("Arquivo criado:", ARQUIVO_SAIDA)
    print("\nAtenção:")
    print("- A chuva de 3h é calculada separadamente para cada estação.")
    print("- Janelas sem cobertura temporal suficiente ficam com valor NaN.")
    print("- Os CSVs originais não foram modificados.")


if __name__ == "__main__":
    main()