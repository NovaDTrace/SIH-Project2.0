"""FastAPI backend for the ISRO Dead-Reckoning Dashboard."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from pipeline import (
    FEATURE_NAMES,
    load_smartphone_csv,
    load_vbox_csv,
    merge_smartphone_vbox,
    run_dead_reckoning,
    train_velocity_model,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# --- DB (kept minimal - we mostly cache in-memory for MVP speed) ---
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="ISRO Dead Reckoning API")
api = APIRouter(prefix="/api")

# In-memory session store (single process, fine for MVP)
SESSIONS: Dict[str, Dict[str, Any]] = {}
SAMPLE_S_CSV = ROOT_DIR / "sample_data" / "S-S1.csv"
SAMPLE_V_CSV = ROOT_DIR / "sample_data" / "V-S1.csv"

log = logging.getLogger("dr_api")
logging.basicConfig(level=logging.INFO)


# ------------------------ Schemas ------------------------

class SessionOut(BaseModel):
    session_id: str
    n_samples: int
    duration_s: float
    lat0: float
    lon0: float
    preview: list[dict]
    sensor_series: dict
    has_vbox: bool = False
    gt_source: str = "smartphone_gps"


class TrainIn(BaseModel):
    session_id: str
    window: int = Field(default=20, ge=5, le=100)
    n_estimators: int = Field(default=60, ge=10, le=200)


class TrainOut(BaseModel):
    mae: float
    rmse: float
    r2: float
    feature_importance: list[dict]
    n_train: int
    n_val: int
    velocity_preview: dict


class SimIn(BaseModel):
    session_id: str
    blackout_start_s: float
    blackout_end_s: float


class AiSummaryIn(BaseModel):
    session_id: str


# ------------------------ Helpers ------------------------

def _build_session(df: pd.DataFrame) -> SessionOut:
    sid = uuid.uuid4().hex[:12]
    has_vbox = "gt_lat" in df.columns
    SESSIONS[sid] = {"df": df, "model": None, "v_pred": None, "sim": None,
                     "has_vbox": has_vbox,
                     "created": datetime.now(timezone.utc)}

    step = max(1, len(df) // 400)
    ss = df.iloc[::step].reset_index(drop=True)
    sensor_series = {
        "t": ss["t"].round(2).tolist(),
        "ax": ss["ax"].round(3).tolist(),
        "ay": ss["ay"].round(3).tolist(),
        "az": ss["az"].round(3).tolist(),
        "wyaw": ss["wyaw"].round(4).tolist(),
        "wpit": ss["wpit"].round(4).tolist(),
        "wrol": ss["wrol"].round(4).tolist(),
        "speed": ss["speed_ms"].round(3).tolist(),
        "yaw": ss["yaw"].round(2).tolist(),
    }
    if has_vbox:
        sensor_series["gt_v"] = ss["gt_v_ms"].round(3).tolist()
        if "gt_wheel_fl" in ss.columns:
            sensor_series["wheel_fl"] = ss["gt_wheel_fl"].round(3).tolist()

    lat_col = "gt_lat" if has_vbox else "lat"
    lon_col = "gt_lon" if has_vbox else "lon"
    preview_cols = ["t", lat_col, lon_col, "speed_ms", "ax", "ay", "az",
                    "wyaw", "yaw"]
    if has_vbox:
        preview_cols += ["gt_v_ms", "gt_heading_deg"]
    preview = df.head(8)[[c for c in preview_cols if c in df.columns]].round(4)\
        .to_dict(orient="records")

    return SessionOut(
        session_id=sid,
        n_samples=len(df),
        duration_s=float(df["t"].iloc[-1] - df["t"].iloc[0]),
        lat0=float(df[lat_col].iloc[0]),
        lon0=float(df[lon_col].iloc[0]),
        preview=preview,
        sensor_series=sensor_series,
        has_vbox=has_vbox,
        gt_source="vbox" if has_vbox else "smartphone_gps",
    )


# ------------------------ Routes ------------------------

@api.get("/")
async def root():
    return {"service": "ISRO Dead Reckoning API", "status": "online"}


@api.post("/dataset/load-preset", response_model=SessionOut)
async def load_preset():
    if not SAMPLE_S_CSV.exists():
        raise HTTPException(500, "Preset smartphone dataset not bundled")
    sdf = await asyncio.to_thread(load_smartphone_csv, str(SAMPLE_S_CSV))
    if SAMPLE_V_CSV.exists():
        vdf = await asyncio.to_thread(load_vbox_csv, str(SAMPLE_V_CSV))
        try:
            merged = await asyncio.to_thread(merge_smartphone_vbox, sdf, vdf)
            return _build_session(merged)
        except Exception as e:
            log.warning(f"Could not align VBOX: {e}. Falling back to smartphone-only.")
    return _build_session(sdf)


@api.post("/dataset/upload", response_model=SessionOut)
async def upload_csv(
    smartphone: UploadFile = File(..., description="S-S1 style smartphone CSV"),
    vbox: Optional[UploadFile] = File(None, description="V-S1 style VBOX CSV (optional)"),
):
    s_raw = await smartphone.read()
    try:
        sdf = await asyncio.to_thread(load_smartphone_csv, s_raw)
    except Exception as e:
        raise HTTPException(400, f"Could not parse smartphone CSV: {e}")

    if vbox is not None:
        v_raw = await vbox.read()
        try:
            vdf = await asyncio.to_thread(load_vbox_csv, v_raw)
            sdf = await asyncio.to_thread(merge_smartphone_vbox, sdf, vdf)
        except Exception as e:
            raise HTTPException(400, f"Could not parse or align VBOX CSV: {e}")

    return _build_session(sdf)


@api.get("/dataset/{session_id}")
async def get_session(session_id: str):
    s = SESSIONS.get(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    df = s["df"]
    return {
        "session_id": session_id,
        "n_samples": int(len(df)),
        "duration_s": float(df["t"].iloc[-1] - df["t"].iloc[0]),
        "trained": s["model"] is not None,
        "simulated": s["sim"] is not None,
    }


@api.post("/pipeline/train", response_model=TrainOut)
async def train(payload: TrainIn):
    s = SESSIONS.get(payload.session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    df = s["df"]

    try:
        trained, v_pred = await asyncio.to_thread(
            train_velocity_model, df, payload.window, payload.n_estimators)
    except Exception as e:
        raise HTTPException(400, f"Training failed: {e}")

    s["model"] = trained
    s["v_pred"] = v_pred

    step = max(1, len(df) // 400)
    return TrainOut(
        mae=trained.mae, rmse=trained.rmse, r2=trained.r2,
        feature_importance=trained.feature_importance,
        n_train=trained.n_train, n_val=trained.n_val,
        velocity_preview={
            "t": df["t"].iloc[::step].round(2).tolist(),
            "gps_speed": df["speed_ms"].iloc[::step].round(3).tolist(),
            "ml_pred": [float(x) for x in v_pred[::step]],
        },
    )


@api.post("/pipeline/simulate")
async def simulate(payload: SimIn):
    s = SESSIONS.get(payload.session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    if s["v_pred"] is None:
        raise HTTPException(400, "Train the ML model before running the simulation")

    df = s["df"]
    if payload.blackout_end_s <= payload.blackout_start_s:
        raise HTTPException(400, "blackout_end_s must be greater than blackout_start_s")

    result = await asyncio.to_thread(
        run_dead_reckoning, df, s["v_pred"],
        payload.blackout_start_s, payload.blackout_end_s)
    s["sim"] = result
    return result


@api.post("/ai/summary")
async def ai_summary(payload: AiSummaryIn):
    s = SESSIONS.get(payload.session_id)
    if not s or not s.get("sim") or not s.get("model"):
        raise HTTPException(400, "Run training and simulation first")

    m = s["sim"]["metrics"]
    tm = s["model"]
    prompt = (
        "You are a mission-control engineer explaining a GPS-denied dead-reckoning "
        "run to an ISRO review panel. Be concise (<180 words) and technical.\n\n"
        f"Session: {payload.session_id}\n"
        f"Blackout window: {m['blackout_start_s']:.1f}s -> {m['blackout_end_s']:.1f}s "
        f"({m['blackout_duration_s']:.1f}s, ~{m['blackout_distance_m']:.1f} m traversed)\n\n"
        f"ML velocity model (RandomForest): MAE={tm.mae:.3f} m/s, RMSE={tm.rmse:.3f} m/s, R2={tm.r2:.3f}\n\n"
        f"INS-only performance:  final drift {m['ins_final_drift_m']:.2f} m "
        f"({m['ins_drift_pct']:.2f}% of segment), RMSE {m['ins_rmse_m']:.2f} m\n"
        f"ML + EKF fused:        final drift {m['fused_final_drift_m']:.2f} m "
        f"({m['fused_drift_pct']:.2f}% of segment), RMSE {m['fused_rmse_m']:.2f} m\n\n"
        f"ISRO drift target: <10% of blackout distance. "
        f"Fused meets target: {m['meets_isro_target']}.\n\n"
        "Write: (1) one-line verdict, (2) key drivers of the drift reduction, "
        "(3) one concrete next step to further reduce drift."
    )

    # Import here so backend still starts even if the SDK is temporarily broken.
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception as e:
        return {"summary": f"[AI summary offline] {e}"}

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {"summary": "[AI summary offline] EMERGENT_LLM_KEY missing"}

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"dr-{payload.session_id}",
            system_message="You are a precise aerospace navigation engineer.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=prompt))
        text = str(resp) if resp else ""
    except Exception as e:
        log.exception("LLM call failed")
        return {"summary": f"[AI summary offline] {e}"}

    return {"summary": text.strip()}


@api.get("/features")
async def features():
    return {"feature_names": FEATURE_NAMES}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def _shutdown():
    client.close()
