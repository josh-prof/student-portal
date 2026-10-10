"""Serverless API for the Student Result and Attendance Portal.

Routes (API Gateway HTTP API -> this Lambda):
  POST /attendance        admin only   {roll, date, status}
  POST /results           admin only   {roll, subject, marks}
  GET  /students/{roll}   public       attendance %, marks, grade
"""
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
table = dynamodb.Table(os.environ.get("TABLE_NAME", ""))
BUCKET = os.environ.get("BUCKET", "")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")

ROLL_RE = re.compile(r"[A-Za-z0-9_-]{1,20}")


def _num(o):
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError


def _resp(code, body):
    return {"statusCode": code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, default=_num)}


def grade(avg):
    for cutoff, g in ((90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D")):
        if avg >= cutoff:
            return g
    return "F"


def _is_admin(event):
    key = (event.get("headers") or {}).get("x-admin-key", "")
    return bool(ADMIN_KEY) and hmac.compare_digest(key.encode(), ADMIN_KEY.encode())


def _audit(action, item):
    now = datetime.now(timezone.utc)
    record = {"action": action, "item": item, "at": now.isoformat()}
    s3.put_object(Bucket=BUCKET,
                  Key=f"audit/{now:%Y-%m-%d}/{uuid.uuid4()}.json",
                  Body=json.dumps(record, default=_num))


def summary(roll):
    items = table.query(KeyConditionExpression=Key("roll").eq(roll))["Items"]
    att = [i for i in items if i["sk"].startswith("ATT#")]
    res = [i for i in items if i["sk"].startswith("RES#")]
    present = sum(1 for i in att if i["status"] == "present")
    pct = round(100 * present / len(att), 1) if att else None
    avg = round(float(sum(i["marks"] for i in res)) / len(res), 1) if res else None
    return {
        "roll": roll,
        "classes_held": len(att),
        "classes_attended": present,
        "attendance_pct": pct,
        "eligible_for_exam": (pct >= 75) if pct is not None else None,
        "results": {i["sk"][4:]: i["marks"] for i in res},
        "average_marks": avg,
        "grade": grade(avg) if avg is not None else None,
    }


def _save_attendance(data):
    roll, date, status = str(data.get("roll", "")), str(data.get("date", "")), data.get("status")
    if not ROLL_RE.fullmatch(roll) or status not in ("present", "absent"):
        return _resp(400, {"error": "need valid roll, date, status (present/absent)"})
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return _resp(400, {"error": "date must be YYYY-MM-DD"})
    item = {"roll": roll, "sk": f"ATT#{date}", "status": status}
    table.put_item(Item=item)
    _audit("attendance", item)
    return _resp(200, {"status": "saved", "item": item})


def _save_result(data):
    roll, subject, marks = str(data.get("roll", "")), str(data.get("subject", "")).strip(), data.get("marks")
    ok_marks = isinstance(marks, (int, Decimal)) and not isinstance(marks, bool) and 0 <= marks <= 100
    if not ROLL_RE.fullmatch(roll) or not (1 <= len(subject) <= 40) or not ok_marks:
        return _resp(400, {"error": "need valid roll, subject and marks between 0 and 100"})
    item = {"roll": roll, "sk": f"RES#{subject}", "marks": marks}
    table.put_item(Item=item)
    _audit("result", item)
    return _resp(200, {"status": "saved", "item": item})


def handler(event, context):
    method = event["requestContext"]["http"]["method"]
    path = event["rawPath"]

    if method == "GET" and path.startswith("/students/"):
        roll = (event.get("pathParameters") or {}).get("roll", "")
        if not ROLL_RE.fullmatch(roll):
            return _resp(400, {"error": "invalid roll number"})
        return _resp(200, summary(roll))

    if method == "POST" and path in ("/attendance", "/results"):
        if not _is_admin(event):
            return _resp(401, {"error": "admin key required"})
        try:
            data = json.loads(event.get("body") or "{}", parse_float=Decimal)
        except ValueError:
            return _resp(400, {"error": "body must be JSON"})
        if not isinstance(data, dict):
            return _resp(400, {"error": "body must be a JSON object"})
        return _save_attendance(data) if path == "/attendance" else _save_result(data)

    return _resp(404, {"error": "not found"})
