"""
Construye los campos de entrada del formulario a partir de
datos/metadatos_variables.json — un componente Gradio por variable del
modelo, con el tipo de control adecuado según su tipo ("categorica",
"logica", "numerica").
 
Dos grupos de variables NO llevan campo de formulario propio:
- `longitude`/`latitude`: las rellena el clic en el mapa (src/mapa.py).
- `total_reviews`/`reviews_por_mes_activo`: no se piden tal cual. Se
  preguntan dos datos sencillos en una sección opcional ("nº de reseñas" y
  "meses desde la primera reseña") y se calculan a partir de ellos, con la
  misma definición que en TFM_Clustering.qmd. Si se dejan a 0, el listing se
  trata como nuevo (sin reseñas).
"""
 
import json
from pathlib import Path
 
import gradio as gr
 
DATOS = Path(__file__).parent.parent / "datos"
 
CAMPOS_EXCLUIDOS_DEL_FORM = {"longitude", "latitude"}
 
# Ciudades que no se ofrecen en el formulario aunque el modelo se entrenó con
# ellas. Istanbul: la posición relativa (output principal) es inmune al sesgo
# del tipo de cambio fijo (sección 2.4), pero la cifra en euros no lo es
# (sección 1.6) — con la lira tan devaluada, esa cifra puede ser directamente
# engañosa para un anfitrión real. Se documenta en la memoria, no solo aquí.
CIUDADES_EXCLUIDAS = {"Istanbul"}
 
# Campos opcionales de reseñas (no son variables del modelo: a partir de
# ellos se calculan total_reviews y reviews_por_mes_activo en leer_listing)
CAMPO_N_RESENAS = "_n_resenas"
CAMPO_MESES_RESENAS = "_meses_resenas"
CAMPOS_RESENAS = [CAMPO_N_RESENAS, CAMPO_MESES_RESENAS]
 
# Overrides del rango bruto del dataset, cuando ese rango no tiene sentido
# para describir un listing nuevo. `minimum_nights` llega a 9999 en el
# dataset, pero es un único caso aislado (fijado a propósito por un
# anfitrión, ya visto en el clustering) — se acota a un rango realista.
RANGOS_MANUALES = {
    "minimum_nights": {"min": 1, "max": 90},
}
 
PASOS_MANUALES = {}
 
ETIQUETAS = {
    "city": "Ciudad",
    "room_type": "Tipo de alojamiento",
    "bedrooms": "Habitaciones",
    "accommodates": "Capacidad (nº de huéspedes)",
    "n_amenities": "Comodidades y servicios (nº aproximado)",
    "has_ac": "Aire acondicionado",
    "has_dishwasher": "Lavavajillas",
    "minimum_nights": "Estancia mínima (noches)",
    "host_total_listings_count": "Nº de alojamientos del anfitrión",
    "has_response_rate": "El anfitrión tiene tasa de respuesta registrada",
    "has_acceptance_rate": "El anfitrión tiene tasa de aceptación registrada",
}
 
# Texto de ayuda (aparece bajo la etiqueta en Gradio); solo donde aporta algo
ETIQUETAS[CAMPO_N_RESENAS] = "Nº de reseñas recibidas"
ETIQUETAS[CAMPO_MESES_RESENAS] = "Meses entre la primera y la última reseña"

INFO = {
    "n_amenities": (
        "Cuenta wifi, cocina, parking, calefacción, TV, lavadora... todo lo "
        "que marcarías al publicar el anuncio."
    ),
    "has_response_rate": (
        "El anfitrión ya ha respondido antes a mensajes en la plataforma "
        "(no es la calidad de esa respuesta, solo si hay historial)."
    ),
    "has_acceptance_rate": (
        "El anfitrión ya tiene un histórico de aceptación de reservas."
    ),
    CAMPO_N_RESENAS: (
        "Déjalo en 0 si el anuncio es nuevo."
    ),
    CAMPO_MESES_RESENAS: (
        "Solo si hay al menos 2 reseñas. 0 si todas son del mismo mes."
    ),
}
 
# Agrupación visual del formulario: (título de sección, [variables])
GRUPOS_CAMPOS = [
    ("📍 Datos básicos", ["city", "room_type", "bedrooms", "accommodates"]),
    ("🛋️ Comodidades y condiciones", ["n_amenities", "has_ac", "has_dishwasher", "minimum_nights"]),
    ("👤 Anfitrión", ["host_total_listings_count", "has_response_rate", "has_acceptance_rate"]),
]
 
ORDEN_VARIABLES = [v for _, variables in GRUPOS_CAMPOS for v in variables]
ORDEN_CAMPOS = ORDEN_VARIABLES + CAMPOS_RESENAS

