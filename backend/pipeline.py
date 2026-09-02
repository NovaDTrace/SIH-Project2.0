"""
IO-VNBD Dead Reckoning Pipeline
===============================
Loads smartphone IMU + GPS CSV, extracts sliding-window features, trains a
RandomForest velocity regressor, then runs an Inertial Navigation System with
an Extended Kalman Filter that fuses ML velocity + GPS (when available) +
non-holonomic constraints during simulated GPS blackout.

Coordinate system: local ENU (metres) around the first GPS fix.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


EARTH_R = 6_378_137.0  # WGS-84 mean radius (m)


# ---------------------------------------------------------------------------
# CSV loading & cleaning
# ---------------------------------------------------------------------------

SMARTPHONE_COLS = {
    "lat": "GPS LATITUDE (degrees)",
    "lon": "GPS LONGITUDE (degrees)",
    "alt": "GPS ALTITUDE (m)",
    "speed": "GPS SPEED (Kmh)",
    "gps_heading": "GPS ORIENTATION (\u00b0)",
    "t_ms": "TIME SINCE START (ms)",
    "ax": "ACCELEROMETER X (m/s\u00b2)",
    "ay": "ACCELEROMETER Y (m/s\u00b2)",
    "az": "ACCELEROMETER Z (m/s\u00b2)",
    "gx": "GRAVITY X (m/s\u00b2)",
    "gy": "GRAVITY Y (m/s\u00b2)",
    "gz": "GRAVITY Z (m/s\u00b2)",
    "wyaw": "GYROSCOPE Yaw (rad/s)",
    "wpit": "GYROSCOPE Pitch (rad/s)",
    "wrol": "GYROSCOPE Roll (rad/s)",
    "mx": "MAGNETIC FIELD X (\u03bcT)",
    "my": "MAGNETIC FIELD Y (\u03bcT)",
    "mz": "MAGNETIC FIELD Z (\u03bcT)",
    "yaw": "ORIENTATION (Yaw) (\u00b0)",
    "pitch": "ORIENTATION (Pitch) (\u00b0)",
    "roll": "ORIENTATION (Roll ) (\u00b0)",
}


def _match_col(columns: list[str], target: str) -> Optional[str]:
    """Loose match for messy CSV headers (whitespace / encoding differences)."""
    norm = lambda s: "".join(ch.lower() for ch in s if ch.isalnum())
    tgt = norm(target)
    for c in columns:
        if norm(c) == tgt:
            return c
    # partial match on first 10 alphanumerics as fallback
    prefix = tgt[:10]
    for c in columns:
        if norm(c).startswith(prefix):
            return c
    return None


def load_smartphone_csv(raw_bytes: bytes | str, max_rows: int = 6_000) -> pd.DataFrame:
    """Read S-S1 style smartphone CSV and return a tidy DataFrame.

    Note: we KEEP native 10 Hz resolution (no down-sampling) so that
    integration dt stays ~100 ms. If the log is longer than `max_rows`
    (~10 minutes) we truncate — a longer drive would need chunked processing.
    """
    if isinstance(raw_bytes, str):
        df = pd.read_csv(raw_bytes, encoding_errors="replace")
    else:
        df = pd.read_csv(io.BytesIO(raw_bytes), encoding_errors="replace")

    df.columns = [c.strip() for c in df.columns]

    mapping = {}
    for key, target in SMARTPHONE_COLS.items():
        col = _match_col(list(df.columns), target)
        if col is not None:
            mapping[key] = col

    required = {"lat", "lon", "speed", "t_ms", "ax", "ay", "az",
                "wyaw", "wpit", "wrol", "yaw"}
    missing = required - set(mapping)
    if missing:
        raise ValueError(f"Smartphone CSV missing required columns: {missing}")

    tidy = pd.DataFrame({k: pd.to_numeric(df[v], errors="coerce")
                         for k, v in mapping.items()})
    tidy = tidy.dropna(subset=["lat", "lon", "speed", "t_ms"]).reset_index(drop=True)

    # Skip the initial "warm-up" portion where the vehicle is stationary — the
    # heading estimator needs some motion to lock on.
    speed_ms = tidy["speed"] * (1000.0 / 3600.0)
    first_move = int((speed_ms > 2.0).idxmax()) if (speed_ms > 2.0).any() else 0
    tidy = tidy.iloc[first_move:].reset_index(drop=True)

    if len(tidy) > max_rows:
        tidy = tidy.iloc[:max_rows].reset_index(drop=True)

    tidy["t"] = (tidy["t_ms"] - tidy["t_ms"].iloc[0]) / 1000.0

    # The IO-VNBD `GPS SPEED (Kmh)` column is saturated / heavily quantised
    # (caps around 19 km/h). We derive a clean speed signal from the raw GPS
    # position track with a 2-second Gaussian-ish moving average window.
    lat_arr = tidy["lat"].to_numpy(); lon_arr = tidy["lon"].to_numpy()
    lat0 = float(lat_arr[0])
    R = EARTH_R
    x_m = np.radians(lon_arr - float(lon_arr[0])) * R * math.cos(math.radians(lat0))
    y_m = np.radians(lat_arr - lat0) * R
    t_s = tidy["t"].to_numpy()
    dx = np.diff(x_m); dy = np.diff(y_m); dt_s = np.maximum(np.diff(t_s), 1e-3)
    step_speed = np.concatenate([[0.0], np.sqrt(dx ** 2 + dy ** 2) / dt_s])
    # 21-sample rolling mean (~2 s at 10 Hz) to remove GPS quantisation noise
    W = 21
    kernel = np.ones(W) / W
    speed_gt = np.convolve(step_speed, kernel, mode="same")
    # Clamp to sane range (~150 km/h)
    speed_gt = np.clip(speed_gt, 0.0, 42.0)
    tidy["speed_ms"] = speed_gt
    return tidy


# ---------------------------------------------------------------------------
# Local ENU projection
# ---------------------------------------------------------------------------

def latlon_to_enu(lat: np.ndarray, lon: np.ndarray,
                  lat0: float, lon0: float) -> tuple[np.ndarray, np.ndarray]:
    """Approximate equirectangular projection to local ENU metres."""
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)
    lat0_r = math.radians(lat0)
    lon0_r = math.radians(lon0)
    x = (lon_r - lon0_r) * math.cos(lat0_r) * EARTH_R  # east
    y = (lat_r - lat0_r) * EARTH_R                     # north
    return x, y


def enu_to_latlon(x: np.ndarray, y: np.ndarray,
                  lat0: float, lon0: float) -> tuple[np.ndarray, np.ndarray]:
    lat0_r = math.radians(lat0)
    lat = np.degrees(y / EARTH_R) + lat0
    lon = np.degrees(x / (EARTH_R * math.cos(lat0_r))) + lon0
    return lat, lon


# ---------------------------------------------------------------------------
# Feature extraction & ML training
# ---------------------------------------------------------------------------

def extract_features(df: pd.DataFrame, window: int = 20) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sliding-window IMU statistics -> features. Target = GPS speed at window end."""
    ax = df["ax"].to_numpy()
    ay = df["ay"].to_numpy()
    az = df["az"].to_numpy()
    # Gravity-subtracted linear acceleration (body frame). Fall back to a
    # constant 9.8 m/s² Z if gravity columns are absent.
    gx = df.get("gx", pd.Series(np.zeros(len(df)))).to_numpy()
    gy = df.get("gy", pd.Series(np.zeros(len(df)))).to_numpy()
    gz = df.get("gz", pd.Series(np.full(len(df), 9.8))).to_numpy()
    lax = ax - gx; lay = ay - gy; laz = az - gz
    wyaw = df["wyaw"].to_numpy()
    wpit = df["wpit"].to_numpy()
    wrol = df["wrol"].to_numpy()
    pitch = df.get("pitch", pd.Series(np.zeros(len(df)))).to_numpy()
    roll = df.get("roll", pd.Series(np.zeros(len(df)))).to_numpy()
    speed = df["speed_ms"].to_numpy()

    la_mag = np.sqrt(lax ** 2 + lay ** 2 + laz ** 2)
    la_horiz = np.sqrt(lax ** 2 + lay ** 2)
    w_mag = np.sqrt(wyaw ** 2 + wpit ** 2 + wrol ** 2)

    n = len(df)
    if n < window + 1:
        raise ValueError("Not enough samples to build a window.")

    idx_end = np.arange(window, n)
    feats = []
    for i in idx_end:
        s = slice(i - window, i)
        feats.append([
            la_mag[s].mean(), la_mag[s].std(), la_mag[s].max(),
            la_horiz[s].mean(), la_horiz[s].std(), la_horiz[s].max(),
            lax[s].mean(), lay[s].mean(), laz[s].mean(),
            lax[s].std(), lay[s].std(), laz[s].std(),
            w_mag[s].mean(), w_mag[s].std(), w_mag[s].max(),
            wyaw[s].std(), wpit[s].std(), wrol[s].std(),
            pitch[s].mean(), roll[s].mean(),
            np.abs(np.diff(la_mag[s])).mean(),
        ])

    X = np.array(feats, dtype=np.float32)
    y = speed[idx_end].astype(np.float32)
    return X, y, idx_end


