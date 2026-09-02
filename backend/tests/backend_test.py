"""Backend API tests for the ISRO Dead-Reckoning dashboard."""
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
SAMPLE_CSV = "/app/backend/sample_data/S-S1.csv"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    return s


@pytest.fixture(scope="session")
def preset_session(client):
    r = client.post(f"{BASE_URL}/api/dataset/load-preset", timeout=180)
    assert r.status_code == 200, r.text[:500]
    return r.json()


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


# --- Dataset ---
class TestDataset:
    def test_load_preset_schema(self, preset_session):
        d = preset_session
        for k in ["session_id", "n_samples", "duration_s", "lat0", "lon0", "preview", "sensor_series"]:
            assert k in d, f"missing {k}"
        assert isinstance(d["session_id"], str) and len(d["session_id"]) > 0
        assert d["n_samples"] > 100
        assert d["duration_s"] > 10
        assert 8 <= abs(d["lat0"]) <= 90 or abs(d["lat0"]) > 0
        assert len(d["preview"]) == 8
        ss = d["sensor_series"]
        keys = ["t", "ax", "ay", "az", "wyaw", "wpit", "wrol", "speed", "yaw"]
        lens = {k: len(ss[k]) for k in keys}
        assert len(set(lens.values())) == 1, f"series length mismatch {lens}"
        assert lens["t"] > 10

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

    def test_upload_valid_csv(self, client):
        with open(SAMPLE_CSV, "rb") as f:
            r = client.post(f"{BASE_URL}/api/dataset/upload",
                            files={"file": ("S-S1.csv", f, "text/csv")}, timeout=300)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert d["n_samples"] > 100
        assert len(d["sensor_series"]["t"]) == len(d["sensor_series"]["speed"])

    def test_upload_invalid_csv(self, client):
        bad = io.BytesIO(b"a,b,c\n1,2,3\n4,5,6\n")
        r = client.post(f"{BASE_URL}/api/dataset/upload",
                        files={"file": ("bad.csv", bad, "text/csv")}, timeout=60)
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"


# --- Training ---
class TestTraining:
    def test_train_unknown_session(self, client):
        r = client.post(f"{BASE_URL}/api/pipeline/train", json={"session_id": "nope"}, timeout=60)
        assert r.status_code == 404

    def test_train_success(self, client, preset_session):
        sid = preset_session["session_id"]
        r = client.post(f"{BASE_URL}/api/pipeline/train",
                        json={"session_id": sid, "window": 20, "n_estimators": 60}, timeout=300)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        for k in ["mae", "rmse", "r2", "feature_importance", "n_train", "n_val", "velocity_preview"]:
            assert k in d
        assert d["mae"] >= 0 and d["rmse"] >= 0
        assert d["n_train"] > 0 and d["n_val"] > 0
        assert len(d["feature_importance"]) == 21
        assert d["feature_importance"][0]["importance"] >= d["feature_importance"][-1]["importance"]
        vp = d["velocity_preview"]
        assert len(vp["t"]) == len(vp["gps_speed"]) == len(vp["ml_pred"]) > 10

    def test_train_validation_bounds(self, client, preset_session):
        r = client.post(f"{BASE_URL}/api/pipeline/train",
                        json={"session_id": preset_session["session_id"], "window": 1}, timeout=60)
        assert r.status_code == 422


# --- Simulation ---
class TestSimulation:
    def test_simulate_without_training(self, client):
        r = client.post(f"{BASE_URL}/api/dataset/load-preset", timeout=180)
        assert r.status_code == 200
        sid = r.json()["session_id"]
        r2 = client.post(f"{BASE_URL}/api/pipeline/simulate",
                         json={"session_id": sid, "blackout_start_s": 120, "blackout_end_s": 150},
                         timeout=60)
        assert r2.status_code == 400, f"expected 400 got {r2.status_code}"

    def test_simulate_unknown_session(self, client):
        r = client.post(f"{BASE_URL}/api/pipeline/simulate",
                        json={"session_id": "nope", "blackout_start_s": 1, "blackout_end_s": 2},
                        timeout=60)
        assert r.status_code == 404

    def test_simulate_invalid_window(self, client, trained_session):
        r = client.post(f"{BASE_URL}/api/pipeline/simulate",
                        json={"session_id": trained_session, "blackout_start_s": 150,
                              "blackout_end_s": 120}, timeout=60)
        assert r.status_code == 400

    def test_simulate_success(self, client, trained_session):
        r = client.post(f"{BASE_URL}/api/pipeline/simulate",
                        json={"session_id": trained_session, "blackout_start_s": 120,
                              "blackout_end_s": 150}, timeout=120)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        m = d["metrics"]
        for k in ["blackout_start_s", "blackout_end_s", "blackout_duration_s", "blackout_distance_m",
                  "ins_final_drift_m", "ins_drift_pct", "ins_rmse_m", "ins_max_err_m",
                  "fused_final_drift_m", "fused_drift_pct", "fused_rmse_m", "fused_max_err_m",
                  "target_drift_pct", "meets_isro_target"]:
            assert k in m, f"metric missing: {k}"
        assert m["blackout_duration_s"] == pytest.approx(30.0)
        assert m["target_drift_pct"] == 10.0
        assert isinstance(m["meets_isro_target"], bool)
        tr = d["trajectories"]
        for name in ["ground_truth", "ins_raw", "fused"]:
            pts = tr[name]
            assert len(pts) > 50, f"{name} too short"
            assert all(len(p) == 2 for p in pts[:20])
        assert len(tr["ground_truth"]) == len(tr["fused"]) == len(tr["ins_raw"])
        vs = d["velocity_series"]
        assert len(vs["t"]) == len(vs["gps"]) == len(vs["ml"]) == len(vs["fused"]) == len(vs["blackout_flag"])
        assert sum(vs["blackout_flag"]) > 0, "no blackout flagged"
        # Core claim: fusion beats INS-only
        print(f"INS drift%={m['ins_drift_pct']:.2f} fused drift%={m['fused_drift_pct']:.2f}")
        assert m["fused_drift_pct"] < m["ins_drift_pct"], (
            f"fused drift {m['fused_drift_pct']} not better than INS {m['ins_drift_pct']}")
        assert m["fused_rmse_m"] < m["ins_rmse_m"]


@pytest.fixture(scope="session")
def trained_session(client, preset_session):
    sid = preset_session["session_id"]
    r = client.post(f"{BASE_URL}/api/pipeline/train", json={"session_id": sid}, timeout=300)
    assert r.status_code == 200, r.text[:300]
    return sid


# --- AI summary (LLM) ---
class TestAiSummary:
    def test_summary_requires_pipeline(self, client, preset_session):
        r = client.post(f"{BASE_URL}/api/ai/summary", json={"session_id": "nope"}, timeout=60)
        assert r.status_code == 400

    def test_summary_success(self, client, trained_session):
        sim = client.post(f"{BASE_URL}/api/pipeline/simulate",
                          json={"session_id": trained_session, "blackout_start_s": 120,
                                "blackout_end_s": 150}, timeout=120)
        assert sim.status_code == 200
        r = client.post(f"{BASE_URL}/api/ai/summary",
                        json={"session_id": trained_session}, timeout=180)
        assert r.status_code == 200, r.text[:300]
        text = r.json().get("summary", "")
        print("AI SUMMARY:", text[:400])
        assert isinstance(text, str) and len(text) > 50
        assert "[AI summary offline]" not in text, f"LLM failed: {text}"
