"""
Lógica de inferencia: equivalente en Python de recomendar_precio() y
explicar_precio() (TFM_ModeloPrecio.qmd, sección 10). No reentrena nada:
carga el modelo XGBoost ya entrenado en R y las tablas de referencia
exportadas desde ahí.
"""
 
import json
from pathlib import Path
 
import numpy as np
import pandas as pd
import xgboost as xgb
 
DATOS = Path(__file__).parent.parent / "datos"
 
 
class ModeloPrecio:
    def __init__(self, datos_dir: Path = DATOS):
        # --- Modelo ---
        self.bst = xgb.Booster()
        self.bst.load_model(str(datos_dir / "modelo_xgb.json"))
 
        # Lista exacta y ordenada de columnas que espera el modelo (incluye
        # "(Intercept)"), leída del propio modelo — no se reconstruye a mano.
        self.feature_names = self.bst.feature_names
        if self.feature_names is None:
            raise RuntimeError(
                "El modelo no trae feature_names embebidos. Hay que "
                "reexportarlo desde R asegurando que la matriz de "
                "entrenamiento tenía colnames (as.matrix(predictoras) los "
                "conserva si predictoras ya los tenía)."
            )
 
        # --- Tablas de referencia ---
        with open(datos_dir / "shap_mapeo.json", encoding="utf-8") as f:
            mapeo = json.load(f)
        self.vars_modelo = mapeo["vars_modelo"]
        self.cols_shap = mapeo["cols_shap"]  # mismas cols que feature_names sin "(Intercept)" ni "BIAS"
 
        self.cuantiles_ciudad = pd.read_csv(datos_dir / "cuantiles_ciudad.csv").set_index("city")
        self.referencias_ciudad = pd.read_csv(datos_dir / "referencias_ciudad.csv").set_index("city")
        self.centros_ciudad = pd.read_csv(datos_dir / "centros_ciudad.csv").set_index("city")
        self.base_ciudad = pd.read_csv(datos_dir / "base_ciudad.csv").set_index("city")
 
        with open(datos_dir / "metadatos_variables.json", encoding="utf-8") as f:
            self.metadatos = {m["variable"]: m for m in json.load(f)}
 
        # Para cada columna del modelo, a qué variable original pertenece
        # (mismo algoritmo de "prefijo más largo" que en R, sección 10.5)
        self._col_a_variable = {}
        for col in self.feature_names:
            candidatas = [v for v in self.vars_modelo if col.startswith(v)]
            self._col_a_variable[col] = max(candidatas, key=len) if candidatas else None
 
    # ------------------------------------------------------------------
    def _construir_vector(self, listing: dict) -> np.ndarray:
        """listing: dict con las 15 variables (claves = vars_modelo)."""
        faltantes = set(self.vars_modelo) - set(listing)
        if faltantes:
            raise ValueError(f"Faltan variables en el listing: {faltantes}")
 
        valores = []
        for col in self.feature_names:
            if col == "(Intercept)":
                valores.append(1.0)
                continue
 
            var = self._col_a_variable[col]
            if var is None:
                raise ValueError(f"Columna del modelo sin variable asociada: {col}")
 
            valor_listing = listing[var]
            resto = col[len(var):]
 
            if resto == "":
                # Passthrough numérico
                valores.append(float(valor_listing))
            elif resto.startswith("."):
                # Dummy categórica: "<var>.<nivel>"
                nivel = resto[1:]
                valores.append(1.0 if str(valor_listing) == nivel else 0.0)
            elif resto == "TRUE":
                # Dummy lógica
                valores.append(1.0 if bool(valor_listing) else 0.0)
            else:
                raise ValueError(f"Sufijo de columna no reconocido: {col!r} (resto={resto!r})")
 
        return np.array(valores, dtype=float).reshape(1, -1)
 
    def _dmatrix(self, listing: dict) -> xgb.DMatrix:
        vector = self._construir_vector(listing)
        return xgb.DMatrix(vector, feature_names=self.feature_names)
 
    @staticmethod
    def _redondeo_precio(x: float) -> float:
        return round(x, 1) if x < 10 else round(x)
 
    # ------------------------------------------------------------------
    def recomendar_precio(self, listing: dict) -> dict:
        ciudad = listing["city"]
        dmat = self._dmatrix(listing)
        log_pred = float(self.bst.predict(dmat)[0])
 
        ref = self.referencias_ciudad.loc[ciudad]
        q = self.cuantiles_ciudad.loc[ciudad]
        log_min = log_pred + q["q_inf"]
        log_max = log_pred + q["q_sup"]
 
        return {
            "ciudad": ciudad,
            "moneda": ref["moneda"],
            "pos_relativa_pct": (np.exp(log_pred) - 1) * 100,
            "pos_min_pct": (np.exp(log_min) - 1) * 100,
            "pos_max_pct": (np.exp(log_max) - 1) * 100,
            "precio_local": round(np.exp(log_pred) * ref["mediana_local"]),
            "rango_local_min": round(np.exp(log_min) * ref["mediana_local"]),
            "rango_local_max": round(np.exp(log_max) * ref["mediana_local"]),
            "precio_eur": self._redondeo_precio(np.exp(log_pred) * ref["mediana_eur"]),
            "rango_eur_min": self._redondeo_precio(np.exp(log_min) * ref["mediana_eur"]),
            "rango_eur_max": self._redondeo_precio(np.exp(log_max) * ref["mediana_eur"]),
        }
 
    # ------------------------------------------------------------------
    def explicar_precio(self, listing: dict) -> dict:
        ciudad = listing["city"]
        dmat = self._dmatrix(listing)
 
        # pred_contribs=True == predcontrib=TRUE de R: última columna = BIAS
        contrib = self.bst.predict(dmat, pred_contribs=True)[0]
        contrib_por_col = dict(zip(self.feature_names + ["BIAS"], contrib))
        # "(Intercept)" no es una variable real (igual que en R, sección 10.5)
        contrib_por_col.pop("(Intercept)", None)
 
        # Contribución por variable original (suma de sus columnas dummy)
        shap_nuevo = {v: 0.0 for v in self.vars_modelo}
        for col in self.cols_shap:
            var = self._col_a_variable[col]
            shap_nuevo[var] += contrib_por_col[col]
 
        log_pred = sum(contrib_por_col.values())
 
        ref_pred = self.base_ciudad.loc[ciudad]
        ref = self.referencias_ciudad.loc[ciudad]
        log_ref = ref_pred["pred_log"]
 
        detalle = []
        for v in self.vars_modelo:
            efecto_log = shap_nuevo[v] - ref_pred[f"shap__{v}"]
            detalle.append({
                "variable": v,
                "valor": listing[v],
                "efecto_log": efecto_log,
                "efecto_pct": (np.exp(efecto_log) - 1) * 100,
            })
        detalle = pd.DataFrame(detalle).sort_values(
            "efecto_log", key=lambda s: s.abs(), ascending=False
        ).reset_index(drop=True)
 
        return {
            "ciudad": ciudad,
            "moneda": ref["moneda"],
            "precio_referencia_local": round(np.exp(log_ref) * ref["mediana_local"]),
            "precio_local": round(np.exp(log_pred) * ref["mediana_local"]),
            "log_pred": log_pred,
            "log_ref": log_ref,
            "detalle": detalle,
        }
 