FEATURE_NAMES = [
    "la_mag_mean", "la_mag_std", "la_mag_max",
    "la_horiz_mean", "la_horiz_std", "la_horiz_max",
    "lax_mean", "lay_mean", "laz_mean",
    "lax_std", "lay_std", "laz_std",
    "w_mag_mean", "w_mag_std", "w_mag_max",
    "wyaw_std", "wpit_std", "wrol_std",
    "pitch_mean", "roll_mean",
    "jerk_mean",
]


@dataclass
class TrainedModel:
    model: RandomForestRegressor
    mae: float
    rmse: float
    r2: float
    feature_importance: list[dict]
    n_train: int
    n_val: int


def train_velocity_model(df: pd.DataFrame, window: int = 20,
                         n_estimators: int = 60) -> tuple[TrainedModel, np.ndarray]:
    X, y, idx_end = extract_features(df, window=window)
    split = int(0.8 * len(X))
    Xtr, Xv = X[:split], X[split:]
    ytr, yv = y[:split], y[split:]

    rf = RandomForestRegressor(
        n_estimators=n_estimators, max_depth=14, min_samples_leaf=4,
        n_jobs=-1, random_state=42,
    )
    rf.fit(Xtr, ytr)
    yp = rf.predict(Xv)

    mae = float(mean_absolute_error(yv, yp))
    rmse = float(math.sqrt(mean_squared_error(yv, yp)))
    ss_res = float(np.sum((yv - yp) ** 2))
    ss_tot = float(np.sum((yv - yv.mean()) ** 2)) or 1.0
    r2 = 1.0 - ss_res / ss_tot

    fi = sorted(
        [{"feature": FEATURE_NAMES[i], "importance": float(v)}
         for i, v in enumerate(rf.feature_importances_)],
        key=lambda d: d["importance"], reverse=True,
    )

    # Predict for the ENTIRE sequence (pad the initial `window` samples w/ GPS)
    v_pred_full = np.zeros(len(df), dtype=np.float32)
    v_pred_full[:window] = df["speed_ms"].to_numpy()[:window]
    v_pred_full[window:] = rf.predict(X)

    trained = TrainedModel(
        model=rf, mae=mae, rmse=rmse, r2=r2,
        feature_importance=fi, n_train=len(Xtr), n_val=len(Xv),
    )
    return trained, v_pred_full


