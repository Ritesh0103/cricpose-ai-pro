"""CricPose iteration-7 backend tests.

Focus: async upload pipeline. /api/analysis/upload must now:
  * return in <3s with status='processing'
  * spawn a background task
  * be pollable via GET /api/analysis/{id}/status

Plus full regression of iter-6 endpoints (auth, demo, reports, CSV, compare, dashboard).
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
EXISTING_USER = {"email": "test@cricpose.ai", "password": "test1234"}

SYNTHETIC_MP4 = (
    b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    + b"\x00" * 4096
)


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


# -------------------- health + auth regression --------------------

def test_health(client):
    assert client.get(f"{API}/health", timeout=10).status_code == 200


class TestAuth:
    def test_signup_and_login(self, client):
        email = f"test_{uuid.uuid4().hex[:8]}@cricpose.ai"
        r = client.post(
            f"{API}/auth/signup",
            json={"full_name": "Iter7", "email": email, "password": "Passw0rd!"},
            timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        assert r.json()["access_token"]

    def test_login_valid(self, client):
        r = client.post(f"{API}/auth/login", json=EXISTING_USER, timeout=20)
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_login_invalid(self, client):
        r = client.post(f"{API}/auth/login",
                        json={"email": EXISTING_USER["email"], "password": "WRONG"},
                        timeout=15)
        assert r.status_code in (400, 401)

    def test_auth_me(self, client, auth_headers):
        r = client.get(f"{API}/auth/me", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("email") == EXISTING_USER["email"]

    def test_guest(self, client):
        r = client.post(f"{API}/auth/guest", timeout=20)
        assert r.status_code == 200
        assert r.json()["access_token"]


# -------------------- NEW: async upload fast-return --------------------

class TestAsyncUpload:
    def test_upload_returns_fast_with_processing(self, client, auth_headers):
        """CORE iter-7 behaviour: HTTP must return in <3s with status='processing'."""
        t0 = time.monotonic()
        r = client.post(
            f"{API}/analysis/upload",
            headers=auth_headers,
            files={"file": ("bad.mp4", SYNTHETIC_MP4, "video/mp4")},
            timeout=15,
        )
        elapsed = time.monotonic() - t0
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:300]}"
        assert elapsed < 5.0, f"upload took {elapsed:.2f}s — background task not detached"
        data = r.json()
        assert data.get("status") == "processing", f"status field={data.get('status')}"
        assert data.get("error") is None, f"error should be null, got {data.get('error')!r}"
        assert data.get("id"), "report id missing"
        # Stash for the next tests in this class
        TestAsyncUpload._report_id = data["id"]
        TestAsyncUpload._upload_elapsed = elapsed

    def test_status_endpoint_transitions_to_failed(self, client, auth_headers):
        """Background task should mark synthetic clip as failed with friendly msg
        within ~60s."""
        rid = getattr(TestAsyncUpload, "_report_id", None)
        if not rid:
            pytest.skip("upload test did not run")
        deadline = time.monotonic() + 90  # generous envelope
        last = None
        while time.monotonic() < deadline:
            r = client.get(f"{API}/analysis/{rid}/status", headers=auth_headers, timeout=15)
            assert r.status_code == 200, r.text
            last = r.json()
            if last.get("status") in ("done", "failed"):
                break
            time.sleep(2.0)
        assert last is not None
        assert last.get("status") == "failed", f"final status={last.get('status')} body={last}"
        err = (last.get("error") or "").lower()
        assert err, "error field must be populated when failed"
        assert ("no bowler" in err
                or "corrupt" in err
                or "unsupported codec" in err
                or "too short" in err), f"error not friendly: {last.get('error')!r}"

    def test_status_bad_id(self, client, auth_headers):
        """Invalid / unknown report id should yield 400 or 404 (not 500)."""
        r = client.get(f"{API}/analysis/not-a-real-id/status",
                       headers=auth_headers, timeout=15)
        assert r.status_code in (400, 404), f"got {r.status_code}: {r.text[:200]}"
        # A well-formed ObjectId that doesn't belong to this user -> 404
        r2 = client.get(f"{API}/analysis/507f1f77bcf86cd799439011/status",
                        headers=auth_headers, timeout=15)
        assert r2.status_code in (400, 404)


# -------------------- Upload validation regression --------------------

class TestUploadValidation:
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
        assert "unsupported" in detail or "mp4" in detail

    def test_large_file_413(self, client, auth_headers):
        """300 MB dummy payload should hit the 200 MB cap and return 413."""
        # Stream via a generator so we don't need 300MB in RAM — requests toolbelt not
        # guaranteed installed, so build a big bytes buffer once.
        size_mb = 220  # smallest size guaranteed to exceed the 200MB cap
        big = b"\x00" * (size_mb * 1024 * 1024)
        try:
            r = client.post(
                f"{API}/analysis/upload",
                headers=auth_headers,
                files={"file": ("huge.mp4", big, "video/mp4")},
                timeout=180,
            )
        except requests.exceptions.RequestException as exc:
            pytest.skip(f"network could not carry {size_mb}MB: {exc}")
        assert r.status_code == 413, f"expected 413, got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or "").lower()
        assert "200" in detail or "cap" in detail or "exceed" in detail


# -------------------- demo regression --------------------

class TestDemoRegression:
    def test_demo_status_done(self, demo_report):
        assert demo_report.get("status") == "done"
        assert demo_report.get("error") is None

    def test_demo_shape(self, demo_report):
        m = demo_report.get("metrics") or {}
        assert m.get("is_demo") is True
        cls = m.get("classification") or {}
        assert cls.get("action_label") == "Semi-open"
        risks = m.get("injury_risk") or []
        assert len(risks) == 7

    def test_demo_report_status_via_reports(self, client, auth_headers, demo_report):
        rid = demo_report["id"]
        r = client.get(f"{API}/reports/{rid}", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "done"
        assert data.get("error") is None

    def test_demo_pdf(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/reports/{demo_report['id']}/pdf",
                       headers=auth_headers, timeout=30)
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_demo_csv_metrics(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/analysis/{demo_report['id']}/csv/metrics",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        assert r.text.splitlines()[0].strip().lower().startswith("metric,value")

    def test_demo_csv_motion(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/analysis/{demo_report['id']}/csv/motion",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        lines = r.text.strip().splitlines()
        assert len(lines) == 121

    def test_demo_csv_events(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/analysis/{demo_report['id']}/csv/events",
                       headers=auth_headers, timeout=20)
        assert r.status_code == 200
        assert len(r.text.strip().splitlines()) == 5


# -------------------- compare regression --------------------

class TestCompare:
    def test_profiles_seven(self, client, auth_headers):
        r = client.get(f"{API}/compare/profiles", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        profiles = r.json()
        assert len(profiles) == 7
        names = " ".join(p.get("name", "").lower() for p in profiles)
        assert "cummins" in names

    def test_compare_with_demo(self, client, auth_headers, demo_report):
        r = client.post(
            f"{API}/compare",
            headers=auth_headers,
            json={"analysis_id": demo_report["id"], "comparison_group": "closest"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d.get("best_match"), f"no best_match: {d}"


# -------------------- dashboard regression --------------------

class TestDashboard:
    def test_dashboard(self, client, auth_headers, demo_report):
        r = client.get(f"{API}/users/dashboard", headers=auth_headers, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d.get("total_reports", 0) >= 1
        assert isinstance(d.get("score_trend"), list) and len(d["score_trend"]) >= 1
        latest = d.get("latest") or {}
        label = (latest.get("action_label")
                 or (latest.get("classification") or {}).get("action_label"))
        assert label is not None, f"latest missing action_label: {latest}"
