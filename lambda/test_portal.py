import json
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ.update(TABLE_NAME="t", BUCKET="b", ADMIN_KEY="secret")
sys.path.insert(0, os.path.dirname(__file__))
with patch("boto3.resource"), patch("boto3.client"):
    import portal


def event(method, path, body=None, key=None, roll=None):
    ev = {"requestContext": {"http": {"method": method}}, "rawPath": path,
          "headers": {"x-admin-key": key} if key else {},
          "body": json.dumps(body) if body is not None else None}
    if roll:
        ev["pathParameters"] = {"roll": roll}
    return ev


def setup_function():
    portal.table = MagicMock()
    portal.s3 = MagicMock()


def test_write_needs_admin_key():
    r = portal.handler(event("POST", "/attendance", {"roll": "ECE01", "date": "2026-10-01", "status": "present"}), None)
    assert r["statusCode"] == 401
    portal.table.put_item.assert_not_called()


def test_attendance_saved_and_audited():
    r = portal.handler(event("POST", "/attendance", {"roll": "ECE01", "date": "2026-10-01", "status": "present"}, key="secret"), None)
    assert r["statusCode"] == 200
    portal.table.put_item.assert_called_once()
    portal.s3.put_object.assert_called_once()


def test_marks_out_of_range_rejected():
    r = portal.handler(event("POST", "/results", {"roll": "ECE01", "subject": "Maths", "marks": 150}, key="secret"), None)
    assert r["statusCode"] == 400


def test_bad_roll_rejected():
    r = portal.handler(event("GET", "/students/x", roll="bad roll!"), None)
    assert r["statusCode"] == 400


def test_summary_math():
    portal.table.query.return_value = {"Items": [
        {"roll": "ECE01", "sk": "ATT#2026-10-01", "status": "present"},
        {"roll": "ECE01", "sk": "ATT#2026-10-02", "status": "absent"},
        {"roll": "ECE01", "sk": "RES#Maths", "marks": Decimal(80)},
        {"roll": "ECE01", "sk": "RES#Physics", "marks": Decimal(60)},
    ]}
    body = json.loads(portal.handler(event("GET", "/students/ECE01", roll="ECE01"), None)["body"])
    assert body["attendance_pct"] == 50.0
    assert body["average_marks"] == 70.0
    assert body["grade"] == "B"
    assert body["eligible_for_exam"] is False
