"""
App de recomendación de precio (TFM Airbnb, fase 10 llevada a producto).
Punto de entrada para HuggingFace Spaces / ejecución local: `python app.py`.
"""

import numpy as np
import gradio as gr
import plotly.graph_objects as go

from src.modelo import ModeloPrecio
from src import formulario, mapa

# El tier gratuito de HuggingFace Spaces (ZeroGPU) exige que exista alguna
# función decorada con @spaces.GPU al arrancar, o rechaza el Space entero —
# aunque la app no necesite GPU en absoluto (XGBoost corre en CPU). Esta
# función no se usa nunca, solo existe para pasar esa comprobación de arranque.
# En local no está instalado el paquete `spaces` (es específico de Spaces),
# así que el import se protege con try/except.
try:
    import spaces

    @spaces.GPU(duration=1)
    def _zerogpu_dummy():
        return None
except ImportError:
    pass

# --- Carga de todo lo necesario (una sola vez al arrancar la app) ---
modelo = ModeloPrecio()
metadatos = formulario.cargar_metadatos()
centros = mapa.cargar_centros()
NOMBRES_CAMPOS = list(formulario.ORDEN_CAMPOS)
CIUDAD_INICIAL = [n for n in metadatos["city"]["niveles"] if n not in formulario.CIUDADES_EXCLUIDAS][0]

FONDO = "#1e1e1e"
FONDO_TARJETA = "#242424"
BORDE = "#3a3a3a"

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

.gradio-container {{ font-family: 'Inter', sans-serif !important; }}

.tfm-titulo-h1 {{
  font-family: 'Poppins', sans-serif !important;
  font-size: 2.4em;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0.2em 0 0.12em 0;
  padding: 0;
  color: #FF9142;
}}
.tfm-subtitulo {{
  font-family: 'Inter', sans-serif;
  font-size: 1.05em;
  line-height: 1.55;
  color: #999;
  margin-top: 0;
  margin-bottom: 0.6em;
}}
.tfm-seccion h4 {{
  font-family: 'Poppins', sans-serif !important;
  font-size: 1.12em;
  font-weight: 700;
  color: #FF9142;
  letter-spacing: 0.01em;
  border-bottom: 2px solid #3a3a3a;
  padding-bottom: 7px;
  margin-top: 20px !important;
  margin-bottom: 10px !important;
}}
#col-formulario {{ gap: 4px; }}
#col-formulario .block {{ margin-bottom: 2px; }}

#coords_oculto, #{mapa.ELEM_ID_BOTON_MAPA} {{
  display: none !important;
}}
"""


def construir_grafico_explicacion(explicacion: dict, top: int = 6) -> go.Figure:
    """Equivalente interactivo (Plotly) de grafico_explicacion() (10.5)."""
    detalle = explicacion["detalle"]
    principales = detalle.iloc[:top]
    resto = detalle.iloc[top:]

    etiquetas = [f"{f.variable} = {f.valor}" for f in principales.itertuples()]
    efectos = list(principales["efecto_pct"])

    if len(resto) > 0:
        efecto_log_resto = resto["efecto_log"].sum()
        etiquetas.append("resto de variables")
        efectos.append((np.exp(efecto_log_resto) - 1) * 100)

    orden = sorted(range(len(efectos)), key=lambda i: abs(efectos[i]))
    etiquetas = [etiquetas[i] for i in orden]
    efectos = [efectos[i] for i in orden]
    colores = ["#5B9BD5" if e > 0 else "#E06666" for e in efectos]

    fig = go.Figure(go.Bar(
        x=efectos, y=etiquetas, orientation="h",
        marker_color=colores,
        text=[f"{e:+.0f}%" for e in efectos],
        textposition="outside",
        hovertemplate="%{y}: %{x:+.1f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="rgba(200,200,200,0.35)", line_width=1)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=FONDO,
        plot_bgcolor=FONDO,
        font=dict(color="#e8e8e8", size=13, family="Inter, sans-serif"),
        title=dict(
            font=dict(family="Poppins, sans-serif", size=18, color="#fafafa"),
            text=(
                f"<b>Por qué ese precio en {explicacion['ciudad']}</b><br>"
                f"<span style='font-size:0.85em; color:#aaa;'>Alojamiento medio: "
                f"{explicacion['precio_referencia_local']} {explicacion['moneda']} "
                f"&rarr; recomendado: {explicacion['precio_local']} "
                f"{explicacion['moneda']}</span>"
            ),
        ),
        xaxis=dict(title="Efecto sobre el precio (%)", gridcolor="#3a3a3a", zeroline=False),
        yaxis=dict(gridcolor="#3a3a3a"),
        margin=dict(l=10, r=40, t=80, b=10),
        height=120 + 40 * len(etiquetas),
        showlegend=False,
    )
    return fig


def formatear_resumen(rec: dict) -> str:
    positivo = rec["pos_relativa_pct"] >= 0
    color = "#43A047" if positivo else "#E53935"
    signo = "+" if positivo else ""
    return f"""
