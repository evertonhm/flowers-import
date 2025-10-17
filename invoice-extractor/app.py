
import gradio as gr
import pandas as pd
import importlib
import json
from pathlib import Path
from scripts.calc_finais import finalize_table

# Paths
PRODUTOS_PATH = Path("produtos.json")
FORNECEDORES_PATH = Path("fornecedores.json")

def carregar_produtos():
    if PRODUTOS_PATH.exists():
        try:
            data = json.loads(PRODUTOS_PATH.read_text(encoding="utf-8"))
            return [p.get("nome") for p in data.get("produtos", []) if p.get("nome")]
        except Exception:
            pass
    return ["Freedom 70/80", "Freedom 60", "Freedom 50", "Coloridas"]

def carregar_fornecedores():
    try:
        data = json.loads(FORECEDORES_PATH.read_text(encoding="utf-8"))
        ids = [f.get("id") for f in data.get("fornecedores", []) if f.get("id")]
        return ids if ids else ["flores_prisma"]
    except Exception:
        return ["flores_prisma"]

FINAL_COLUMNS = [
    "Produto",
    "Núm. de hastes",
    "Subtotal do invoice",
    "Cotação do dólar",
    "Preço",
    "Custos de operação",
    "Total",
]

# ---------- Helpers de formatação/parse (pt-BR) ----------
def _fmt_num_br(value: float) -> str:
    try:
        s = f"{float(value):,.2f}"  # 1,234,567.89
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234.567,89
        return s
    except Exception:
        return "0,00"

def fmt_brl(value: float) -> str:
    return f"R$ {_fmt_num_br(value)}"

def fmt_usd(value: float) -> str:
    return f"$ {_fmt_num_br(value)}"

def parse_brl_to_float(text) -> float:
    if text is None:
        return 0.0
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip()
    for sym in ["R$", "$"]:
        s = s.replace(sym, "")
    s = s.replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def format_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    out = df.copy()
    if "Subtotal do invoice" in out.columns:
        out["Subtotal do invoice"] = out["Subtotal do invoice"].apply(fmt_usd)
    for col in ["Cotação do dólar", "Preço", "Custos de operação", "Total"]:
        if col in out.columns:
            out[col] = out[col].apply(fmt_brl)
    return out

def empty_table():
    produtos = carregar_produtos()
    df = pd.DataFrame([[p, 0, 0.0, 0.0, 0.0, 0.0, 0.0] for p in produtos], columns=FINAL_COLUMNS)
    return format_display(df)

def processar_arquivos(files, fornecedores, cotacao_dolar):
    all_items = []
    logs = []

    for (file, fornecedor) in zip(files, fornecedores):
        if not file or not fornecedor:
            continue
        try:
            module_path = f"scripts.{fornecedor}.parser"
            module = importlib.import_module(module_path)
            parser_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type):
                    parser_class = attr
                    break
            if not parser_class:
                logs.append(f"❌ Parser não encontrado para {fornecedor}")
                continue
            parser = parser_class()
            items = parser.parse(file.name)
            all_items.extend(items)
            logs.append(f"✅ {file.name} processado com sucesso ({fornecedor})")
        except Exception as e:
            logs.append(f"⚠️ Erro ao processar {file.name}: {e}")

    produtos = carregar_produtos()
    df_final = finalize_table(all_items, float(cotacao_dolar or 0), produtos)
    return format_display(df_final), "\n".join(logs), all_items

