import requests
import sqlite3
import folium
import pandas as pd
from datetime import datetime, timedelta
import webbrowser

# Función para obtener las subcategorías de una categoría principal
def obtener_subcategorias(category_id):
    url = f"https://api.mercadolibre.com/categories/{category_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['children_categories']
    else:
        print("Error al obtener subcategorías")
        return []

# Función para obtener los estados
def obtener_estados():
    url = "https://api.mercadolibre.com/classified_locations/countries/AR"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['states']
    else:
        print("Error al obtener estados")
        return []

# Función para obtener los distritos de un estado
def obtener_distritos(state_id):
    url = f"https://api.mercadolibre.com/classified_locations/states/{state_id}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['cities']
    else:
        print("Error al obtener distritos")
        return []

# Función para obtener los artículos de una categoría con paginación
def fetch_items(category_id, buying_mode, state_id=None, city_id=None, price_min=None, price_max=None):
    items = []
    offset = 0
    limit = 50
    while True:
        url = f"https://api.mercadolibre.com/sites/MLA/search?category={category_id}&buying_mode={buying_mode}&offset={offset}&limit={limit}"
        if state_id:
            url += f"&state={state_id}"
        if city_id:
            url += f"&city={city_id}"
        if price_min and price_max:
            url += f"&price={price_min}-{price_max}"
        
        print(f"Fetch items URL: {url}")
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            items.extend(data.get('results', []))
            if len(data.get('results', [])) < limit:
                break
            offset += limit
        else:
            print("Error al obtener artículos:", response.status_code)
            print(response.text)
            break
    return items

# Función para crear la tabla si no existe
def create_table():
    conn = sqlite3.connect('mercadolibre.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            site_id TEXT,
            title TEXT,
            price REAL,
            thumbnail TEXT,
            created_date TEXT,
            latitude REAL,
            longitude REAL,
            permalink TEXT
        )
    """)
    conn.commit()
    conn.close()

# Función para borrar los artículos en la base de datos
def clear_items():
    conn = sqlite3.connect('mercadolibre.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items")
    conn.commit()
    conn.close()
    print("Base de datos limpiada.")

# Función para almacenar los artículos en la base de datos
def store_items(items):
    conn = sqlite3.connect('mercadolibre.db')
    cursor = conn.cursor()
    for item in items:
        if 'location' in item and 'latitude' in item['location'] and 'longitude' in item['location']:
            cursor.execute("""
                INSERT OR REPLACE INTO items (id, site_id, title, price, thumbnail, created_date, latitude, longitude, permalink)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item['id'],
                item['site_id'],
                item['title'],
                item['price'],
                item['thumbnail'],
                item['stop_time'],
                item['location']['latitude'],
                item['location']['longitude'],
                item['permalink']
            ))
    conn.commit()
    conn.close()
    print(f"Almacenados {len(items)} artículos en la base de datos.")

# Función para crear el mapa
def create_map():
    conn = sqlite3.connect('mercadolibre.db')
    query = "SELECT title, latitude, longitude, price, permalink FROM items WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("No hay datos de ubicación para mostrar en el mapa.")
        return

    print(f"Datos obtenidos para el mapa: {len(df)} filas.")

    map_center = [df['latitude'].mean(), df['longitude'].mean()] if not df.empty else [-34.6083, -58.3712]
    m = folium.Map(location=map_center, zoom_start=12)

    for index, row in df.iterrows():
        street_view_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={row['latitude']},{row['longitude']}"
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=(f"<b>{row['title']}</b><br>Price: ${row['price']}<br><a href='{row['permalink']}' target='_blank'>Link</a>"
                   f"<br><a href='{street_view_url}' target='_blank'>Street View</a>"),
            tooltip=row['title']
        ).add_to(m)

    folium.TileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', 
                     attr='OpenStreetMap', name='OpenStreetMap').add_to(m)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                     attr='Google', name='Google Satélite').add_to(m)
    
    folium.LayerControl().add_to(m)
    m.save('mapa_inmuebles.html')
    webbrowser.open('mapa_inmuebles.html')

def main():
    create_table()  # Crear la tabla si no existe
    clear_items()  # Borrar los artículos existentes en la base de datos

    # Obtener categorías de propiedades
    category_id = "MLA1459"  # ID de la categoría principal de propiedades
    subcategorias = obtener_subcategorias(category_id)
    print("Subcategorías disponibles para propiedades:")
    for subcategoria in subcategorias:
        print(f"{subcategoria['name']} - ID: {subcategoria['id']}")

    # Seleccionar estado
    estados = obtener_estados()
    print("Seleccione un estado:")
    for i, estado in enumerate(estados, 1):
        print(f"{i}. {estado['name']}")
    estado_idx = int(input("Ingrese el número del estado deseado: ")) - 1
    state_id = estados[estado_idx]['id']

    # Seleccionar distrito
    distritos = obtener_distritos(state_id)
    print("Seleccione un distrito:")
    for i, distrito in enumerate(distritos, 1):
        print(f"{i}. {distrito['name']}")
    distrito_idx = int(input("Ingrese el número del distrito deseado: ")) - 1
    city_id = distritos[distrito_idx]['id']

    # Realizar una solicitud directa con los parámetros obtenidos
    print(f"Realizando solicitud directa con la categoría MLA1466, estado {state_id} y ciudad {city_id}")
    url = f"https://api.mercadolibre.com/sites/MLA/search?category=MLA1466&buying_mode=buying&state={state_id}&city={city_id}&offset=0&limit=50"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print(f"Total de resultados: {data['paging']['total']}")
        print("Ejemplos de resultados:")
        for result in data['results'][:5]:
            print(result)
    else:
        print("Error al realizar la solicitud:", response.status_code)
        print(response.text)

    # Seleccionar opción de compra/alquiler
    print("Seleccione una opción:")
    print("1. Comprar")
    print("2. Alquilar")
    buying_mode = "buying" if input("Ingrese el número de la opción deseada: ") == "1" else "rental"

    # Seleccionar tipo de propiedad
    print("Seleccione el tipo de propiedad:")
    print("1. Departamento")
    print("2. Casa")
    print("3. Local")
    property_type_map = {1: "MLA1472", 2: "MLA1466", 3: "MLA79242"}  # Categorías específicas de MercadoLibre
    category_id = property_type_map[int(input("Ingrese el número del tipo de propiedad deseado: "))]

    # Seleccionar rango de precios
    print("Desea establecer un rango de precios?")
    print("1. Sí")
    print("2. No")
    if input("Ingrese el número de la opción deseada: ") == "1":
        price_min = input("Ingrese el precio mínimo: ")
        price_max = input("Ingrese el precio máximo: ")
    else:
        price_min = price_max = None

    # Obtener artículos
    items = fetch_items(category_id, buying_mode, state_id=state_id, city_id=city_id, price_min=price_min, price_max=price_max)

    valid_items = [item for item in items if 'location' in item and 'latitude' in item['location'] and 'longitude' in item['location']]
    print(f"Valid items with location data: {len(valid_items)}")

    if valid_items:
        # Almacenar artículos en la base de datos
        store_items(valid_items)
        # Crear el mapa
        create_map()
        print("Mapa creado: 'mapa_inmuebles.html'")
    else:
        print("No hay artículos para almacenar.")

if __name__ == "__main__":
    main()
