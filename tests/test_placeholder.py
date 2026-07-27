def test_imports():
    import pyproj

    crs = pyproj.CRS.from_epsg(4545)
    assert crs is not None


def test_rasterio_imports():
    import rasterio

    crs = rasterio.crs.CRS.from_epsg(4545)
    assert crs is not None
