"""Ay güney kutbu kalıcı gölgeli bölge (PSR) güvenli rota planlayıcı (Extra 4).

Kutup stereografik ızgara üzerinde A* (heapq) algoritması kullanarak aday iniş
noktalarından hedef PSR krater kenarına kadar eğim ve kalıcı gölge maliyetlerini
minimize eden güvenli yüzey geçiş koridoru üretir.
"""

from __future__ import annotations

import heapq
import math

import numpy as np

from luna_sight.terrain.polar import R_MOON_M, lonlat_to_xy, xy_to_lonlat
from luna_sight.terrain.sites import get_candidate_site
from luna_sight.terrain.surface_3d import IAU_CRATERS, R_MOON_KM, compute_lunar_elevation

DEFAULT_ROVER_SPEED_KMH: float = 1.5  # Basınçlı Ay roverı / EVA geçiş hızı (km/saat)

#: Başlıca Ay güney kutbu Kalıcı Gölgeli Bölge (PSR) hedefleri.
#: Tüm boylam değerleri doğu-pozitif kanonik [-180.0, 180.0] aralığındadır.
PSR_TARGETS: dict[str, dict[str, object]] = {
    "Shackleton PSR": {
        "name": "Shackleton PSR",
        "latitude_deg": -89.67,
        "longitude_deg_east": 129.78,
        "radius_km": 10.45,
    },
    "Shoemaker PSR": {
        "name": "Shoemaker PSR",
        "latitude_deg": -88.10,
        "longitude_deg_east": 44.90,
        "radius_km": 25.45,
    },
    "Faustini PSR": {
        "name": "Faustini PSR",
        "latitude_deg": -87.30,
        "longitude_deg_east": 77.00,
        "radius_km": 21.25,
    },
    "de Gerlache PSR": {
        "name": "de Gerlache PSR",
        "latitude_deg": -88.50,
        "longitude_deg_east": -87.10,
        "radius_km": 16.20,
    },
    "Haworth PSR": {
        "name": "Haworth PSR",
        "latitude_deg": -86.90,
        "longitude_deg_east": -4.00,
        "radius_km": 25.70,
    },
    "Cabeus PSR": {
        "name": "Cabeus PSR",
        "latitude_deg": -84.90,
        "longitude_deg_east": -35.50,
        "radius_km": 50.00,
    },
    "Amundsen PSR": {
        "name": "Amundsen PSR",
        "latitude_deg": -84.44,
        "longitude_deg_east": 83.07,
        "radius_km": 51.70,
    },
    "Slater PSR": {
        "name": "Slater PSR",
        "latitude_deg": -88.08,
        "longitude_deg_east": 111.29,
        "radius_km": 12.50,
    },
    "Nobile PSR": {
        "name": "Nobile PSR",
        "latitude_deg": -85.28,
        "longitude_deg_east": 53.27,
        "radius_km": 39.65,
    },
}


def _normalize_lon_180(lon_deg: np.ndarray) -> np.ndarray:
    return ((lon_deg + 180.0) % 360.0) - 180.0


def _resolve_psr_target(
    site_x_m: float,
    site_y_m: float,
    target_psr: str | None,
) -> dict[str, object]:
    if target_psr is not None:
        if target_psr in PSR_TARGETS:
            return PSR_TARGETS[target_psr]
        needle = target_psr.strip().lower()
        for key, item in PSR_TARGETS.items():
            if key.lower() == needle or key.lower().removesuffix(" psr") == needle:
                return item
        valid = ", ".join(PSR_TARGETS.keys())
        raise KeyError(f"Bilinmeyen PSR hedefi '{target_psr}'. Tanımlı hedefler: {valid}")

    best_target: dict[str, object] | None = None
    best_rim_dist = float("inf")
    for item in PSR_TARGETS.values():
        cx, cy = lonlat_to_xy(float(item["longitude_deg_east"]), float(item["latitude_deg"]))
        center_dist_m = math.hypot(site_x_m - cx, site_y_m - cy)
        rim_dist_m = abs(center_dist_m - float(item["radius_km"]) * 1000.0)
        if rim_dist_m < best_rim_dist:
            best_rim_dist = rim_dist_m
            best_target = item

    assert best_target is not None
    return best_target


