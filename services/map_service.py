from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Mapping

import folium
from folium.plugins import MarkerCluster

from services.gps_parser import AUSTRIA_LAT, AUSTRIA_LON


logger = logging.getLogger(__name__)


# Folium's named-colour palette is small (see folium.Icon docs); stick to it
# so the marker icons render reliably across providers.
CATEGORY_COLORS: dict[int, str] = {
    1: "green",   # tape + duct/wire (best)
    2: "orange",  # duct/wire only
    3: "red",     # tape only
    4: "gray",    # neither detected
}
DEFAULT_COLOR = "blue"
DEFAULT_ZOOM = 14
# Above this point count, switch to MarkerCluster so the browser stays responsive.
CLUSTER_THRESHOLD = 200


def _coerce_points(points: Mapping | Iterable[Mapping]) -> list[dict]:
    if isinstance(points, Mapping):
        return [dict(points)]
    return [dict(p) for p in points]


def _in_austria(lat: float, lon: float) -> bool:
    return (
        AUSTRIA_LAT[0] <= lat <= AUSTRIA_LAT[1]
        and AUSTRIA_LON[0] <= lon <= AUSTRIA_LON[1]
    )


def _format_tooltip(name: str, confidence) -> str:
    try:
        pct = f"{float(confidence) * 100:.2f}%"
    except (TypeError, ValueError):
        pct = "n/a"
    return f"{name} — confidence: {pct}"


def _category_color(category) -> str:
    if category is None:
        return DEFAULT_COLOR
    try:
        return CATEGORY_COLORS.get(int(category), DEFAULT_COLOR)
    except (TypeError, ValueError):
        return DEFAULT_COLOR


def build_map(
    points: Mapping | Iterable[Mapping],
    output_path: str | Path | None = None,
    zoom_start: int = DEFAULT_ZOOM,
    filter_outside_austria: bool = True,
) -> str:
    """Render an interactive Folium/Leaflet map for one or more recognition records.

    Accepts either a single dict or an iterable of dicts. Each record must
    have ``latitude`` and ``longitude``; ``category`` (int 1-4) and
    ``image_name`` are used for marker colour and popup respectively.

    Returns the HTML document as a string. If ``output_path`` is given, the
    same HTML is also written to disk.

    Raises:
        ValueError: when no points remain after coordinate validation.
    """
    valid: list[dict] = []
    for entry in _coerce_points(points):
        lat = entry.get("latitude")
        lon = entry.get("longitude")
        if lat is None or lon is None:
            continue
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            continue
        if filter_outside_austria and not _in_austria(lat, lon):
            continue
        entry["latitude"] = lat
        entry["longitude"] = lon
        valid.append(entry)

    if not valid:
        raise ValueError("No valid points to render after filtering.")

    center_lat = sum(p["latitude"] for p in valid) / len(valid)
    center_lon = sum(p["longitude"] for p in valid) / len(valid)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start)

    container = MarkerCluster().add_to(m) if len(valid) > CLUSTER_THRESHOLD else m

    for p in valid:
        name = p.get("image_name") or "no name"
        folium.Marker(
            location=[p["latitude"], p["longitude"]],
            popup=name,
            tooltip=_format_tooltip(name, p.get("confidence")),
            icon=folium.Icon(color=_category_color(p.get("category"))),
        ).add_to(container)

    html = m.get_root().render()

    if output_path is not None:
        path = Path(output_path)
        path.write_text(html, encoding="utf-8")
        logger.info("Saved map with %d points to %s", len(valid), path)

    return html
