"""Ejecutar desde la raíz del repo: python probar_paridad.py"""
import json
from src.modelo import ModeloPrecio
 
listing = json.loads("""
{
  "city": "New York",
  "room_type": "Private room",
  "bedrooms": 1,
  "accommodates": 2,
  "host_total_listings_count": 1,
  "longitude": -73.9489,
  "latitude": 40.7104,
  "has_ac": false,
  "minimum_nights": 30,
  "has_response_rate": false,
  "n_amenities": 10,
  "has_acceptance_rate": false,
  "reviews_por_mes_activo": 0,
  "has_dishwasher": false,
  "total_reviews": 0
}
""")
 
m = ModeloPrecio()
 
print("--- recomendar_precio() en Python ---")
for k, v in m.recomendar_precio(listing).items():
    print(f"  {k}: {v}")
 
print("\n--- explicar_precio() en Python (detalle) ---")
print(m.explicar_precio(listing)["detalle"].to_string(index=False))
 
