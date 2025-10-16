
import json
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Tuple

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Extractor • Streamlit", layout="wide")
st.title("📦 Extração de Itens de Invoice (JSON)")
st.caption("Upload do JSON → planilha de produtos → agregações e validações")

def parse_decimal(x: str) -> Decimal:
    try:
        return Decimal(str(x).replace(",", ".")).quantize(Decimal("0.0001"))
    except (InvalidOperation, TypeError):
        return Decimal("0")

def parse_int(x: str) -> int:
    try:
        return int(str(x).strip())
    except Exception:
        # Alguns campos podem vir vazios
        try:
            return int(float(str(x).replace(",", ".").strip()))
        except Exception:
            return 0

def flatten_invoice(js: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    invs = js.get("invoices", [])
    if not invs:
        return pd.DataFrame(), {}

    inv = invs[0]
    meta = {
        "id_invoice": inv.get("id_invoice"),
        "tx_company": inv.get("tx_company"),
        "nm_bill": inv.get("nm_bill"),
        "nm_ship": inv.get("nm_ship"),
        "dt_invoice": inv.get("dt_invoice"),
        "dt_fly": inv.get("dt_fly"),
        "nu_totalstemsPO": parse_int(inv.get("nu_totalstemsPO")),
        "mny_total": parse_decimal(inv.get("mny_total")),
        "nu_boxes": parse_int(inv.get("nu_boxes", 0)),
    }

    rows: List[Dict[str, Any]] = []
    for box in inv.get("boxes", []):
        box_id = box.get("id_box")
        box_name = box.get("nm_box")
        for p in box.get("products", []):
            stems_per_bunch = parse_int(p.get("nu_stems_bunch"))
            bunches = parse_int(p.get("nu_bunches"))
            stems_total = stems_per_bunch * bunches
            rate = parse_decimal(p.get("mny_rate_stem"))
            value = (rate * Decimal(stems_total)).quantize(Decimal("0.0001"))

            rows.append({
                "invoice_id": meta["id_invoice"],
                "supplier": meta["tx_company"],
                "box_id": box_id,
                "box_name": box_name,
                "product_guid": p.get("gu_product"),
                "product_name": p.get("nm_product"),
                "species": p.get("nm_species"),
                "variety": p.get("nm_variety"),
                "length_cm": parse_int(p.get("nu_length")),
                "stems_per_bunch": stems_per_bunch,
                "bunches": bunches,
                "stems_total": stems_total,
                "rate_per_stem": float(rate),
                "value_total": float(value),
                "barcodes": p.get("barcodes")
            })

    df = pd.DataFrame(rows)
    return df, meta

st.sidebar.header("1) Upload do JSON")
up = st.sidebar.file_uploader("Selecione o arquivo .json", type=["json"])

if up is not None:
    js = json.loads(up.read().decode("utf-8", errors="ignore"))
    df, meta = flatten_invoice(js)

    if df.empty:
        st.warning("Nenhuma invoice encontrada no JSON.")
        st.stop()

    # KPIs
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric("Invoice", meta.get("id_invoice", "—"))
    with c2: st.metric("Fornecedor", meta.get("tx_company", "—"))
    with c3: st.metric("Caixas (JSON)", meta.get("nu_boxes", 0))
    with c4: st.metric("Hastes (JSON)", meta.get("nu_totalstemsPO", 0))
    with c5: st.metric("Valor total (JSON)", f"{meta.get('mny_total', 0)}")

    # Tabela de itens
    st.subheader("Itens extraídos")
    st.dataframe(
        df[["product_name","variety","length_cm","stems_per_bunch","bunches","stems_total","rate_per_stem","value_total","box_id"]],
        use_container_width=True,
        hide_index=True
    )

    # Agregações
    st.subheader("Agregações rápidas")
    agg_variety = df.groupby(["variety","length_cm"], as_index=False).agg(
        bunches=("bunches","sum"),
        stems=("stems_total","sum"),
        value=("value_total","sum")
    ).sort_values(["variety","length_cm"])

    agg_product = df.groupby(["product_name"], as_index=False).agg(
        bunches=("bunches","sum"),
        stems=("stems_total","sum"),
        value=("value_total","sum")
    ).sort_values("value", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        st.caption("Por variedade x comprimento")
        st.dataframe(agg_variety, use_container_width=True, hide_index=True)
    with c2:
        st.caption("Por produto")
        st.dataframe(agg_product, use_container_width=True, hide_index=True)

    # Validações
    st.subheader("Validações")
    stems_calc = int(df["stems_total"].sum())
    boxes_calc = df["box_id"].nunique()
    value_calc = round(df["value_total"].sum(), 2)

    ok_stems = stems_calc == int(meta.get("nu_totalstemsPO", 0))
    ok_boxes = boxes_calc == int(meta.get("nu_boxes", 0))

    st.write(f"**Hastes (calculadas)**: {stems_calc}  • **Hastes (JSON)**: {meta.get('nu_totalstemsPO', 0)}  →  "
             + ("✅ OK" if ok_stems else "⚠️ Divergente"))
    st.write(f"**Caixas (calculadas)**: {boxes_calc}  • **Caixas (JSON)**: {meta.get('nu_boxes', 0)}  →  "
             + ("✅ OK" if ok_boxes else "⚠️ Divergente"))
    st.write(f"**Valor total (calculado)**: {value_calc} (soma de stems × rate)")

    # Downloads
    st.subheader("Exportar")
    st.download_button(
        "Baixar itens (CSV)",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"itens_{meta.get('id_invoice','invoice')}.csv",
        mime="text/csv"
    )

    st.download_button(
        "Baixar agregação por variedade (CSV)",
        agg_variety.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"agregacao_variedade_{meta.get('id_invoice','invoice')}.csv",
        mime="text/csv"
    )

    st.download_button(
        "Baixar agregação por produto (CSV)",
        agg_product.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"agregacao_produto_{meta.get('id_invoice','invoice')}.csv",
        mime="text/csv"
    )
else:
    st.info("Faça o upload de um arquivo JSON para começar.")
