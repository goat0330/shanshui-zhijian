"""Download auditable Sentinel-1/Sentinel-2 evidence and ancillary rasters.

No proxy, Earth Engine project or output CRS is hard-coded. Direct downloads
must result in a local file; asynchronous Drive exports are reported as pending
and are never falsely marked as downloaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def initialise_ee(project: str | None):
    import ee

    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
    except Exception as exc:
        raise RuntimeError(
            "Earth Engine is not initialised. Run `earthengine authenticate` and "
            "pass --project when your account requires a Cloud project."
        ) from exc
    return ee


def load_aoi(ee, path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    geometry = payload["features"][0]["geometry"] if payload.get("type") == "FeatureCollection" else payload.get("geometry", payload)
    return ee.Geometry(geometry)


def build_s2_composite(ee, start: str, end: str, aoi, cloud_threshold: float):
    source = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
    )
    cloud_score = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    linked = source.linkCollection(cloud_score, ["cs_cdf"])

    def mask(image):
        return image.updateMask(image.select("cs_cdf").gte(cloud_threshold))

    bands = ["B2", "B3", "B4", "B8", "B11", "B12"]
    aliases = ["blue", "green", "red", "nir", "swir1", "swir2"]
    return linked.map(mask).median().select(bands, aliases).clip(aoi)


def build_s1_composite(ee, start: str, end: str, aoi):
    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .select(["VV", "VH"])
    )
    return collection.median().clip(aoi)


def download_local(image, output_path: Path, region, scale: float, crs: str) -> dict:
    import requests

    params = {
        "region": region,
        "scale": scale,
        "crs": crs,
        "format": "GEO_TIFF",
        "filePerBand": False,
    }
    url = image.getDownloadURL(params)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".part")
    response = requests.get(url, timeout=600, stream=True)
    response.raise_for_status()
    with temporary.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
    if temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Earth Engine returned an empty file for {output_path.name}")
    temporary.replace(output_path)
    return {
        "path": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "sha256": _sha256(output_path),
        "status": "downloaded",
    }


def start_drive_export(ee, image, name: str, region, scale: float, crs: str, folder: str) -> dict:
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=name,
        folder=folder,
        fileNamePrefix=name,
        scale=scale,
        crs=crs,
        region=region,
        maxPixels=1e10,
    )
    task.start()
    status = task.status()
    return {
        "status": "drive_export_pending",
        "task_id": status.get("id") or getattr(task, "id", None),
        "state": status.get("state"),
        "note": "The file is not local yet; download it from Drive before training.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Cycle 4 real water data")
    parser.add_argument("--aoi", type=Path, default=ROOT / "data/chongqing_demo/aoi.geojson")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/chongqing_demo/raw")
    parser.add_argument("--project", default=os.environ.get("EE_PROJECT"))
    parser.add_argument("--proxy", default=None, help="Optional HTTPS proxy; never applied unless explicitly supplied")
    parser.add_argument("--output-crs", default="EPSG:4545")
    parser.add_argument("--t1-start", default="2026-05-01")
    parser.add_argument("--t1-end", default="2026-06-01")
    parser.add_argument("--t2-start", default="2026-06-01")
    parser.add_argument("--t2-end", default="2026-07-01")
    parser.add_argument("--cloud-threshold", type=float, default=0.60)
    parser.add_argument("--include-s1", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--drive-export-on-large", action="store_true")
    parser.add_argument("--drive-folder", default="shanshui_cycle4")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.aoi.is_file():
        parser.error(f"AOI not found: {args.aoi}")
    if not 0 <= args.cloud_threshold <= 1:
        parser.error("--cloud-threshold must be in [0, 1]")
    if args.proxy:
        os.environ["HTTPS_PROXY"] = args.proxy
        os.environ["https_proxy"] = args.proxy

    ee = initialise_ee(args.project)
    aoi = load_aoi(ee, args.aoi)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    assets: list[tuple[str, object, int, str, dict]] = []
    for label, start, end in (
        ("t1", args.t1_start, args.t1_end),
        ("t2", args.t2_start, args.t2_end),
    ):
        assets.append((
            f"s2_{label}",
            build_s2_composite(ee, start, end, aoi, args.cloud_threshold),
            10,
            "COPERNICUS/S2_SR_HARMONIZED",
            {"start": start, "end_exclusive": end, "cloud_score_band": "cs_cdf"},
        ))
        if args.include_s1:
            assets.append((
                f"s1_{label}",
                build_s1_composite(ee, start, end, aoi),
                10,
                "COPERNICUS/S1_GRD",
                {"start": start, "end_exclusive": end, "bands": ["VV", "VH"]},
            ))

    ancillary = [
        (
            "jrc_water_occurrence",
            ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").clip(aoi),
            30,
            "JRC/GSW1_4/GlobalSurfaceWater",
            {"role": "stable-water prior / weak label, not date-specific truth"},
        ),
        (
            "worldcover_2021",
            ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").clip(aoi),
            10,
            "ESA/WorldCover/v200",
            {"role": "context prior"},
        ),
        (
            "dem_glo30",
            ee.ImageCollection("COPERNICUS/DEM/GLO30").mosaic().select("DEM").clip(aoi),
            30,
            "COPERNICUS/DEM/GLO30",
            {"role": "terrain prior"},
        ),
    ]
    assets.extend(ancillary)

    manifest = {
        "schema_version": "dataset-manifest.v0.1",
        "created_at": _timestamp(),
        "aoi_path": str(args.aoi),
        "earth_engine_project": args.project or "default-account-project",
        "output_crs": args.output_crs,
        "cloud_score_plus": {
            "collection": "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED",
            "join_method": "ImageCollection.linkCollection(system:index)",
            "band": "cs_cdf",
            "threshold": args.cloud_threshold,
        },
        "assets": [],
    }

    for name, image, scale, source, provenance in assets:
        output_path = args.output_dir / f"{name}.tif"
        record = {
            "asset_id": name,
            "source_collection": source,
            "scale_m": scale,
            "crs": args.output_crs,
            "provenance": provenance,
        }
        if output_path.exists() and not args.force:
            record.update({
                "path": str(output_path),
                "size_bytes": output_path.stat().st_size,
                "sha256": _sha256(output_path),
                "status": "existing_verified",
            })
        else:
            try:
                record.update(download_local(image, output_path, aoi, scale, args.output_crs))
            except Exception as exc:
                if not args.drive_export_on_large:
                    record.update({"status": "failed", "error": str(exc)})
                    manifest["assets"].append(record)
                    manifest_path = args.output_dir / "dataset_manifest.json"
                    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
                    raise RuntimeError(
                        f"Direct local download failed for {name}. No local file was claimed. "
                        "Use --drive-export-on-large only when you will manually retrieve the Drive output."
                    ) from exc
                record.update(start_drive_export(
                    ee,
                    image,
                    name,
                    aoi,
                    scale,
                    args.output_crs,
                    args.drive_folder,
                ))
        manifest["assets"].append(record)
        print(f"{name}: {record['status']}")

    manifest_path = args.output_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    local_failures = [item for item in manifest["assets"] if item["status"] not in {"downloaded", "existing_verified"}]
    print(f"Dataset manifest: {manifest_path}")
    if local_failures:
        print("Some exports are not local and must not be used for training yet:")
        for item in local_failures:
            print(f"  - {item['asset_id']}: {item['status']}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
