"""Sentinel-2 SR cloud-light median composite over Thailand, rendered as an
interactive HTML map (geemap/Leaflet) on a Google Satellite basemap.

One-time setup before running (needs your own Google login):
    earthengine authenticate
    earthengine set_project ee-yatikarn

Then:
    python Sentinel2.py
"""
import datetime

import ee
import geemap

PROJECT_ID = 'ee-yatikarn'
START_DATE = '2026-01-01'
END_DATE = datetime.date.today().isoformat()
MAX_CLOUD_PERCENT = 10

GOOGLE_SATELLITE_URL = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'


def mask_s2_clouds(image):
    qa = image.select('QA60')
    cloud_bit = 1 << 10
    cirrus_bit = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
    return image.updateMask(mask).divide(10000).copyProperties(image, ['system:time_start'])


def main():
    ee.Initialize(project=PROJECT_ID)

    thailand = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(
        ee.Filter.eq('ADM0_NAME', 'Thailand')
    )
    geom = thailand.geometry()

    s2 = (
        ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterDate(START_DATE, END_DATE)
        .filterBounds(geom)
        .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD_PERCENT))
    )
    print('Scenes matched:', s2.size().getInfo())

    composite = s2.map(mask_s2_clouds).median().clip(geom)
    vis_params = {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 0.3}

    m = geemap.Map()
    # base=True keeps this in the base tile pane (radio choice), so overlay
    # layers added below (Sentinel-2, boundary) always render above it,
    # regardless of which layer checkbox the user toggles on last.
    m.add_tile_layer(GOOGLE_SATELLITE_URL, name='Google Satellite', attribution='Google', base=True)
    m.centerObject(geom, 6)
    m.addLayer(
        composite, vis_params,
        f'Sentinel-2 median ({START_DATE} to {END_DATE}, cloud<={MAX_CLOUD_PERCENT}%)',
    )
    m.addLayer(thailand.style(color='ffff00', fillColor='00000000', width=2), {}, 'Thailand boundary')
    m.to_html('Sentinel2.html')
    print('Wrote Sentinel2.html')


if __name__ == '__main__':
    main()
