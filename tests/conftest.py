import logging
import os
import sys

logger = logging.getLogger(__name__)


def _find_valid_proj_lib():
    """Find a PROJ database with layout version >= 5 (required by rasterio)."""
    candidates = [
        r"D:\py\Python3\Lib\site-packages\rasterio\proj_data",
        r"D:\py\Python3\Lib\site-packages\pyproj\proj_dir\share\proj",
    ]
    for path in candidates:
        db = os.path.join(path, "proj.db")
        if os.path.exists(db):
            try:
                import sqlite3
                c = sqlite3.connect(db)
                minor = c.execute(
                    "SELECT value FROM metadata WHERE key='DATABASE.LAYOUT.VERSION.MINOR'"
                ).fetchone()
                c.close()
                if minor and int(minor[0]) >= 5:
                    return path
            except Exception:
                continue
    return None


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

    valid_proj = _find_valid_proj_lib()
    if valid_proj:
        os.environ["PROJ_LIB"] = valid_proj
        logger.info("Using PROJ_LIB=%s", valid_proj)

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
