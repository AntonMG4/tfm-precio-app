"""
Mapa interactivo (Leaflet) para marcar la ubicación exacta del listing con
un clic, en vez de pedir latitude/longitude como números sueltos.

DISEÑO (importante, evita un problema real de los navegadores): un
gr.HTML() cuyo VALOR se actualiza dinámicamente inyecta el string como
innerHTML — y los navegadores, por especificación, no ejecutan <script>
insertados así. Por eso toda la lógica del mapa vive en el `head=` de
gr.Blocks() (que sí es contenido real de la página, se ejecuta como en
cualquier web), y el <div> del mapa es estático: no vuelve a tocarse.

Flujo:
1. `construir_head(centros)` — Leaflet + los centros de las 10 ciudades
   (como objeto JS) + la función global `inicializarMapa(divId, lat, lon)`.
   Se pasa una sola vez a gr.Blocks(head=...).
2. `DIV_MAPA_HTML` — el <div> estático, se pinta una vez con gr.HTML().
3. Cambiar de ciudad (o cargar la app) dispara `JS_RECENTRAR` vía el
   parámetro `js=` de un evento (fn=None): lee `window.CENTROS_CIUDAD` y
   llama a `inicializarMapa` — sin volver a inyectar HTML/scripts.
4. Al hacer clic en el mapa, el JS guarda las coordenadas en
   `window.__coords_mapa` y "pulsa" un botón oculto; ese botón tiene su
   propio evento con `js=JS_LEER_COORDS` que las escribe en un Textbox
   oculto, como "lat,lon" (Textbox y no Number: un input numérico nativo
   no se puede esconder del todo con visible=False — sus flechas de
   incremento/decremento no encogen a 0 y acaban desbordando).
"""

import json
from pathlib import Path

import pandas as pd

DATOS = Path(__file__).parent.parent / "datos"

ID_DIV_MAPA = "mapa-listing"
ELEM_ID_BOTON_MAPA = "btn_leer_mapa_oculto"
ZOOM_INICIAL = 12

DIV_MAPA_HTML = f'<div id="{ID_DIV_MAPA}" style="height:400px;border-radius:8px;"></div>'

JS_LEER_COORDS = "() => (window.__coords_mapa || [null, null]).join(',')"

JS_RECENTRAR = f"""
(ciudad) => {{
  const c = window.CENTROS_CIUDAD[ciudad];
  if (c) {{ window.inicializarMapa("{ID_DIV_MAPA}", c.lat, c.lon, {ZOOM_INICIAL}); }}
  return [];
}}
"""


def cargar_centros(datos_dir: Path = DATOS) -> pd.DataFrame:
    return pd.read_csv(datos_dir / "centros_ciudad.csv").set_index("city")


def construir_head(centros: pd.DataFrame) -> str:
    centros_js = json.dumps({
        ciudad: {"lat": float(fila["centro_lat"]), "lon": float(fila["centro_lon"])}
        for ciudad, fila in centros.iterrows()
    })

    return f"""
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
window.CENTROS_CIUDAD = {centros_js};
window.__mapaInstancia = null;
window.__coords_mapa = null;

window.inicializarMapa = function(divId, lat, lon, zoom) {{
  if (window.__mapaInstancia) {{
    window.__mapaInstancia.remove();
    window.__mapaInstancia = null;
  }}
  const contenedor = document.getElementById(divId);
  if (!contenedor) return;

  const mapa = L.map(divId).setView([lat, lon], zoom);
  window.__coords_mapa = [lat, lon];  // valor por defecto: el centro, hasta que se haga clic
  L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
  }}).addTo(mapa);

  let marcador = null;
  mapa.on("click", function(e) {{
    window.__coords_mapa = [e.latlng.lat, e.latlng.lng];
    if (marcador) {{ mapa.removeLayer(marcador); }}
    marcador = L.marker(e.latlng).addTo(mapa);

    const boton = document.getElementById("{ELEM_ID_BOTON_MAPA}");
    if (boton) {{ boton.click(); }}
  }});

  window.__mapaInstancia = mapa;
}};
</script>
"""