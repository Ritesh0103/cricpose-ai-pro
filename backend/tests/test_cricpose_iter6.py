"""CricPose iteration-6 backend tests.

Focus: new /api/analysis/demo endpoint, upload error responses (415/413/400/422),
CSV/PDF/compare/dashboard all driven off the demo report.
"""
import os
import struct
import uuid
import zlib

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
EXISTING_USER = {"email": "test@cricpose.ai", "password": "test1234"}


# -------------------- fixtures --------------------

@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(client):
    r = client.post(f"{API}/auth/login", json=EXISTING_USER, timeout=30)
    if r.status_code != 200:
        client.post(
            f"{API}/auth/signup",
            json={"full_name": "Test User", "email": EXISTING_USER["email"],
                  "password": EXISTING_USER["password"]},
            timeout=30,
        )
        r = client.post(f"{API}/auth/login", json=EXISTING_USER, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def demo_report(client, auth_headers):
    r = client.post(f"{API}/analysis/demo", headers=auth_headers, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


# -------------------- health + auth --------------------

def test_health(client):
    assert client.get(f"{API}/health", timeout=10).status_code == 200


class TestAuth:
    def test_signup_and_login(self, client):
        email = f"test_{uuid.uuid4().hex[:8]}@cricpose.ai"
        r = client.post(
            f"{API}/auth/signup",
            json={"full_name": "Iter6", "email": email, "password": "Passw0rd!"},
            timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        assert r.json()["access_token"]

    def test_signup_duplicate(self, client):
        r = client.post(
            f"{API}/auth/signup",
            json={"full_name": "Dup", "email": EXISTING_USER["email"],
                  "password": "whatever123"},
            timeout=15,
        )
        assert r.status_code in (400, 409, 422)

    def test_login_valid(self, client):
        r = client.post(f"{API}/auth/login", json=EXISTING_USER, timeout=20)
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_login_invalid(self, client):
        r = client.post(f"{API}/auth/login",
                        json={"email": EXISTING_USER["email"], "password": "WRONG"},
                        timeout=15)
        assert r.status_code in (400, 401)

    def test_guest(self, client):
        r = client.post(f"{API}/auth/guest", timeout=20)
        assert r.status_code == 200
        assert r.json()["access_token"]


# -------------------- demo endpoint --------------------

class TestDemoEndpoint:
    def test_demo_requires_auth(self, client):
        assert client.post(f"{API}/analysis/demo", timeout=15).status_code == 401

    def test_demo_shape(self, demo_report):
        d = demo_report
        assert d.get("id")
        m = d.get("metrics") or {}
        assert m.get("is_demo") is True, f"is_demo not True: {m.get('is_demo')}"
        assert isinstance(m.get("joint_metrics"), (list, dict)) and m.get("joint_metrics")
        cls = m.get("classification") or {}
        assert cls.get("action_label") == "Semi-open", f"action_label: {cls}"
        inj = m.get("injury_analysis") or {}
        assert float(inj.get("probability", -1)) == 22.0
        assert inj.get("band") == "Low"
        risks = m.get("injury_risk") or []
        assert len(risks) == 7, f"expected 7 injury_risk entries, got {len(risks)}"
        motion = m.get("motion_series") or {}
        for key in ("wrist_trajectory", "symmetry", "risk_heatmap"):
            assert key in motion, f"motion_series missing {key}"
        # wrist_trajectory may be list of {x,y} or nested; just ensure length 120
        wt = motion["wrist_trajectory"]
        assert len(wt) == 120, f"wrist_trajectory len={len(wt)}"
        assert len(motion["symmetry"]) == 120
        assert len(motion["risk_heatmap"]) == 120
        dist = m.get("distribution_stats") or {}
        assert len(dist) >= 4, f"distribution_stats keys={list(dist.keys())}"


# -------------------- reports --------------------

class TestReports:
    def test_list_has_demo(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/reports", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert demo_report["id"] in ids

    def test_detail(self, client, auth_headers, demo_report):
        rid = demo_report["id"]
        r = client.get(f"{API}/reports/{rid}", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        assert r.json().get("id") == rid

    def test_pdf(self, client, auth_headers, demo_report):
        rid = demo_report["id"]
        r = client.get(f"{API}/reports/{rid}/pdf", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:200]
        ct = r.headers.get("content-type", "")
        assert "pdf" in ct.lower(), f"content-type={ct}"
        assert r.content[:4] == b"%PDF", f"magic={r.content[:8]!r}"


# -------------------- CSV --------------------

class TestCsv:
    def test_unknown_400(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/analysis/{demo_report['id']}/csv/unknown",
                       headers=auth_headers, timeout=15)
        assert r.status_code == 400

    def test_metrics(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/analysis/{demo_report['id']}/csv/metrics",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        text = r.text.lower()
        assert text.splitlines()[0].strip().startswith("metric,value")
        for kw in ("report_id", "title", "fps", "bowling_arm", "summary",
                   "joint", "score", "classification", "injury"):
            assert kw in text, f"metrics CSV missing '{kw}'"

    def test_motion(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/analysis/{demo_report['id']}/csv/motion",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert len(lines) == 121, f"motion lines={len(lines)}"
        hdr = lines[0].lower()
        for c in ("frame", "timestamp", "bowling_arm_angle_deg", "shoulder_alignment_deg",
                  "front_knee_bend_deg", "back_knee_bend_deg", "trunk_lateral_flexion_deg",
                  "pelvis_shoulder_separation_deg", "wrist_x_norm", "wrist_y_norm",
                  "left_knee_deg", "right_knee_deg", "trunk_flex_deg", "risk_band"):
            assert c in hdr, f"motion header missing {c}: {hdr}"

    def test_events(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/analysis/{demo_report['id']}/csv/events",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert len(lines) == 5, f"events lines={len(lines)}"


# -------------------- upload errors --------------------

class TestUploadErrors:
    def test_auth_required(self, client):
        r = client.post(f"{API}/analysis/upload",
                        files={"file": ("a.mp4", b"\x00", "video/mp4")}, timeout=15)
        assert r.status_code == 401

    def test_text_plain_415(self, client, auth_headers):
        r = client.post(
            f"{API}/analysis/upload",
            headers=auth_headers,
            files={"file": ("a.txt", b"hello", "text/plain")},
            timeout=20,
        )
        assert r.status_code == 415, f"expected 415 got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert detail and "something went wrong" not in detail
        assert "unsupported" in detail or "mp4" in detail

    def test_empty_file_400(self, client, auth_headers):
        r = client.post(
            f"{API}/analysis/upload",
            headers=auth_headers,
            files={"file": ("empty.mp4", b"", "video/mp4")},
            timeout=20,
        )
        assert r.status_code == 400, f"got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "empty" in detail

    def test_synthetic_mp4_422(self, client, auth_headers):
        """Tiny fake mp4 body that OpenCV can't decode → service should raise a
        friendly 422 whose detail starts with 'No bowler' (not generic 'Analysis failed')."""
        # Minimal mp4 ftyp box; MediaPipe/OpenCV will fail to open or detect.
        body = (
            b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
            + b"\x00" * 4096
        )
        r = client.post(
            f"{API}/analysis/upload",
            headers=auth_headers,
            files={"file": ("bad.mp4", body, "video/mp4")},
            timeout=180,
        )
        # Accept 422 with friendly body; explicitly reject 500 or generic fallback.
        assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text[:300]}"
        detail = r.json().get("detail", "")
        assert "Analysis failed" not in detail
        # Friendly messages all start with one of these phrases:
        lowered = detail.lower()
        assert ("no bowler" in lowered or "corrupt" in lowered
                or "unsupported codec" in lowered or "too short" in lowered), \
            f"detail not friendly: {detail}"


# -------------------- compare --------------------

class TestCompare:
    def test_profiles_seven(self, client, auth_headers):
        r = client.get(f"{API}/compare/profiles", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        profiles = r.json()
        assert len(profiles) == 7
        names = " ".join(p.get("name", "").lower() for p in profiles)
        assert "cummins" in names

    def test_compare_demo_closest(self, client, auth_headers, demo_report):
        r = client.post(
            f"{API}/compare",
            headers=auth_headers,
            json={"analysis_id": demo_report["id"], "comparison_group": "closest"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        best = d.get("best_match") or {}
        assert best, f"no best_match: {d}"
        # similarity_score can be nested inside best_match or at top-level
        assert ("similarity_score" in best
                or "similarity_score" in d
                or "similarity" in d), f"no similarity score field. Keys={list(d.keys())}, best_keys={list(best.keys())}"


# -------------------- dashboard --------------------

class TestDashboard:
    def test_after_demo(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/users/dashboard", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d.get("total_reports", 0) >= 1
        latest = d.get("latest") or {}
        # Accept action_label either on latest or nested classification
        label = (latest.get("action_label")
                 or (latest.get("classification") or {}).get("action_label"))
        assert label == "Semi-open", f"latest label={label} latest={latest}"
        assert isinstance(d.get("score_trend"), list) and len(d["score_trend"]) >= 1
