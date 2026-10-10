import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import app  # noqa: E402

client = app.test_client()


def test_health():
    assert client.get("/health").json["status"] == "ok"


def test_struggling_student_is_at_risk():
    r = client.post("/risk", json={"attendance_pct": 50, "average_marks": 35})
    assert r.json["at_risk"] is True and r.json["eligible_for_exam"] is False


def test_strong_student_is_safe():
    r = client.post("/risk", json={"attendance_pct": 95, "average_marks": 85})
    assert r.json["at_risk"] is False and r.json["eligible_for_exam"] is True


def test_bad_input():
    assert client.post("/risk", json={"x": 1}).status_code == 400
    assert client.post("/risk", json={"attendance_pct": 120, "average_marks": 50}).status_code == 400
