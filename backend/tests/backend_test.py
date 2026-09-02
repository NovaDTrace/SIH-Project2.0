"""Backend API tests for the ISRO Dead-Reckoning dashboard (VBOX-aware)."""
import io
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
SAMPLE_S_CSV = "/app/backend/sample_data/S-S1.csv"
SAMPLE_V_CSV = "/app/backend/sample_data/V-S1.csv"


@pytest.fixture(scope="session")
def client():
    return requests.Session()


@pytest.fixture(scope="session")
def preset_session(client):
    r = client.post(f"{BASE_URL}/api/dataset/load-preset", timeout=300)
    assert r.status_code == 200, r.text[:500]
    return r.json()


@pytest.fixture(scope="session")
def trained_session(client, preset_session):
    sid = preset_session["session_id"]
    r = client.post(f"{BASE_URL}/api/pipeline/train", json={"session_id": sid}, timeout=300)
    assert r.status_code == 200, r.text[:300]
    return {"sid": sid, "train": r.json()}


# --- Health ---
class TestHealth:
    def test_root(self, client):
        r = client.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "online"
        assert "ISRO" in d["service"]

    def test_features(self, client):
        r = client.get(f"{BASE_URL}/api/features", timeout=30)
        assert r.status_code == 200
        names = r.json()["feature_names"]
        assert isinstance(names, list) and len(names) == 21


