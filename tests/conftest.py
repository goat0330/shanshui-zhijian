import logging
import os
import sys

logger = logging.getLogger(__name__)


def pytest_sessionstart(session):
    """Isolate geospatial environment from PostgreSQL pollution at session start."""
    postgres_vars = []
    dangerous = ["PROJ_LIB", "GDAL_DATA", "PROJ_DATA"]

    for var in dangerous:
        val = os.environ.pop(var, None)
        if val and any(
            marker in val.lower()
            for marker in ["postgres", "postgis"]
        ):
            postgres_vars.append(f"{var}={val}")

    if postgres_vars:
        logger.warning(
            "PostgreSQL-polluted environment variables removed:\n  %s",
            "\n  ".join(postgres_vars),
        )

    # Verify pyproj works after isolation
    try:
        import pyproj

        crs = pyproj.CRS.from_epsg(4545)
        _ = crs.to_wkt()
    except Exception as exc:
        logger.warning("pyproj CRS verification failed: %s", exc)

    # Verify rasterio works after isolation
    try:
        import rasterio

        crs = rasterio.crs.CRS.from_epsg(4545)
        _ = crs.to_wkt()
    except Exception as exc:
        logger.warning("rasterio CRS verification failed: %s", exc)
