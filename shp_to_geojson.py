"""Convert a shapefile to GeoJSON, reprojecting to WGS84 (EPSG:4326) using its .prj file.

Usage:
    python shp_to_geojson.py <input.shp> <output.geojson>
"""
import argparse
import json
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer


def reproject_geometry(geom: dict, transformer: Transformer) -> dict:
    def tf_ring(coords):
        return [list(transformer.transform(x, y)) for x, y in coords]

    def tf_nested(coords, depth):
        if depth == 1:
            return tf_ring(coords)
        return [tf_nested(c, depth - 1) for c in coords]

    depth = {'Point': 0, 'MultiPoint': 1, 'LineString': 1,
              'MultiLineString': 2, 'Polygon': 2, 'MultiPolygon': 3}[geom['type']]
    if depth == 0:
        x, y = transformer.transform(*geom['coordinates'])
        coords = [x, y]
    else:
        coords = tf_nested(geom['coordinates'], depth)
    return {'type': geom['type'], 'coordinates': coords}


def convert(shp_path: Path, out_path: Path):
    prj_path = shp_path.with_suffix('.prj')
    source_crs = CRS.from_wkt(prj_path.read_text()) if prj_path.exists() else CRS.from_epsg(4326)
    transformer = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True)

    with shapefile.Reader(str(shp_path)) as sf:
        features = []
        for shape_rec in sf.iterShapeRecords():
            geom = shape_rec.shape.__geo_interface__
            geom = reproject_geometry(geom, transformer)
            features.append({
                'type': 'Feature',
                'geometry': geom,
                'properties': shape_rec.record.as_dict(),
            })

    geojson = {'type': 'FeatureCollection', 'features': features}
    out_path.write_text(json.dumps(geojson, ensure_ascii=False), encoding='utf-8')
    return len(features), source_crs.name


def main():
    parser = argparse.ArgumentParser(description='Convert a shapefile to WGS84 GeoJSON.')
    parser.add_argument('input', help='Path to input .shp file')
    parser.add_argument('output', help='Path to output .geojson file')
    args = parser.parse_args()

    shp_path = Path(args.input)
    out_path = Path(args.output)
    n, crs_name = convert(shp_path, out_path)
    print(f'Converted {n} feature(s) from {crs_name} -> WGS84')
    print(f'Wrote {out_path} ({out_path.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