TITULO_SECCION_RESENAS = "📈 Si tu anuncio ya está publicado (opcional)"
 
 
def cargar_metadatos(datos_dir: Path = DATOS) -> dict:
    with open(datos_dir / "metadatos_variables.json", encoding="utf-8") as f:
        items = json.load(f)
    return {m["variable"]: m for m in items}
 
 
def construir_campo(var: str, meta: dict) -> gr.components.Component:
    """Crea el componente Gradio para UNA variable (se llama ya dentro de un
    `with gr.Blocks()`/`gr.Column()`, así que renderiza en su posición actual)."""
    tipo = meta["tipo"]
    etiqueta = ETIQUETAS.get(var, var)
    info = INFO.get(var)
 
    if tipo == "categorica":
        niveles = meta["niveles"]
        if var == "city":
            niveles = [n for n in niveles if n not in CIUDADES_EXCLUIDAS]
        return gr.Dropdown(choices=niveles, value=niveles[0], label=etiqueta, info=info)
    elif tipo == "logica":
        return gr.Checkbox(value=False, label=etiqueta, info=info)
    elif tipo == "numerica":
        rango = RANGOS_MANUALES.get(var, {"min": meta["min"], "max": meta["max"]})
        return gr.Number(
            value=meta["mediana"], minimum=rango["min"], maximum=rango["max"],
            step=PASOS_MANUALES.get(var, 1), label=etiqueta, info=info,
        )
    else:
        raise ValueError(f"Tipo de variable no reconocido: {tipo!r} (variable {var})")
 
 
def construir_campos_agrupados(metadatos: dict | None = None) -> dict:
    """Pinta el formulario por secciones (con cabecera) y devuelve
    {variable: componente}, en el orden de ORDEN_CAMPOS."""
    if metadatos is None:
        metadatos = cargar_metadatos()
 
    faltan = set(ORDEN_VARIABLES) - set(metadatos)
    if faltan:
        raise ValueError(f"GRUPOS_CAMPOS incluye variables sin metadatos: {faltan}")
 
    campos = {}
    for titulo, variables in GRUPOS_CAMPOS:
        gr.Markdown(f"#### {titulo}", elem_classes="tfm-seccion")
        for var in variables:
            campos[var] = construir_campo(var, metadatos[var])

    gr.Markdown(f"#### {TITULO_SECCION_RESENAS}", elem_classes="tfm-seccion")
    campos[CAMPO_N_RESENAS] = gr.Number(
        value=0, minimum=0, maximum=2000, step=1,
        label=ETIQUETAS[CAMPO_N_RESENAS], info=INFO[CAMPO_N_RESENAS],
    )
    campos[CAMPO_MESES_RESENAS] = gr.Number(
        value=0, minimum=0, maximum=200, step=1, interactive=False,
        label=ETIQUETAS[CAMPO_MESES_RESENAS], info=INFO[CAMPO_MESES_RESENAS],
    )
    # Con 0 o 1 reseñas no hay intervalo entre la primera y la última:
    # el campo de meses se desactiva y se pone a 0
    campos[CAMPO_N_RESENAS].change(
        fn=_actualizar_campo_meses,
        inputs=[campos[CAMPO_N_RESENAS], campos[CAMPO_MESES_RESENAS]],
        outputs=campos[CAMPO_MESES_RESENAS],
    )
    return campos


def _actualizar_campo_meses(n_resenas, meses):
    activo = (n_resenas or 0) >= 2
    return gr.Number(interactive=activo, value=meses if activo else 0)
 
 
def leer_listing(valores: dict, lat: float, lon: float) -> dict:
    """
    valores: {variable: valor} de los componentes del formulario.
    lat/lon: los marcados en el mapa.
    Devuelve el dict `listing` completo (15 variables) para ModeloPrecio.
    """
    listing = dict(valores)
    listing["latitude"] = lat
    listing["longitude"] = lon

    # Reseñas: misma definición que en TFM_Clustering.qmd
    #   meses_activo = meses entre la primera y la última reseña + 1
    #   reviews_por_mes_activo = total_reviews / meses_activo
    n_resenas = int(listing.pop(CAMPO_N_RESENAS, 0) or 0)
    meses = int(listing.pop(CAMPO_MESES_RESENAS, 0) or 0)
    listing["total_reviews"] = n_resenas
    if n_resenas == 0:
        listing["reviews_por_mes_activo"] = 0
    elif n_resenas == 1:
        # Una sola reseña: primera = última, meses_activo = 1
        listing["reviews_por_mes_activo"] = 1.0
    else:
        listing["reviews_por_mes_activo"] = n_resenas / (meses + 1)
    return listing