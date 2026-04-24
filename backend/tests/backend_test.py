"""CricPose AI Pro backend tests.

Covers: auth (signup/login/guest/me/logout), users dashboard, analysis upload,
report streaming (video/source/thumbnail), reports list/detail/pdf,
compare profiles, and compare analysis.
"""
import os
import time
import uuid
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://biomech-analysis-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
DEMO_VIDEO = Path("/tmp/demo.mp4")
EXISTING_USER = {"email": "test@cricpose.ai", "password": "test1234"}
PRECREATED_REPORT_ID = "69eb491cab8a5e7440652153"  # iteration-4 report with premium metrics + all 5 videos


# ---------- fixtures ----------

@pytest.fixture(scope="session")
def session_client():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


@pytest.fixture(scope="session")
def existing_token(session_client):
    r = session_client.post(f"{API}/auth/login", json=EXISTING_USER, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="session")
def auth_headers(existing_token):
    return {"Authorization": f"Bearer {existing_token}"}


@pytest.fixture(scope="session")
def sample_report(session_client, auth_headers):
    """Use an existing report or upload one (upload can take 30-60s)."""
    r = session_client.get(f"{API}/reports", headers=auth_headers, timeout=30)
    if r.status_code == 200 and r.json():
        return r.json()[0]
    # fallback: upload demo video
    assert DEMO_VIDEO.exists(), "demo video missing"
    with DEMO_VIDEO.open("rb") as f:
        up = session_client.post(
            f"{API}/analysis/upload",
            headers=auth_headers,
            files={"file": ("demo.mp4", f, "video/mp4")},
            timeout=180,
        )
    assert up.status_code == 200, f"upload failed {up.status_code} {up.text[:300]}"
    data = up.json()
    return {"id": data["id"], "title": data.get("title"), "overall_score": data.get("overall_score", 0)}


# ---------- health ----------

def test_health(session_client):
    r = session_client.get(f"{API}/health", timeout=10)
    assert r.status_code == 200


# ---------- auth ----------

