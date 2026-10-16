"""
Integração Filtrada e Robusta de Rótulos de Alagamento com a Base Ambiental
Gera: data/processed/base_integrada.csv
"""

from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PASTA_PROCESSADOS = RAIZ / "data" / "processed"
PASTA_ALAGAMENTOS = RAIZ / "data" / "raw" / "alagamentos"
ARQUIVO_AMBIENTAL = PASTA_PROCESSADOS / "base_ambiental.csv"
ARQUIVO_SAIDA = PASTA_PROCESSADOS / "base_integrada.csv"

# Categorias do Excel que indicam alagamento/impacto efetivo
CATEGORIAS_EFETIVAS = [
    'Alagamentos registrados',
    'Alagamentos + transbordamento',
    'Alagamento crônico / problema de drenagem',
    'Água invadiu unidade de saúde',
    'Alagamentos + famílias afetadas',
    'Casas atingidas / famílias afetadas',
    'Lâminas de água / canais elevados',
    'Registro de alagamento/inundação',
    'Alagamentos + bloqueios',
    'Alagamentos + vias interditadas',
    'Alagamentos recorrentes',
    'Problemas de alagamento'
]

def main():
    if not ARQUIVO_AMBIENTAL.exists():
        raise FileNotFoundError(
            f"Base ambiental não encontrada: {ARQUIVO_AMBIENTAL}. Execute o mare.py primeiro."
        )
    
    arquivos_excel = list(PASTA_ALAGAMENTOS.glob("*.xlsx")) + list(PASTA_ALAGAMENTOS.glob("*.xls"))
    if not arquivos_excel:
        arquivos_excel = list(RAIZ.glob("*.xlsx")) + list(RAIZ.glob("*.xls"))
    
    if not arquivos_excel:
        raise FileNotFoundError("Nenhum arquivo Excel (.xlsx) de alagamentos encontrado.")
    
    caminho_excel = arquivos_excel[0]
    print(f"[1/4] A carregar arquivo de ocorrências: {caminho_excel.name}...")
    df_labels = pd.read_excel(caminho_excel)
    df_labels.columns = df_labels.columns.str.strip()

    print(f"[2/4] A carregar base ambiental: {ARQUIVO_AMBIENTAL.name}...")
    df_ambiental = pd.read_csv(ARQUIVO_AMBIENTAL, encoding="utf-8-sig")
    df_ambiental["datahora_utc"] = pd.to_datetime(df_ambiental["datahora_utc"], utc=True)
    df_ambiental["data_str"] = df_ambiental["datahora_utc"].dt.strftime("%Y-%m-%d")

    # Processar Excel
    col_data = next(c for c in df_labels.columns if "data" in c.lower())
    df_labels["data_str"] = pd.to_datetime(df_labels[col_data], errors="coerce").dt.strftime("%Y-%m-%d")

    # Selecionar explicitamente a coluna de tipo ou ocorrência
    col_ocorrencia = next((c for c in df_labels.columns if "tipo" in c.lower() or "ocorrencia" in c.lower() or "ocorrência" in c.lower()), None)
    
    if col_ocorrencia:
        df_labels["alagamento"] = df_labels[col_ocorrencia].isin(CATEGORIAS_EFETIVAS).astype(int)
    else:
        raise ValueError("Coluna 'Tipo / ocorrência' não encontrada no Excel.")

    # Agrupar por data string para garantir o match exato
    resumo_efetivo = df_labels[df_labels["alagamento"] == 1].groupby("data_str")["alagamento"].max().reset_index()

    print("[3/4] A cruzar dados ambientais com os alagamentos efetivos por data...")
    df_integrada = pd.merge(df_ambiental, resumo_efetivo, on="data_str", how="left")
    df_integrada["alagamento"] = df_integrada["alagamento"].fillna(0).astype(int)
    df_integrada = df_integrada.drop(columns=["data_str"])

    PASTA_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    df_integrada.to_csv(ARQUIVO_SAIDA, index=False, encoding="utf-8-sig")

    # Estatísticas para o relatório
    total_linhas = len(df_integrada)
    total_positivos = int(df_integrada["alagamento"].sum())
    
    df_ambiental["alagamento_col"] = df_integrada["alagamento"]
    datas_com_alagamento = df_ambiental[df_ambiental["alagamento_col"] == 1].groupby("data_str").size().reset_index(name="registros_horarios")

    print("\n" + "=" * 65)
    print("       INTEGRAÇÃO FILTRADA CONCLUÍDA — RESUMO EXECUTIVO")
    print("=" * 65)
    print(f" • Arquivo de saída gerado  : {ARQUIVO_SAIDA.relative_to(RAIZ)}")
    print(f" • Total de registos na base: {total_linhas:,}")
    print(f" • Registos com alagamento  : {total_positivos:,} ({total_positivos/total_linhas*100:.2f}%)")
    print(f" • Datas únicas afetadas    : {len(datas_com_alagamento)}")
    print("-" * 65)
    print(" DATAS COM ALAGAMENTO EFETIVO E REGISTOS NA BASE:")
    print("-" * 65)
    print(f" {'DATA':<15} | {'REGISTOS HORÁRIOS NA BASE':<25}")
    print("-" * 65)
    for _, row in datas_com_alagamento.iterrows():
        print(f" {str(row['data_str']):<15} | {row['registros_horarios']:<25}")
    print("=" * 65)

if __name__ == "__main__":
    main()