def _compute_crater_floor_psr_mask(lat_grid: np.ndarray, lon_grid: np.ndarray) -> np.ndarray:
    """IAU krater katalogundaki kalıcı gölgeli tabanları (PSR çekirdeği) işaretler."""
    lat_r = np.radians(lat_grid)
    lon_r = np.radians(lon_grid)
    psr_floor = np.zeros(lat_grid.shape, dtype=bool)
    for crater in IAU_CRATERS:
        if float(crater.get("psr_fraction", 0.0)) <= 0.0:
            continue
        c_lat = math.radians(float(crater["lat_deg"]))
        c_lon = math.radians(float(crater["lon_deg"]))
        radius_km = float(crater["diameter_km"]) / 2.0
        cos_d = np.sin(lat_r) * math.sin(c_lat) + np.cos(lat_r) * math.cos(c_lat) * np.cos(
            lon_r - c_lon
        )
        d_km = np.arccos(np.clip(cos_d, -1.0, 1.0)) * R_MOON_KM
        psr_floor |= d_km < (0.55 * radius_km)
    return psr_floor


def _astar_grid(
    slope_deg: np.ndarray,
    psr_floor: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    cell_m: float,
    max_slope_deg: float,
    strict_barrier: bool,
) -> list[tuple[int, int]] | None:
    rows, cols = slope_deg.shape
    sr, sc = start
    gr, gc = goal

    def heuristic(r: int, c: int) -> float:
        return math.hypot((r - gr) * cell_m, (c - gc) * cell_m)

    open_heap: list[tuple[float, float, int, int]] = [(heuristic(sr, sc), 0.0, sr, sc)]
    g_score: dict[tuple[int, int], float] = {start: 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    closed: set[tuple[int, int]] = set()

    neighbors = (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    )

    while open_heap:
        _f, g_curr, r, c = heapq.heappop(open_heap)
        curr = (r, c)
        if curr in closed:
            continue
        if curr == goal:
            path = [curr]
            while curr in came_from:
                curr = came_from[curr]
                path.append(curr)
            path.reverse()
            return path
        closed.add(curr)

        for dr, dc in neighbors:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            nxt = (nr, nc)
            if nxt in closed:
                continue

            s_val = float(slope_deg[nr, nc])
            if strict_barrier and nxt != goal and nxt != start and s_val > max_slope_deg:
                continue

            step_dist = cell_m * math.hypot(dr, dc)
            slope_cost = 1.0 + 0.5 * (s_val / max_slope_deg) ** 2
            shadow_cost = 0.75 if (bool(psr_floor[nr, nc]) and nxt != goal) else 0.0
            excess_cost = (
                50.0 * ((s_val - max_slope_deg) / max_slope_deg) ** 2
                if (not strict_barrier and s_val > max_slope_deg)
                else 0.0
            )
            tentative_g = g_curr + step_dist * (slope_cost + shadow_cost + excess_cost)

            if tentative_g < g_score.get(nxt, float("inf")):
                g_score[nxt] = tentative_g
                came_from[nxt] = curr
                heapq.heappush(open_heap, (tentative_g + heuristic(nr, nc), tentative_g, nr, nc))

    return None


def find_safe_corridor(
    site_id: str,
    target_psr: str | None = None,
    grid_size: int = 35,
    max_slope_deg: float = 15.0,
) -> dict[str, object]:
    """Aday iniş noktasından hedef PSR krater kenarına A* ile güvenli koridor planlar.

    ``target_psr=None`` verildiğinde stereografik mesafeye göre en yakın PSR
    krater kenarı seçilir. ``estimated_eva_hours``, ``DEFAULT_ROVER_SPEED_KMH``
    (1.5 km/saat) temel alınarak hesaplanır.
    """
    if grid_size < 5:
        raise ValueError("grid_size en az 5 olmalıdır.")
    if max_slope_deg <= 0.0:
        raise ValueError("max_slope_deg pozitif olmalıdır.")

    site = get_candidate_site(site_id)
    target = _resolve_psr_target(site.x_m, site.y_m, target_psr)

    psr_cx, psr_cy = lonlat_to_xy(
        float(target["longitude_deg_east"]),
        float(target["latitude_deg"]),
    )
    r_psr_m = float(target["radius_km"]) * 1000.0
    dx = site.x_m - psr_cx
    dy = site.y_m - psr_cy
    dist_c = math.hypot(dx, dy)
    ux, uy = (dx / dist_c, dy / dist_c) if dist_c > 1e-3 else (1.0, 0.0)

    target_x_m = psr_cx + r_psr_m * ux
    target_y_m = psr_cy + r_psr_m * uy
    target_lon_deg, target_lat_deg = xy_to_lonlat(target_x_m, target_y_m)

    mid_x = 0.5 * (site.x_m + target_x_m)
    mid_y = 0.5 * (site.y_m + target_y_m)
    span = max(abs(target_x_m - site.x_m), abs(target_y_m - site.y_m))
    half_extent = max(5_000.0, 0.75 * span)

    xs = np.linspace(mid_x - half_extent, mid_x + half_extent, grid_size)
    ys = np.linspace(mid_y - half_extent, mid_y + half_extent, grid_size)
    xg, yg = np.meshgrid(xs, ys)

    rho = np.hypot(xg, yg)
    lat_grid = np.degrees(2.0 * np.arctan2(rho, 2.0 * R_MOON_M) - np.pi / 2.0)
    lon_grid = _normalize_lon_180(np.where(rho > 0.0, np.degrees(np.arctan2(xg, yg)), 0.0))

    elev_m = compute_lunar_elevation(lat_grid, lon_grid) * 1000.0
    cell_m = (2.0 * half_extent) / (grid_size - 1)
    dz_dy, dz_dx = np.gradient(elev_m, cell_m)
    slope_deg = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    psr_floor = _compute_crater_floor_psr_mask(lat_grid, lon_grid)

    sr = int(np.argmin(np.abs(ys - site.y_m)))
    sc = int(np.argmin(np.abs(xs - site.x_m)))
    gr = int(np.argmin(np.abs(ys - target_y_m)))
    gc = int(np.argmin(np.abs(xs - target_x_m)))

    path = _astar_grid(
        slope_deg,
        psr_floor,
        (sr, sc),
        (gr, gc),
        cell_m,
        max_slope_deg,
        strict_barrier=True,
    )
    if path is None:
        path = _astar_grid(
            slope_deg,
            psr_floor,
            (sr, sc),
            (gr, gc),
            cell_m,
            max_slope_deg,
            strict_barrier=False,
        )
    if path is None:
        path = [(sr, sc), (gr, gc)]

    waypoints: list[dict[str, object]] = []
    solar_safe_flags: list[bool] = []
    cumulative_km = 0.0
    prev_x = site.x_m
    prev_y = site.y_m

    for step, (r, c) in enumerate(path):
        if step == 0:
            wx, wy = site.x_m, site.y_m
            w_lon, w_lat = xy_to_lonlat(wx, wy)
            w_elev = float(compute_lunar_elevation(w_lat, w_lon) * 1000.0)
        elif step == len(path) - 1:
            wx, wy = target_x_m, target_y_m
            w_lon, w_lat = target_lon_deg, target_lat_deg
            w_elev = float(compute_lunar_elevation(w_lat, w_lon) * 1000.0)
        else:
            wx = float(xs[c])
            wy = float(ys[r])
            w_lon = float(lon_grid[r, c])
            w_lat = float(lat_grid[r, c])
            w_elev = float(elev_m[r, c])

        if step > 0:
            cumulative_km += math.hypot(wx - prev_x, wy - prev_y) / 1000.0
        prev_x, prev_y = wx, wy

        local_slope = float(slope_deg[r, c])
        is_solar_safe = (not bool(psr_floor[r, c])) and (local_slope <= max_slope_deg)
        solar_safe_flags.append(is_solar_safe)

        waypoints.append(
            {
                "step": step,
                "lat_deg": round(w_lat, 6),
                "lon_deg_east": round(w_lon, 6),
                "x_m": round(wx, 2),
                "y_m": round(wy, 2),
                "elevation_m": round(w_elev, 2),
                "local_slope_deg": round(local_slope, 3),
                "cumulative_km": round(cumulative_km, 4),
            }
        )

    total_distance_km = round(cumulative_km, 4)
    estimated_eva_hours = round(total_distance_km / DEFAULT_ROVER_SPEED_KMH, 3)
    route_slopes = [float(wp["local_slope_deg"]) for wp in waypoints]
    solar_safe_fraction_pct = round(
        100.0 * sum(1 for flag in solar_safe_flags if flag) / len(solar_safe_flags),
        2,
    )

    return {
        "site_id": site.site_id,
        "site_name": site.site_name,
        "target_name": str(target["name"]),
        "target_lat_deg": round(target_lat_deg, 6),
        "target_lon_deg_east": round(target_lon_deg, 6),
        "total_distance_km": total_distance_km,
        "estimated_eva_hours": estimated_eva_hours,
        "max_route_slope_deg": round(max(route_slopes), 3),
        "mean_route_slope_deg": round(float(np.mean(route_slopes)), 3),
        "solar_safe_fraction_pct": solar_safe_fraction_pct,
        "waypoints": waypoints,
    }


__all__ = [
    "DEFAULT_ROVER_SPEED_KMH",
    "PSR_TARGETS",
    "find_safe_corridor",
]
