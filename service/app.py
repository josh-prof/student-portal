"""Microservice: student at-risk prediction (Flask)."""
import joblib
from flask import Flask, jsonify, request

app = Flask(__name__)
model = joblib.load("model.joblib")


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    return resp


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/risk")
def risk():
    data = request.get_json(silent=True) or {}
    try:
        att, marks = float(data["attendance_pct"]), float(data["average_marks"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="need numeric attendance_pct and average_marks"), 400
    if not (0 <= att <= 100 and 0 <= marks <= 100):
        return jsonify(error="values must be between 0 and 100"), 400
    p = float(model.predict_proba([[att, marks]])[0][1])
    return jsonify(attendance_pct=att, average_marks=marks,
                   risk_probability=round(p, 3), at_risk=p >= 0.5,
                   eligible_for_exam=att >= 75)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