# ---------------------------------------------------------------------------
# Dead Reckoning + Extended Kalman Filter
# ---------------------------------------------------------------------------

def unwrap_heading_deg(h_deg: np.ndarray) -> np.ndarray:
    return np.degrees(np.unwrap(np.radians(h_deg)))


def run_dead_reckoning(df: pd.DataFrame,
                       v_pred: np.ndarray,
                       blackout_start_s: float,
                       blackout_end_s: float) -> dict:
    """
    Runs three trajectories:
      * GT       : ground truth from GPS
      * INS raw  : integrates GPS speed with orientation yaw (no filter)
      * Fused    : EKF with GPS updates outside blackout + ML velocity always,
                   with non-holonomic constraint enforced in body frame.
    """
    t = df["t"].to_numpy()
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    v_gps = df["speed_ms"].to_numpy()

    # --- Heading source ---
    # ISRO note: the phone frame ≠ vehicle frame, so device-yaw is unreliable.
    # We derive the vehicle heading primarily from GPS heading (reliable when
    # moving) and *change* the heading using the gyroscope yaw rate during
    # GPS blackout. Compass heading is measured East-of-North (0° = N,
    # 90° = E). We convert to the ENU math convention (0 rad = East, CCW).
    wyaw = df["wyaw"].to_numpy()               # rad/s about phone Z
    yaw_dev_deg = df["yaw"].to_numpy()          # phone-fused yaw (deg, compass CW)
    yaw_dev = np.radians(90.0 - yaw_dev_deg)    # convert to ENU CCW rad
    yaw_dev = np.unwrap(yaw_dev)
    moving = v_gps > 2.0
    in_blackout_arr = (t >= blackout_start_s) & (t <= blackout_end_s)

    # ------------------------------------------------------------------
    # Phone-to-vehicle heading alignment (ISRO brief section 6)
    # ------------------------------------------------------------------
    # The phone's internal sensor-fusion yaw (accel+gyro+mag) is smoothed
    # and drifts slowly, but it is expressed in the *phone* frame. The
    # difference between phone yaw and the true direction of motion
    # (derived from consecutive GPS positions) is the phone-to-vehicle
    # rotational offset δ. We estimate δ during the pre-blackout window
    # where GPS is available, then apply it during blackout.
    _lat0 = float(df["lat"].iloc[0]); _lon0 = float(df["lon"].iloc[0])
    _gx, _gy = latlon_to_enu(df["lat"].to_numpy(),
                             df["lon"].to_numpy(), _lat0, _lon0)
    dxs = np.diff(_gx); dys = np.diff(_gy)
    step = np.sqrt(dxs ** 2 + dys ** 2)
    gt_hdg = np.full(len(df), np.nan)
    gt_hdg[1:] = np.where(step > 0.7, np.arctan2(dys, dxs), np.nan)

    align_mask = (~np.isnan(gt_hdg)) & moving & (~in_blackout_arr)
    if align_mask.sum() >= 5:
        offs = gt_hdg[align_mask] - yaw_dev[align_mask]
        # Circular median of the offset
        s = np.sin(offs); c = np.cos(offs)
        delta = math.atan2(np.median(s), np.median(c))
    else:
        delta = 0.0

    # Final vehicle heading:
    #   * outside blackout, moving: snap to GT-motion heading (best available)
    #   * outside blackout, stationary: carry forward last-known GT heading
    #   * during blackout: phone yaw + learned offset
    heading = yaw_dev + delta
    last_gt = None
    for i in range(len(df)):
        if (not math.isnan(gt_hdg[i])) and moving[i] and not in_blackout_arr[i]:
            heading[i] = gt_hdg[i]
            last_gt = gt_hdg[i]
        elif not in_blackout_arr[i] and last_gt is not None:
            heading[i] = last_gt

    lat0, lon0 = float(lat[0]), float(lon[0])
    gt_x, gt_y = latlon_to_enu(lat, lon, lat0, lon0)

    n = len(df)
    # Zero-velocity update helper: below 0.5 m/s the vehicle is treated as
    # stationary — this eliminates noise-driven drift while idling at lights.
    def _zupt(vv):
        return 0.0 if abs(vv) < 0.5 else vv

    v_clean = np.array([_zupt(x) for x in v_gps], dtype=np.float64)

    # --- INS raw baseline: propagate with LAST-KNOWN GPS speed (frozen at
    # blackout entry) + phone-yaw heading. This mimics a naïve dead-reckoning
    # implementation that has no ML velocity estimator.
    ins_x = np.zeros(n)
    ins_y = np.zeros(n)
    ins_x[0], ins_y[0] = gt_x[0], gt_y[0]
    v_frozen = float(v_clean[0])
    for i in range(1, n):
        dt = max(t[i] - t[i - 1], 1e-3)
        in_blk = blackout_start_s <= t[i] <= blackout_end_s
        if in_blk:
            v = v_frozen
        else:
            v = v_clean[i - 1]
            v_frozen = v
        ins_x[i] = ins_x[i - 1] + v * math.cos(heading[i - 1]) * dt
        ins_y[i] = ins_y[i - 1] + v * math.sin(heading[i - 1]) * dt

    # --- EKF fused: state = [x, y, v, psi]; measurement = GPS (x, y) ---
    x = np.array([gt_x[0], gt_y[0], v_pred[0], heading[0]], dtype=np.float64)
    P = np.diag([1.0, 1.0, 1.0, 0.1])
    Q = np.diag([0.05, 0.05, 0.5, 0.02])         # process noise
    R = np.diag([4.0, 4.0])                       # GPS meas noise (m^2)
    R_v = 0.5                                     # ML velocity noise (m/s)^2
    H_pos = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float64)
    H_v = np.array([[0, 0, 1, 0]], dtype=np.float64)

    fused_x = np.zeros(n)
    fused_y = np.zeros(n)
    fused_v = np.zeros(n)
    fused_x[0], fused_y[0], fused_v[0] = gt_x[0], gt_y[0], v_pred[0]

    blackout_flags = np.zeros(n, dtype=bool)
    for i in range(1, n):
        dt = max(t[i] - t[i - 1], 1e-3)
        # ZUPT: if ML predicts near-stationary, freeze velocity state to 0.
        if v_pred[i] < 0.5:
            x[2] = 0.0
        # --- Predict (constant velocity + turn model)
        v = x[2]
        psi = x[3]
        x[0] += v * math.cos(psi) * dt
        x[1] += v * math.sin(psi) * dt
        # heading driven by phone-fused orientation + phone→vehicle offset
        x[3] = heading[i]
        F = np.array([
            [1, 0, math.cos(psi) * dt, -v * math.sin(psi) * dt],
            [0, 1, math.sin(psi) * dt,  v * math.cos(psi) * dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])
        P = F @ P @ F.T + Q

        in_blackout = blackout_start_s <= t[i] <= blackout_end_s
        blackout_flags[i] = in_blackout

        # --- ML velocity update (always available)
        z_v = np.array([v_pred[i]])
        y_res = z_v - H_v @ x
        S = H_v @ P @ H_v.T + np.array([[R_v]])
        K = P @ H_v.T @ np.linalg.inv(S)
        x = x + (K @ y_res).flatten()
        P = (np.eye(4) - K @ H_v) @ P

        # --- GPS position update (only if not in blackout)
        if not in_blackout:
            z = np.array([gt_x[i], gt_y[i]])
            y_res = z - H_pos @ x
            S = H_pos @ P @ H_pos.T + R
            K = P @ H_pos.T @ np.linalg.inv(S)
            x = x + K @ y_res
            P = (np.eye(4) - K @ H_pos) @ P
        else:
            # Non-holonomic constraint: lateral velocity ~ 0 in body frame.
            # Since we already parameterize v as scalar forward speed this is
            # implicit; we additionally clamp v to be non-negative.
            if x[2] < 0:
                x[2] = 0.0

        fused_x[i], fused_y[i], fused_v[i] = x[0], x[1], x[2]

    gt_lat, gt_lon = enu_to_latlon(gt_x, gt_y, lat0, lon0)
    ins_lat, ins_lon = enu_to_latlon(ins_x, ins_y, lat0, lon0)
    fused_lat, fused_lon = enu_to_latlon(fused_x, fused_y, lat0, lon0)

    # --- Metrics: focus on blackout region ---
    bmask = blackout_flags
    if bmask.sum() > 0:
        ins_err = np.sqrt((ins_x[bmask] - gt_x[bmask]) ** 2 + (ins_y[bmask] - gt_y[bmask]) ** 2)
        fused_err = np.sqrt((fused_x[bmask] - gt_x[bmask]) ** 2 + (fused_y[bmask] - gt_y[bmask]) ** 2)
        # Segment distance = true GT path length during blackout (ENU steps).
        bidx = np.where(bmask)[0]
        if len(bidx) >= 2:
            seg_dist = float(np.sum(np.sqrt(np.diff(gt_x[bidx]) ** 2 +
                                            np.diff(gt_y[bidx]) ** 2)))
        else:
            seg_dist = 1.0
        seg_dist = max(seg_dist, 1.0)
        final_err_ins = float(ins_err[-1]) if len(ins_err) else 0.0
        final_err_fused = float(fused_err[-1]) if len(fused_err) else 0.0
    else:
        ins_err = np.array([0.0])
        fused_err = np.array([0.0])
        seg_dist = 1.0
        final_err_ins = final_err_fused = 0.0

    metrics = {
        "blackout_start_s": blackout_start_s,
        "blackout_end_s": blackout_end_s,
        "blackout_duration_s": float(blackout_end_s - blackout_start_s),
        "blackout_distance_m": seg_dist,
        "ins_final_drift_m": final_err_ins,
        "ins_drift_pct": 100.0 * final_err_ins / seg_dist,
        "ins_rmse_m": float(np.sqrt(np.mean(ins_err ** 2))),
        "ins_max_err_m": float(np.max(ins_err)),
        "fused_final_drift_m": final_err_fused,
        "fused_drift_pct": 100.0 * final_err_fused / seg_dist,
        "fused_rmse_m": float(np.sqrt(np.mean(fused_err ** 2))),
        "fused_max_err_m": float(np.max(fused_err)),
        "target_drift_pct": 10.0,
        "meets_isro_target": bool(100.0 * final_err_fused / seg_dist < 10.0),
    }

    # Downsample trajectories for JSON transport (~800 points max)
    step = max(1, n // 800)
    def _pts(lat_arr, lon_arr):
        return [[float(la), float(lo)] for la, lo in zip(lat_arr[::step], lon_arr[::step])]

    return {
        "metrics": metrics,
        "trajectories": {
            "ground_truth": _pts(gt_lat, gt_lon),
            "ins_raw":      _pts(ins_lat, ins_lon),
            "fused":        _pts(fused_lat, fused_lon),
        },
        "blackout_indices": [int(np.argmax(blackout_flags)) if blackout_flags.any() else 0,
                             int(len(blackout_flags) - 1 - np.argmax(blackout_flags[::-1])) if blackout_flags.any() else 0],
        "velocity_series": {
            "t": t[::step].tolist(),
            "gps": v_gps[::step].tolist(),
            "ml":  v_pred[::step].tolist(),
            "fused": fused_v[::step].tolist(),
            "blackout_flag": blackout_flags[::step].astype(int).tolist(),
        },
    }
