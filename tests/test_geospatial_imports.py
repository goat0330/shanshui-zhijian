"""Minimal geospatial dependency import checks used by Preflight CI."""


def test_pyproj_import_and_crs():
    import pyproj

    crs = pyproj.CRS.from_epsg(4545)
    assert crs is not None


def test_rasterio_import_and_crs():
    import rasterio

    crs = rasterio.crs.CRS.from_epsg(4545)
    assert crs is not None