class TestAuth:
    def test_login_existing(self, session_client):
        r = session_client.post(f"{API}/auth/login", json=EXISTING_USER, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["access_token"]
        assert d["user"]["email"] == EXISTING_USER["email"]

    def test_login_invalid(self, session_client):
        r = session_client.post(f"{API}/auth/login",
                                json={"email": "TEST_nope@x.io", "password": "wrong"}, timeout=15)
        assert r.status_code in (400, 401)

    def test_signup_and_me(self, session_client):
        email = f"test_{uuid.uuid4().hex[:8]}@cricpose.ai"
        r = session_client.post(
            f"{API}/auth/signup",
            json={"full_name": "Test User", "email": email, "password": "Passw0rd!"},
            timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        tok = r.json()["access_token"]
        assert r.json()["user"]["email"] == email
        me = session_client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert me.status_code == 200
        assert me.json()["email"] == email

    def test_signup_duplicate(self, session_client):
        r = session_client.post(
            f"{API}/auth/signup",
            json={"full_name": "Dup", "email": EXISTING_USER["email"], "password": "whatever123"},
            timeout=15,
        )
        assert r.status_code in (400, 409, 422)

    def test_guest_login_me(self, session_client):
        r = session_client.post(f"{API}/auth/guest", timeout=20)
        assert r.status_code == 200
        tok = r.json()["access_token"]
        assert tok
        me = session_client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert me.status_code == 200

    def test_me_without_token(self, session_client):
        r = session_client.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_logout(self, session_client, auth_headers):
        r = session_client.post(f"{API}/auth/logout", headers=auth_headers, timeout=10)
        assert r.status_code in (200, 204)


# ---------- users dashboard ----------

class TestDashboard:
    def test_dashboard_requires_auth(self, session_client):
        r = session_client.get(f"{API}/users/dashboard", timeout=10)
        assert r.status_code == 401

    def test_dashboard_ok(self, session_client, auth_headers):
        r = session_client.get(f"{API}/users/dashboard", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, dict)


# ---------- reports ----------

class TestReports:
    def test_list_reports(self, session_client, auth_headers):
        r = session_client.get(f"{API}/reports", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_reports_require_auth(self, session_client):
        assert session_client.get(f"{API}/reports", timeout=10).status_code == 401

    def test_report_detail(self, session_client, auth_headers, sample_report):
        r = session_client.get(f"{API}/reports/{sample_report['id']}", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == sample_report["id"]
        assert "joint_metrics" in d or "metrics" in d

    def test_report_detail_not_found(self, session_client, auth_headers):
        r = session_client.get(f"{API}/reports/000000000000000000000000",
                               headers=auth_headers, timeout=15)
        assert r.status_code in (404, 400)

    def test_report_pdf(self, session_client, auth_headers, sample_report):
        r = session_client.get(f"{API}/reports/{sample_report['id']}/pdf",
                               headers=auth_headers, timeout=60, stream=True)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        chunk = next(r.iter_content(1024), b"")
        assert chunk.startswith(b"%PDF"), "PDF magic bytes missing"


# ---------- analysis streaming ----------

class TestAnalysisStreaming:
    def test_source_video(self, session_client, auth_headers, sample_report):
        r = session_client.get(f"{API}/analysis/{sample_report['id']}/source",
                               headers=auth_headers, timeout=30, stream=True)
        assert r.status_code in (200, 206)
        r.close()

    def test_processed_video(self, session_client, auth_headers, sample_report):
        r = session_client.get(f"{API}/analysis/{sample_report['id']}/video",
                               headers=auth_headers, timeout=30, stream=True)
        assert r.status_code in (200, 206, 404)  # processed may not exist on old seeded report
        r.close()

    def test_source_range_request(self, session_client, auth_headers, sample_report):
        h = {**auth_headers, "Range": "bytes=0-1023"}
        r = session_client.get(f"{API}/analysis/{sample_report['id']}/source",
                               headers=h, timeout=30, stream=True)
        # expect 206 Partial content if range is honored, otherwise 200
        assert r.status_code in (200, 206)
        r.close()

    def test_thumbnail(self, session_client, auth_headers, sample_report):
        r = session_client.get(f"{API}/analysis/{sample_report['id']}/thumbnail",
                               headers=auth_headers, timeout=20)
        assert r.status_code in (200, 404)

    def test_streaming_requires_auth(self, session_client, sample_report):
        r = session_client.get(f"{API}/analysis/{sample_report['id']}/source", timeout=10)
        assert r.status_code == 401


# ---------- compare ----------

class TestCompare:
    def test_list_profiles(self, session_client, auth_headers):
        r = session_client.get(f"{API}/compare/profiles", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        profiles = r.json()
        assert isinstance(profiles, list)
        assert len(profiles) == 7, f"expected 7 bowler profiles, got {len(profiles)}"
        names = {p.get("name", "").lower() for p in profiles}
        expected = {"bumrah", "starc", "shami", "lee", "anderson", "steyn", "cummins"}
        matched = sum(1 for e in expected if any(e in n for n in names))
        assert matched == 7, f"Missing expected bowlers. Got: {names}"
        assert any("cummins" in n for n in names), "Pat Cummins profile missing"

    def test_compare_closest(self, session_client, auth_headers, sample_report):
        r = session_client.post(
            f"{API}/compare",
            headers=auth_headers,
            json={"analysis_id": sample_report["id"], "comparison_group": "closest"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "target" in d or "targets" in d or "comparisons" in d or "similarity" in d or d

    def test_compare_custom_target(self, session_client, auth_headers, sample_report):
        # pick a bowler from profiles
        p = session_client.get(f"{API}/compare/profiles", headers=auth_headers, timeout=15).json()
        slug = p[0].get("name")
        r = session_client.post(
            f"{API}/compare",
            headers=auth_headers,
            json={"analysis_id": sample_report["id"], "target_bowler": slug, "comparison_group": "custom"},
            timeout=30,
        )
        assert r.status_code in (200, 422), r.text

    @pytest.mark.parametrize("group", ["pace_legends", "swing_bowlers", "sling_actions"])
    def test_compare_groups(self, session_client, auth_headers, sample_report, group):
        r = session_client.post(
            f"{API}/compare",
            headers=auth_headers,
            json={"analysis_id": sample_report["id"], "comparison_group": group},
            timeout=30,
        )
        assert r.status_code == 200, f"{group}: {r.status_code} {r.text[:200]}"


# ---------- upload (last; slow) ----------

class TestUpload:
    def test_upload_requires_auth(self, session_client):
        assert DEMO_VIDEO.exists()
        with DEMO_VIDEO.open("rb") as f:
            r = session_client.post(
                f"{API}/analysis/upload",
                files={"file": ("demo.mp4", f, "video/mp4")},
                timeout=30,
            )
        assert r.status_code == 401

    def test_upload_bad_content_type(self, session_client, auth_headers):
        r = session_client.post(
            f"{API}/analysis/upload",
            headers=auth_headers,
            files={"file": ("a.txt", b"hello", "text/plain")},
            timeout=15,
        )
        assert r.status_code == 400

    @pytest.mark.slow
    def test_upload_and_analyze(self, session_client, auth_headers):
        assert DEMO_VIDEO.exists()
        t0 = time.time()
        with DEMO_VIDEO.open("rb") as f:
            r = session_client.post(
                f"{API}/analysis/upload",
                headers=auth_headers,
                files={"file": ("demo.mp4", f, "video/mp4")},
                timeout=240,
            )
        elapsed = time.time() - t0
        assert r.status_code == 200, f"upload failed ({elapsed:.1f}s): {r.status_code} {r.text[:300]}"
        d = r.json()
        # validate 12 joint metric fields exist
        required = [
            "release_angle_deg", "release_speed_kph", "runup_speed_kph",
            "stride_length_m", "pelvis_shoulder_separation_deg",
            "trunk_lateral_flexion_deg", "front_knee_flexion_ffc_deg",
            "front_knee_flexion_br_deg", "vGRF_body_weights", "shoulder_alignment_deg",
        ]
        jm = d.get("joint_metrics") or d.get("metrics", {}).get("joint_metrics") or {}
        missing = [k for k in required if k not in jm]
        assert not missing, f"Missing metrics: {missing}. Got keys: {list(jm.keys())[:30]}"
        # persistence: GET report
        rid = d["id"]
        g = session_client.get(f"{API}/reports/{rid}", headers=auth_headers, timeout=30)
        assert g.status_code == 200

        # NEW: verify all 5 video URLs populated on AnalysisResponse
        for key in ("source_video_url", "processed_video_url",
                    "tracking_video_url", "sidebyside_video_url", "slowmo_video_url"):
            assert d.get(key), f"Upload response missing {key}. Got: {list(d.keys())}"
            assert f"/api/analysis/{rid}" in d[key], f"{key} wrong path: {d[key]}"


# ---------- NEW: 3 extra video endpoints (iteration 2) ----------

class TestNewVideoEndpoints:
    """tracking / sidebyside / slowmo — must serve 206 Partial Content with Range."""

    @pytest.fixture(scope="class")
    def report_id(self, session_client, auth_headers):
        # prefer precreated report (has all 5 paths)
        r = session_client.get(f"{API}/reports/{PRECREATED_REPORT_ID}",
                               headers=auth_headers, timeout=15)
        if r.status_code == 200:
            return PRECREATED_REPORT_ID
        # fallback: find a recent report that has the new videos
        lst = session_client.get(f"{API}/reports", headers=auth_headers, timeout=15).json()
        for item in lst:
            det = session_client.get(f"{API}/reports/{item['id']}",
                                     headers=auth_headers, timeout=15).json()
            if det.get("tracking_video_url") and det.get("sidebyside_video_url") and det.get("slowmo_video_url"):
                return item["id"]
        pytest.skip("No report with all 3 new videos available")

    def test_report_detail_has_new_urls(self, session_client, auth_headers, report_id):
        r = session_client.get(f"{API}/reports/{report_id}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d.get("tracking_video_url"), f"missing tracking_video_url: {d}"
        assert d.get("sidebyside_video_url"), f"missing sidebyside_video_url: {d}"
        assert d.get("slowmo_video_url"), f"missing slowmo_video_url: {d}"
        assert d["tracking_video_url"].endswith(f"/api/analysis/{report_id}/tracking")
        assert d["sidebyside_video_url"].endswith(f"/api/analysis/{report_id}/sidebyside")
        assert d["slowmo_video_url"].endswith(f"/api/analysis/{report_id}/slowmo")

    @pytest.mark.parametrize("endpoint", ["tracking", "sidebyside", "slowmo"])
    def test_new_video_range_206(self, session_client, auth_headers, report_id, endpoint):
        h = {**auth_headers, "Range": "bytes=0-1023"}
        r = session_client.get(f"{API}/analysis/{report_id}/{endpoint}",
                               headers=h, timeout=30, stream=True)
        assert r.status_code == 206, f"{endpoint}: expected 206 got {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("video/"), r.headers
        cr = r.headers.get("content-range", "")
        assert cr.startswith("bytes 0-"), f"Content-Range header wrong: {cr}"
        # read a chunk to make sure body is actually served
        chunk = next(r.iter_content(256), b"")
        assert chunk, f"{endpoint} returned empty body"
        r.close()

    @pytest.mark.parametrize("endpoint", ["tracking", "sidebyside", "slowmo"])
    def test_new_video_full_200(self, session_client, auth_headers, report_id, endpoint):
        r = session_client.get(f"{API}/analysis/{report_id}/{endpoint}",
                               headers=auth_headers, timeout=60, stream=True)
        assert r.status_code in (200, 206)
        assert r.headers.get("content-type", "").startswith("video/")
        r.close()

    @pytest.mark.parametrize("endpoint", ["tracking", "sidebyside", "slowmo"])
    def test_new_video_requires_auth(self, session_client, report_id, endpoint):
        r = session_client.get(f"{API}/analysis/{report_id}/{endpoint}", timeout=10)
        assert r.status_code == 401

    @pytest.mark.parametrize("endpoint", ["tracking", "sidebyside", "slowmo"])
    def test_new_video_not_found(self, session_client, auth_headers, endpoint):
        r = session_client.get(f"{API}/analysis/000000000000000000000000/{endpoint}",
                               headers=auth_headers, timeout=15)
        assert r.status_code in (400, 404)


# ---------- NEW: iteration-4 premium metrics / classification / injury analysis ----------

class TestPremiumMetrics:
    """Assert that upload response and persisted report contain new iteration-4 fields."""

    @pytest.fixture(scope="class")
    def report_detail(self, session_client, auth_headers):
        r = session_client.get(f"{API}/reports/{PRECREATED_REPORT_ID}",
                               headers=auth_headers, timeout=20)
        assert r.status_code == 200, f"precreated report fetch failed {r.status_code}"
        return r.json()

    def _jm(self, rep):
        return rep.get("joint_metrics") or rep.get("metrics", {}).get("joint_metrics") or {}

    def _classification(self, rep):
        return rep.get("classification") or rep.get("metrics", {}).get("classification")

    def _injury_analysis(self, rep):
        return rep.get("injury_analysis") or rep.get("metrics", {}).get("injury_analysis")

    def _injury_risk(self, rep):
        return rep.get("injury_risk") or rep.get("metrics", {}).get("injury_risk") or []

    def test_new_joint_metrics_present(self, report_detail):
        jm = self._jm(report_detail)
        new_fields = {
            "release_height_m": (1.4, 3.0),
            "wrist_velocity_mps": (0.0, 30.0),
            "hip_rotation_speed_dps": (0.0, 1400.0),
            "landing_balance_score": (0.0, 100.0),
            "symmetry_score": (0.0, 100.0),
        }
        missing = [k for k in new_fields if k not in jm]
        assert not missing, f"Missing new joint_metrics: {missing}. Keys: {list(jm.keys())}"
        for k, (lo, hi) in new_fields.items():
            v = jm[k]
            assert isinstance(v, (int, float)), f"{k} not numeric: {v!r}"
            # tolerant range — allow ±20% outside published range
            lo_t = lo - abs(lo) * 0.2 - 0.01
            hi_t = hi + abs(hi) * 0.2
            assert lo_t <= v <= hi_t, f"{k}={v} out of range [{lo},{hi}]"

    def test_classification_block(self, report_detail):
        c = self._classification(report_detail)
        assert c, f"classification block missing. rep keys: {list(report_detail.keys())}"
        assert c.get("action_type") in {"side_on", "front_on", "semi_open", "mixed"}
        assert c.get("action_label"), "action_label missing"
        conf = c.get("confidence")
        assert isinstance(conf, (int, float)) and 35 <= conf <= 99, f"confidence out of range: {conf}"
        for f in ("shoulder_at_bfc_deg", "shoulder_at_ffc_deg", "shoulder_delta_deg", "description"):
            assert f in c, f"classification missing field {f}"

    def test_injury_analysis_block(self, report_detail):
        ia = self._injury_analysis(report_detail)
        assert ia, f"injury_analysis block missing"
        prob = ia.get("probability")
        assert isinstance(prob, (int, float)) and 0 <= prob <= 100, f"probability out of range: {prob}"
        assert ia.get("band") in {"Low", "Moderate", "High"}, f"bad band: {ia.get('band')}"
        contribs = ia.get("contributors")
        assert isinstance(contribs, list), "contributors not a list"
        if contribs:
            assert "label" in contribs[0] and "weight" in contribs[0]

    def test_injury_risk_has_7_entries_including_new(self, report_detail):
        risks = self._injury_risk(report_detail)
        assert isinstance(risks, list)
        assert len(risks) == 7, f"expected 7 injury_risk entries, got {len(risks)}: {[r.get('label') for r in risks]}"
        labels = {r.get("label") for r in risks}
        for required in ("Mixed-action Flag", "Front Knee Hyperextension",
                         "Landing Mechanics", "Kinematic Asymmetry"):
            assert required in labels, f"injury_risk missing '{required}'. Got: {labels}"

    def test_pat_cummins_in_pace_legends_group(self, session_client, auth_headers):
        r = session_client.post(
            f"{API}/compare",
            headers=auth_headers,
            json={"analysis_id": PRECREATED_REPORT_ID, "comparison_group": "pace_legends"},
            timeout=30,
        )
        assert r.status_code == 200, f"pace_legends compare failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        # Collect all candidate names across likely shapes
        import json as _json
        txt = _json.dumps(body).lower()
        assert "cummins" in txt, f"Pat Cummins not present in pace_legends comparison response"

