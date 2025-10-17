
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

class FloresPrismaJSON:
    """
    Extrator para fornecedor 'Flores Prisma' (JSON).
    - Aplica de-para por 'nm_product' usando depara.json (mesma pasta por padrão)
    - Emite o schema canônico: product, stems, rate_usd, value_usd, source_file

    Regras:
      - Se nm_product for nulo => ignora a linha.
      - stems = nu_stems_bunch * nu_bunches
      - rate_usd = mny_rate_stem
      - value_usd = stems * rate_usd
    """

    name = "flores_prisma_json"

    def __init__(self, depara_path: Optional[str] = None) -> None:
        # Procura o de-para na mesma pasta do arquivo por padrão
        self.depara_path = depara_path or str(Path(__file__).with_name("depara.json"))
        self._default = "Coloridas"
        self.depara_map = self._load_depara(self.depara_path)

    # ---------- helpers ----------

    @staticmethod
    def _parse_int(v) -> int:
        try:
            return int(str(v).strip())
        except Exception:
            try:
                return int(float(str(v).replace(",", ".").strip()))
            except Exception:
                return 0

    @staticmethod
    def _parse_float(v) -> float:
        # Corrigido: não remover ponto decimal. Apenas troca vírgula por ponto.
        try:
            return float(str(v).replace(",", ".").strip())
        except Exception:
            try:
                return float(v)
            except Exception:
                return 0.0

    def _load_depara(self, path: str) -> Dict[str, str]:
        try:
            js = json.loads(Path(path).read_text(encoding="utf-8"))
            self._default = js.get("default", "Coloridas")
            rules = js.get("regras", [])
            return {r.get("match"): r.get("produto") for r in rules if r.get("match")}
        except Exception:
            return {}

    def _map_product(self, nm_product: Optional[str]) -> Optional[str]:
        if nm_product is None:
            return None  # regra: não classificar
        nm = str(nm_product).strip()
        return self.depara_map.get(nm, self._default)

    # ---------- main ----------

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        data = json.loads(Path(file_path).read_text(encoding="utf-8", errors="ignore"))
        invs = data.get("invoices", [])
        if not invs:
            return []
        inv = invs[0]

        out: List[Dict[str, Any]] = []
        for box in inv.get("boxes", []):
            for p in box.get("products", []):
                nm_product = p.get("nm_product")
                product = self._map_product(nm_product)
                if product is None:
                    # nm_product nulo: ignorar
                    continue

                stems_per_bunch = self._parse_int(p.get("nu_stems_bunch"))
                bunches = self._parse_int(p.get("nu_bunches") or 1)
                stems = stems_per_bunch * bunches

                rate  = self._parse_float(p.get("mny_rate_stem"))
                value = stems * rate

                out.append({
                    "product": product,
                    "stems": stems,
                    "rate_usd": rate,
                    "value_usd": value,
                    "source_file": Path(file_path).name,
                })

        return out
