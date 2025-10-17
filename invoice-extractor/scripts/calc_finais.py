
from __future__ import annotations
from typing import List, Dict, Optional
import pandas as pd

COLUMNS = [
    "Produto",
    "Núm. de hastes",
    "Subtotal do invoice",
    "Cotação do dólar",
    "Preço",
    "Custos de operação",
    "Total",
]

def finalize_table(items: List[Dict], cotacao: float, produtos: List[str], ops_costs_map: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Consolida itens normalizados (de qualquer fornecedor) na tabela final.
    items: lista com dicts contendo product, stems, value_usd (pelo menos)
    cotacao: valor em R$ informado no app
    produtos: lista canônica e ordem das linhas (produtos.json)
    ops_costs_map: custos manuais por produto (R$). Default 0.0 por produto.
    """
    df_items = pd.DataFrame(items) if items else pd.DataFrame(columns=["product","stems","value_usd"])

    # Agrupar por produto
    if not df_items.empty:
        g = df_items.groupby("product", dropna=False).agg(
            total_stems=("stems","sum"),
            subtotal_usd=("value_usd","sum"),
        ).reset_index().rename(columns={"product":"Produto"})
    else:
        g = pd.DataFrame(columns=["Produto","total_stems","subtotal_usd"])

    # Garantir todas as linhas em 'produtos' presentes
    have = set(g["Produto"]) if not g.empty else set()
    missing = [p for p in produtos if p not in have]
    if missing:
        add = pd.DataFrame({"Produto": missing, "total_stems": 0, "subtotal_usd": 0.0})
        g = pd.concat([g, add], ignore_index=True)

    # Ordenar conforme 'produtos'
    order = {p:i for i,p in enumerate(produtos)}
    g["__ord"] = g["Produto"].map(order).fillna(1_000_000).astype(int)
    g = g.sort_values("__ord").drop(columns="__ord")

    # Calcular colunas finais
    cot = float(cotacao or 0.0)
    ops = ops_costs_map or {}

    out = pd.DataFrame({
        "Produto": g["Produto"],
        "Núm. de hastes": g["total_stems"].astype(int),
        "Subtotal do invoice": g["subtotal_usd"].astype(float).round(2),  # USD
        "Cotação do dólar": cot,
    })
    out["Preço"] = (out["Subtotal do invoice"] * cot).round(2)            # BRL total
    out["Custos de operação"] = [float(ops.get(prod, 0.0) or 0.0) for prod in out["Produto"]]
    out["Total"] = [
        round(((preco + opsc) / stems), 4) if stems and stems > 0 else 0.0
        for preco, opsc, stems in zip(out["Preço"], out["Custos de operação"], out["Núm. de hastes"])
    ]

    return out[COLUMNS]