<div style="border:1px solid {BORDE}; border-radius:14px; padding:24px 28px;
            background:{FONDO_TARJETA}; box-shadow:0 4px 18px rgba(0,0,0,0.25);">
  <div style="font-family:'Inter',sans-serif; font-size:1.05em; color:#999; letter-spacing:0.02em; text-transform:uppercase;">
    {rec['ciudad']}
  </div>
  <div style="display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; margin-top:8px;">
    <span style="font-family:'Poppins',sans-serif; font-size:2.5em; font-weight:800; color:#fafafa; line-height:1;">
      {rec['precio_local']:.0f} {rec['moneda']}
    </span>
    <span style="font-family:'Inter',sans-serif; background:{color}; color:white; padding:6px 14px; border-radius:999px;
                 font-weight:700; font-size:0.9em;">
      {signo}{rec['pos_relativa_pct']:.0f}% vs. mediana
    </span>
  </div>
  <div style="font-family:'Inter',sans-serif; color:#aaa; font-size:0.92em; margin-top:14px; line-height:1.7;
              border-top:1px solid {BORDE}; padding-top:12px;">
    Rango habitual: <b style="color:#ddd;">{rec['rango_local_min']:.0f} – {rec['rango_local_max']:.0f} {rec['moneda']}</b><br/>
    &asymp; {rec['precio_eur']:.0f} &euro; (rango {rec['rango_eur_min']:.0f}–{rec['rango_eur_max']:.0f} &euro;)
  </div>
</div>
"""


def _parsear_coords(coords_str: str):
    """'lat,lon' (string del Textbox oculto) -> (lat, lon) como float, o (None, None)."""
    if not coords_str:
        return None, None
    try:
        lat_s, lon_s = coords_str.split(",")
        return float(lat_s), float(lon_s)
    except (ValueError, AttributeError):
        return None, None


def calcular(*valores):
    *valores_campos, coords_str = valores
    lat, lon = _parsear_coords(coords_str)
    if lat is None or lon is None:
        raise gr.Error("Marca la ubicación del alojamiento en el mapa antes de calcular.")

    valores_dict = dict(zip(NOMBRES_CAMPOS, valores_campos))
    listing = formulario.leer_listing(valores_dict, lat, lon)

    rec = modelo.recomendar_precio(listing)
    exp = modelo.explicar_precio(listing)

    return formatear_resumen(rec), construir_grafico_explicacion(exp)


def coords_ciudad(ciudad: str) -> str:
    fila = centros.loc[ciudad]
    return f"{fila['centro_lat']},{fila['centro_lon']}"


with gr.Blocks(title="Recomendador de precio — Airbnb") as demo:
    gr.HTML('<h1 class="tfm-titulo-h1">🏷️ Recomendador de precio</h1>')
    gr.Markdown(
        "Completa los datos del alojamiento, marca su ubicación en el mapa, y "
        "obtén una recomendación de precio con su rango de confianza y una "
        "explicación de qué características lo justifican.",
        elem_classes="tfm-subtitulo",
    )

    with gr.Row():
        with gr.Column(scale=1, elem_id="col-formulario"):
            campos = formulario.construir_campos_agrupados(metadatos)
            gr.Markdown("#### 🗺️ Ubicación", elem_classes="tfm-seccion")
            gr.HTML(mapa.DIV_MAPA_HTML)
            gr.Markdown("*Haz clic en el mapa para marcar la ubicación exacta del alojamiento.*")
            # Textbox y no Number: un input numérico nativo no se esconde
            # del todo con visible=False (sus flechas de incremento/
            # decremento no encogen a 0 y acaban desbordando el layout).
            coords_oculto = gr.Textbox(visible=False, elem_id="coords_oculto")
            boton_mapa_oculto = gr.Button(visible=False, elem_id=mapa.ELEM_ID_BOTON_MAPA)
            boton_calcular = gr.Button("💰 Calcular precio recomendado", variant="primary", size="lg")

        with gr.Column(scale=1):
            resumen = gr.HTML()
            grafico = gr.Plot()

    # --- Ciudad -> recentra el mapa (client-side, JS ya cargado en `head`)
    #     y actualiza el valor por defecto de las coordenadas (server-side, para el cálculo)
    campos["city"].change(fn=coords_ciudad, inputs=campos["city"], outputs=coords_oculto)
    campos["city"].change(fn=None, inputs=campos["city"], outputs=[], js=mapa.JS_RECENTRAR)

    # --- Clic en el mapa -> JS puro, sin pasar por el servidor (ver src/mapa.py)
    boton_mapa_oculto.click(fn=None, inputs=None, outputs=coords_oculto, js=mapa.JS_LEER_COORDS)

    boton_calcular.click(
        fn=None, inputs=None, outputs=coords_oculto,
        js=mapa.JS_LEER_COORDS,
    ).then(
        fn=calcular,
        inputs=[campos[v] for v in NOMBRES_CAMPOS] + [coords_oculto],
        outputs=[resumen, grafico],
    ).then(
        fn=None, inputs=None, outputs=[],
        js="() => { window.scrollTo({top: 0, behavior: 'smooth'}); return []; }",
    )

    # --- Estado inicial al cargar la app
    demo.load(fn=coords_ciudad, inputs=campos["city"], outputs=coords_oculto)
    demo.load(fn=None, inputs=campos["city"], outputs=[], js=mapa.JS_RECENTRAR)


if __name__ == "__main__":
    demo.launch(css=CSS, head=mapa.construir_head(centros))