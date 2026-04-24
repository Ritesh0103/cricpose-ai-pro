"""CricPose iteration-5 backend tests.

Focus: CSV endpoints, dashboard shape (score_trend/latest), compare profiles
(7 including Cummins), auth flow, 404/400 edge cases.

Upload-dependent tests are skipped automatically when no report exists (no real
bowling clip pre-seeded; MediaPipe rejects synthetic clips).
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
EXISTING_USER = {"email": "test@cricpose.ai", "password": "test1234"}


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Accept": "application/json"})
    return s


@pytest.fixture(scope="session")
def token(client):
    r = client.post(f"{API}/auth/login", json=EXISTING_USER, timeout=30)
    # Auto-signup if the seeded user is missing on this env
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
def any_report_id(client, auth_headers):
    r = client.get(f"{API}/reports", headers=auth_headers, timeout=20)
    assert r.status_code == 200
    lst = r.json()
    if not lst:
        pytest.skip("No report available; upload-dependent tests skipped")
    return lst[0]["id"]


# ---------- health ----------

def test_health(client):
    r = client.get(f"{API}/health", timeout=10)
    assert r.status_code == 200


# ---------- auth ----------

class TestAuth:
    def test_login_existing(self, client):
        r = client.post(f"{API}/auth/login", json=EXISTING_USER, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["access_token"]
        assert d["user"]["email"] == EXISTING_USER["email"]

    def test_login_invalid(self, client):
        r = client.post(f"{API}/auth/login",
                        json={"email": "TEST_nope@x.io", "password": "wrong"}, timeout=15)
        assert r.status_code in (400, 401)

    def test_signup_and_me(self, client):
        email = f"test_{uuid.uuid4().hex[:8]}@cricpose.ai"
        r = client.post(
            f"{API}/auth/signup",
            json={"full_name": "Test User", "email": email, "password": "Passw0rd!"},
            timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        tok = r.json()["access_token"]
        assert r.json()["user"]["email"] == email
        me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert me.status_code == 200
        assert me.json()["email"] == email

    def test_signup_duplicate(self, client):
        r = client.post(
            f"{API}/auth/signup",
            json={"full_name": "Dup", "email": EXISTING_USER["email"],
                  "password": "whatever123"},
            timeout=15,
        )
        assert r.status_code in (400, 409, 422)

    def test_guest_login(self, client):
        r = client.post(f"{API}/auth/guest", timeout=20)
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_me_without_token(self, client):
        r = client.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401


# ---------- dashboard shape ----------

class TestDashboard:
    def test_requires_auth(self, client):
        assert client.get(f"{API}/users/dashboard", timeout=10).status_code == 401

    def test_dashboard_shape(self, client, auth_headers):
        r = client.get(f"{API}/users/dashboard", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ("total_reports", "average_overall_score", "best_score",
                  "recent_activity", "score_trend", "latest"):
            assert k in d, f"dashboard missing key: {k}. Got: {list(d.keys())}"
        assert isinstance(d["score_trend"], list)
        assert isinstance(d["recent_activity"], list)
        assert d["latest"] is None or isinstance(d["latest"], dict)
        assert isinstance(d["total_reports"], int)


# ---------- compare profiles ----------

class TestCompareProfiles:
    def test_list_profiles_seven(self, client, auth_headers):
        r = client.get(f"{API}/compare/profiles", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        profiles = r.json()
        assert isinstance(profiles, list)
        assert len(profiles) == 7, f"expected 7 profiles got {len(profiles)}"
        names = " ".join(p.get("name", "") for p in profiles).lower()
        for bowler in ("bumrah", "starc", "shami", "lee", "anderson", "steyn", "cummins"):
            assert bowler in names, f"{bowler} missing from profiles: {names}"


# ---------- CSV endpoints (always-tested: 400 unknown + auth; values require report) ----------

class TestCsvEndpoints:
    FAKE_ID = "000000000000000000000000"

    def test_csv_unknown_kind_400(self, client, auth_headers):
        r = client.get(f"{API}/analysis/{self.FAKE_ID}/csv/unknown",
                       headers=auth_headers, timeout=15)
        assert r.status_code == 400, r.text

    def test_csv_requires_auth(self, client):
        r = client.get(f"{API}/analysis/{self.FAKE_ID}/csv/metrics", timeout=10)
        assert r.status_code == 401

    def test_csv_metrics(self, client, auth_headers, any_report_id):
        r = client.get(f"{API}/analysis/{any_report_id}/csv/metrics",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        text = r.text.strip()
        first = text.splitlines()[0].lower()
        assert "metric" in first and "value" in first, f"header wrong: {first}"
        assert len(text.splitlines()) > 3

    def test_csv_motion(self, client, auth_headers, any_report_id):
        r = client.get(f"{API}/analysis/{any_report_id}/csv/motion",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("text/csv")
        header = r.text.splitlines()[0].lower()
        assert "frame" in header, f"motion header missing 'frame': {header}"
        # at least one of the expected series columns
        assert any(c in header for c in ("bowling_arm_angle", "front_knee_bend",
                                         "wrist_x")), f"motion header: {header}"

    def test_csv_events(self, client, auth_headers, any_report_id):
        r = client.get(f"{API}/analysis/{any_report_id}/csv/events",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert len(lines) >= 5, f"events CSV too short: {lines}"  # header + 4 events
        body = " ".join(lines[1:]).lower()
        for ev in ("bfc", "ffc", "release", "follow"):
            assert ev in body, f"event {ev} missing: {body[:200]}"


# ---------- reports & streaming (require a report; auto-skip if none) ----------

class TestReports:
    def test_list_auth(self, client):
        assert client.get(f"{API}/reports", timeout=10).status_code == 401

    def test_detail_not_found(self, client, auth_headers):
        r = client.get(f"{API}/reports/000000000000000000000000",
                       headers=auth_headers, timeout=15)
        assert r.status_code in (400, 404)

    def test_detail_has_video_urls(self, client, auth_headers, any_report_id):
        r = client.get(f"{API}/reports/{any_report_id}", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for key in ("source_video_url", "processed_video_url",
                    "tracking_video_url", "sidebyside_video_url", "slowmo_video_url"):
            assert d.get(key), f"missing {key}"


class TestStreaming:
    @pytest.mark.parametrize("ep", ["source", "video", "tracking", "sidebyside", "slowmo"])
    def test_video_range(self, client, auth_headers, any_report_id, ep):
        h = {**auth_headers, "Range": "bytes=0-1023"}
        r = client.get(f"{API}/analysis/{any_report_id}/{ep}",
                       headers=h, timeout=30, stream=True)
        assert r.status_code in (200, 206), f"{ep}: {r.status_code}"
        r.close()

    def test_thumbnail(self, client, auth_headers, any_report_id):
        r = client.get(f"{API}/analysis/{any_report_id}/thumbnail",
                       headers=auth_headers, timeout=20)
        assert r.status_code in (200, 404)


# ---------- upload basic validations ----------

class TestUploadValidations:
    def test_upload_requires_auth(self, client):
        r = client.post(f"{API}/analysis/upload",
                        files={"file": ("a.mp4", b"\x00\x00", "video/mp4")},
                        timeout=15)
        assert r.status_code == 401

    def test_upload_bad_content_type(self, client, auth_headers):
        r = client.post(f"{API}/analysis/upload",
                        headers=auth_headers,
                        files={"file": ("a.txt", b"hello", "text/plain")},
                        timeout=15)
        assert r.status_code == 400