def app_ui():
    fornecedores_opcoes = carregar_fornecedores()

    with gr.Blocks(title="Extração e Consolidação de Dados") as demo:
        
        gr.HTML("""
<style>
  /* Fonte levemente menor e sem quebra */
  #result-table table,
  #result-table thead th,
  #result-table tbody td {
    font-size: 0.92rem;
    line-height: 1.1;
    white-space: nowrap;
  }

  /* Larguras mínimas para colunas longas (Produto/Preço/Total) */
  #result-table thead th:nth-child(1),
#result-table tbody td:nth-child(1) {
  min-width: 260px;
}

  #result-table thead th:nth-child(5),
#result-table tbody td:nth-child(5) {
  min-width: 170px;
}

  #result-table thead th:nth-child(7),
#result-table tbody td:nth-child(7) {
  min-width: 210px;
}

  /* Em telas menores, diminui um pouco mais a fonte e aumenta um pouco a largura */
  @media (max-width: 900px) {
    #result-table table,
    #result-table thead th,
    #result-table tbody td {
      font-size: 0.86rem;
    }
    /* ligeiro reforço nas colunas largas */

#result-table thead th:nth-child(1),
#result-table tbody td:nth-child(1) {
  min-width: 280px;
}

#result-table thead th:nth-child(5),
#result-table tbody td:nth-child(5) {
  min-width: 180px;
}

#result-table thead th:nth-child(7),
#result-table tbody td:nth-child(7) {
  min-width: 230px;
}
  }
</style>
        """)
        gr.Markdown("## 📦 Extração e Consolidação de Dados de Fornecedores")

        last_items = gr.State([])

        with gr.Row():
            with gr.Column(scale=3):
                uploads = gr.Files(label="Adicionar arquivos (JSON ou PDF)", file_count="multiple", type="filepath", file_types=[".json", ".pdf"])

                MAX_FILES = 20
                row_containers = []
                name_labels = []
                analyze_checks = []
                supplier_dds = []

                for i in range(MAX_FILES):
                    with gr.Row(visible=False) as row:
                        lbl = gr.Markdown("")
                        cb  = gr.Checkbox(label="analisar", value=True)
                        dd  = gr.Dropdown(label="fornecedor", choices=fornecedores_opcoes, value=(fornecedores_opcoes[0] if fornecedores_opcoes else None))
                    row_containers.append(row)
                    name_labels.append(lbl)
                    analyze_checks.append(cb)
                    supplier_dds.append(dd)

                cotacao = gr.Number(label="Cotação do dólar (R$)", value=5.00, precision=4)
                process_btn = gr.Button("▶️ Processar", variant="primary")

            with gr.Column(scale=9):
                out_table = gr.Dataframe(elem_id="result-table", value=empty_table(), headers=FINAL_COLUMNS, wrap=False, interactive=True, label="Resultados")
                logs = gr.Markdown("Aguardando processamento…")
                download = gr.DownloadButton(label="Baixar tabela (CSV)", visible=False)

        def on_files_change(files):
            names = []
            if files:
                for f in files:
                    names.append(Path(f.name if hasattr(f, "name") else str(f)).name)
            row_updates = [gr.update(visible=(i < len(names))) for i in range(MAX_FILES)]
            label_updates = [gr.update(value=f"**{names[i]}**") if i < len(names) else gr.update(value="") for i in range(MAX_FILES)]
            cb_updates = [gr.update(value=True, visible=(i < len(names))) for i in range(MAX_FILES)]
            dd_updates = [gr.update(value=(fornecedores_opcoes[0] if fornecedores_opcoes else None), choices=fornecedores_opcoes, visible=(i < len(names))) for i in range(MAX_FILES)]
            return (*row_updates, *label_updates, *cb_updates, *dd_updates)

        uploads.change(
            on_files_change,
            inputs=[uploads],
            outputs=[*row_containers, *name_labels, *analyze_checks, *supplier_dds],
        )

        def run_processing(files, *args):
            n = len(files or [])
            names = []
            if files:
                for f in files:
                    names.append(Path(f.name if hasattr(f, "name") else str(f)).name)

            idx = 0
            labels_vals = args[idx: idx+MAX_FILES]; idx += MAX_FILES
            checks_vals = args[idx: idx+MAX_FILES]; idx += MAX_FILES
            dds_vals    = args[idx: idx+MAX_FILES]; idx += MAX_FILES
            cotacao_val = args[idx]

            filtered_files = []
            filtered_suppliers = []
            for i in range(min(n, MAX_FILES)):
                if bool(checks_vals[i]):
                    filtered_files.append(files[i])
                    filtered_suppliers.append(dds_vals[i])

            if not filtered_files:
                return empty_table(), "Nenhum arquivo selecionado para análise.", []

            df, log, items = processar_arquivos(filtered_files, filtered_suppliers, cotacao_val)
            return df, log, items

        result = process_btn.click(
            run_processing,
            inputs=[uploads, *name_labels, *analyze_checks, *supplier_dds, cotacao],
            outputs=[out_table, logs, last_items]
        )

        def on_table_change(current_df, cotacao_val, items):
            try:
                df = pd.DataFrame(current_df, columns=FINAL_COLUMNS) if not isinstance(current_df, pd.DataFrame) else current_df
            except Exception:
                df = pd.DataFrame(current_df)
            ops_map = {}
            if not df.empty and "Produto" in df.columns and "Custos de operação" in df.columns:
                for _, row in df.iterrows():
                    prod = row.get("Produto")
                    cost = row.get("Custos de operação")
                    ops_map[prod] = parse_brl_to_float(cost)
            produtos = carregar_produtos()
            numeric_df = finalize_table(items or [], float(cotacao_val or 0), produtos, ops_costs_map=ops_map)
            return format_display(numeric_df)

        out_table.change(on_table_change, inputs=[out_table, cotacao, last_items], outputs=[out_table])
        cotacao.change(on_table_change, inputs=[out_table, cotacao, last_items], outputs=[out_table])

        def to_csv(df_display: pd.DataFrame):
            tmp = Path("/tmp/resultado.csv")
            if isinstance(df_display, pd.DataFrame):
                df_display.to_csv(tmp, index=False, sep=";", encoding="utf-8-sig")
            else:
                pd.DataFrame(df_display).to_csv(tmp, index=False, sep=";", encoding="utf-8-sig")
            return str(tmp), gr.update(visible=True)

        result.then(to_csv, inputs=[out_table], outputs=[download, download])

    return demo

if __name__ == "__main__":
    app_ui().launch()
