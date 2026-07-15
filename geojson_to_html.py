"""Render a GeoJSON file as a standalone interactive HTML map (Leaflet + Google Maps basemap).

The GeoJSON data is embedded inline in the HTML so the file works when opened
directly in a browser (file://) without hitting fetch/CORS issues.

Usage:
    python geojson_to_html.py <input.geojson> <output.html> [--title TITLE]
"""
import argparse
import json
from pathlib import Path

TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    html, body {{ margin: 0; height: 100%; }}
    #map {{ width: 100%; height: 100vh; }}
    .leaflet-popup-content {{ font-family: 'Segoe UI', Tahoma, sans-serif; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const geodata = {geojson};

    const map = L.map('map');

    // Google Maps roadmap tiles (unofficial XYZ endpoint, no API key needed for light/local use).
    L.tileLayer('https://{{s}}.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}', {{
      maxZoom: 20,
      subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
      attribution: '&copy; Google Maps'
    }}).addTo(map);

    const layer = L.geoJSON(geodata, {{
      style: {{ color: '#e74c3c', weight: 2, fillColor: '#e74c3c', fillOpacity: 0.1 }},
      onEachFeature: (feature, lyr) => {{
        if (feature.properties && Object.keys(feature.properties).length) {{
          const rows = Object.entries(feature.properties)
            .map(([k, v]) => `<tr><th style="text-align:left;padding-right:8px">${{k}}</th><td>${{v}}</td></tr>`)
            .join('');
          lyr.bindPopup(`<table>${{rows}}</table>`);
        }}
      }}
    }}).addTo(map);

    map.fitBounds(layer.getBounds());
  </script>
</body>
</html>
"""


def build_html(geojson_path: Path, title: str) -> str:
    geojson = json.loads(geojson_path.read_text(encoding='utf-8'))
    return TEMPLATE.format(title=title, geojson=json.dumps(geojson, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description='Render a GeoJSON file as an interactive Leaflet HTML map.')
    parser.add_argument('input', help='Path to input .geojson file')
    parser.add_argument('output', help='Path to output .html file')
    parser.add_argument('--title', default=None, help='Page title (defaults to input filename)')
    args = parser.parse_args()

    geojson_path = Path(args.input)
    out_path = Path(args.output)
    title = args.title or geojson_path.stem

    html = build_html(geojson_path, title)
    out_path.write_text(html, encoding='utf-8')
    print(f'Wrote {out_path} ({out_path.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