# --- Dataset / preset with VBOX ground truth ---
class TestPresetVbox:
    def test_preset_has_vbox(self, preset_session):
        d = preset_session
        assert d["has_vbox"] is True, f"has_vbox not True: {d.get('has_vbox')}"
        assert d["gt_source"] == "vbox", f"gt_source={d.get('gt_source')}"

    def test_preset_shape(self, preset_session):
        d = preset_session
        assert d["n_samples"] > 4000, f"n_samples={d['n_samples']}"
        assert 400 < d["duration_s"] < 900, f"duration_s={d['duration_s']}"
        assert abs(d["lat0"]) > 0 and abs(d["lon0"]) >= 0

    def test_preset_preview_gt_fields(self, preset_session):
        rows = preset_session["preview"]
        assert len(rows) == 8
        for key in ["gt_lat", "gt_lon", "gt_v_ms", "gt_heading_deg"]:
            assert key in rows[0], f"preview missing {key}: {list(rows[0].keys())}"
        assert all(isinstance(r["gt_v_ms"], (int, float)) for r in rows)

    def test_preset_sensor_series_consistent(self, preset_session):
        ss = preset_session["sensor_series"]
        keys = ["t", "ax", "ay", "az", "wyaw", "wpit", "wrol", "speed", "yaw"]
        lens = {k: len(ss[k]) for k in keys}
        assert len(set(lens.values())) == 1, f"length mismatch {lens}"
        assert "gt_v" in ss, "gt_v series missing when VBOX present"
        assert len(ss["gt_v"]) == lens["t"]

    def test_preset_speed_range_realistic(self, preset_session):
        sp = preset_session["sensor_series"]["speed"]
        assert max(sp) > 10.0, f"max speed {max(sp)} m/s looks saturated"
        assert max(sp) < 60.0

    def test_get_session(self, client, preset_session):
        sid = preset_session["session_id"]
        r = client.get(f"{BASE_URL}/api/dataset/{sid}", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["session_id"] == sid
        assert d["n_samples"] == preset_session["n_samples"]
        assert "_id" not in d

    def test_get_session_unknown(self, client):
        r = client.get(f"{BASE_URL}/api/dataset/does-not-exist", timeout=30)
        assert r.status_code == 404


# --- Upload contract: smartphone (required) + vbox (optional) ---
class TestUpload:
    def test_upload_smartphone_only(self, client):
        with open(SAMPLE_S_CSV, "rb") as f:
            r = client.post(f"{BASE_URL}/api/dataset/upload",
                            files={"smartphone": ("S-S1.csv", f, "text/csv")}, timeout=600)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d["has_vbox"] is False
        assert d["gt_source"] == "smartphone_gps"
        assert d["n_samples"] > 100
        assert "gt_lat" not in d["preview"][0]

    def test_upload_both_files(self, client):
        with open(SAMPLE_S_CSV, "rb") as sf, open(SAMPLE_V_CSV, "rb") as vf:
            r = client.post(f"{BASE_URL}/api/dataset/upload",
                            files={"smartphone": ("S-S1.csv", sf, "text/csv"),
                                   "vbox": ("V-S1.csv", vf, "text/csv")}, timeout=600)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d["has_vbox"] is True
        assert d["gt_source"] == "vbox"
        assert "gt_v_ms" in d["preview"][0]

    def test_upload_missing_smartphone_field(self, client):
        bad = io.BytesIO(b"a,b,c\n1,2,3\n")
        r = client.post(f"{BASE_URL}/api/dataset/upload",
                        files={"file": ("bad.csv", bad, "text/csv")}, timeout=60)
        assert r.status_code == 422, f"expected 422 got {r.status_code}"

    def test_upload_invalid_smartphone_csv(self, client):
        bad = io.BytesIO(b"a,b,c\n1,2,3\n4,5,6\n")
        r = client.post(f"{BASE_URL}/api/dataset/upload",
                        files={"smartphone": ("bad.csv", bad, "text/csv")}, timeout=60)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"

    def test_upload_valid_smartphone_garbage_vbox(self, client):
        with open(SAMPLE_S_CSV, "rb") as sf:
            r = client.post(f"{BASE_URL}/api/dataset/upload",
                            files={"smartphone": ("S-S1.csv", sf, "text/csv"),
                                   "vbox": ("bad.csv", io.BytesIO(b"x,y\n1,2\n3,4\n"), "text/csv")},
                            timeout=600)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"
        assert "VBOX" in r.json().get("detail", "")


# --- Training on VBOX ground truth ---
class TestTraining:
    def test_train_unknown_session(self, client):
        r = client.post(f"{BASE_URL}/api/pipeline/train", json={"session_id": "nope"}, timeout=60)
        assert r.status_code == 404

    def test_train_validation_bounds(self, client, preset_session):
        r = client.post(f"{BASE_URL}/api/pipeline/train",
                        json={"session_id": preset_session["session_id"], "window": 1}, timeout=60)
        assert r.status_code == 422

    def test_train_schema(self, trained_session):
        d = trained_session["train"]
        for k in ["mae", "rmse", "r2", "feature_importance", "n_train", "n_val", "velocity_preview"]:
            assert k in d
        assert d["n_train"] > 0 and d["n_val"] > 0
        assert len(d["feature_importance"]) == 21
        assert d["feature_importance"][0]["importance"] >= d["feature_importance"][-1]["importance"]
        vp = d["velocity_preview"]
        assert len(vp["t"]) == len(vp["gps_speed"]) == len(vp["ml_pred"]) > 10

    def test_train_accuracy_with_vbox_gt(self, trained_session):
        d = trained_session["train"]
        print(f"MAE={d['mae']:.3f} RMSE={d['rmse']:.3f} R2={d['r2']:.3f}")
        assert d["mae"] < 5.0, f"MAE {d['mae']} not < 5.0 m/s"
        assert d["r2"] > 0.2, f"R2 {d['r2']} not > 0.2"


# --- Simulation ---
class TestSimulation:
    def test_simulate_without_training(self, client):
        r = client.post(f"{BASE_URL}/api/dataset/load-preset", timeout=300)
        assert r.status_code == 200
        sid = r.json()["session_id"]
        r2 = client.post(f"{BASE_URL}/api/pipeline/simulate",
                         json={"session_id": sid, "blackout_start_s": 120, "blackout_end_s": 150},
                         timeout=60)
        assert r2.status_code == 400

    def test_simulate_unknown_session(self, client):
        r = client.post(f"{BASE_URL}/api/pipeline/simulate",
                        json={"session_id": "nope", "blackout_start_s": 1, "blackout_end_s": 2},
                        timeout=60)
        assert r.status_code == 404

    def test_simulate_invalid_window(self, client, trained_session):
        r = client.post(f"{BASE_URL}/api/pipeline/simulate",
                        json={"session_id": trained_session["sid"], "blackout_start_s": 150,
                              "blackout_end_s": 120}, timeout=60)
        assert r.status_code == 400

    def test_simulate_schema_and_isro_target(self, client, trained_session):
        r = client.post(f"{BASE_URL}/api/pipeline/simulate",
                        json={"session_id": trained_session["sid"], "blackout_start_s": 300,
                              "blackout_end_s": 360}, timeout=180)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        m = d["metrics"]
        for k in ["blackout_start_s", "blackout_end_s", "blackout_duration_s", "blackout_distance_m",
                  "ins_final_drift_m", "ins_drift_pct", "ins_rmse_m", "ins_max_err_m",
                  "fused_final_drift_m", "fused_drift_pct", "fused_rmse_m", "fused_max_err_m",
                  "target_drift_pct", "meets_isro_target"]:
            assert k in m, f"metric missing: {k}"
        assert m["blackout_duration_s"] == pytest.approx(60.0)
        assert m["target_drift_pct"] == 10.0
        tr = d["trajectories"]
        assert len(tr["ground_truth"]) == len(tr["fused"]) == len(tr["ins_raw"]) > 50
        vs = d["velocity_series"]
        assert len(vs["t"]) == len(vs["gps"]) == len(vs["ml"]) == len(vs["fused"]) == len(vs["blackout_flag"])
        assert sum(vs["blackout_flag"]) > 0
        print(f"INS drift%={m['ins_drift_pct']:.2f} fused drift%={m['fused_drift_pct']:.2f} "
              f"target={m['meets_isro_target']}")
        assert m["fused_drift_pct"] < m["ins_drift_pct"]
        assert m["fused_rmse_m"] < m["ins_rmse_m"]
        assert m["fused_drift_pct"] <= 15.0, f"fused drift {m['fused_drift_pct']}% > 15%"
        assert m["meets_isro_target"] is True, (
            f"meets_isro_target False (fused {m['fused_drift_pct']:.2f}%)")


# --- AI summary (LLM) ---
class TestAiSummary:
    def test_summary_requires_pipeline(self, client):
        r = client.post(f"{BASE_URL}/api/ai/summary", json={"session_id": "nope"}, timeout=60)
        assert r.status_code == 400

    def test_summary_success(self, client, trained_session):
        sim = client.post(f"{BASE_URL}/api/pipeline/simulate",
                          json={"session_id": trained_session["sid"], "blackout_start_s": 300,
                                "blackout_end_s": 360}, timeout=180)
        assert sim.status_code == 200
        r = client.post(f"{BASE_URL}/api/ai/summary",
                        json={"session_id": trained_session["sid"]}, timeout=240)
        assert r.status_code == 200, r.text[:300]
        text = r.json().get("summary", "")
        print("AI SUMMARY:", text[:400])
        assert isinstance(text, str) and len(text) > 50
        assert "[AI summary offline]" not in text, f"LLM failed: {text}"
