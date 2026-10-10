"""Load demo data. Usage: python seed_data.py <API_URL> <ADMIN_KEY>"""
import random
import sys
from datetime import date, timedelta

import requests

api, key = sys.argv[1].rstrip("/"), sys.argv[2]
headers = {"x-admin-key": key, "Content-Type": "application/json"}
random.seed(1)

students = {"ECE01": 0.95, "ECE02": 0.80, "ECE03": 0.55}   # attendance probability
marks = {"ECE01": 82, "ECE02": 66, "ECE03": 38}
subjects = ["Maths", "Signals", "Python", "Electronics"]

for roll, p in students.items():
    for d in range(20):
        day = (date.today() - timedelta(days=d)).isoformat()
        status = "present" if random.random() < p else "absent"
        requests.post(api + "/attendance", headers=headers,
                      json={"roll": roll, "date": day, "status": status}, timeout=10)
    for sub in subjects:
        m = max(0, min(100, marks[roll] + random.randint(-8, 8)))
        requests.post(api + "/results", headers=headers,
                      json={"roll": roll, "subject": sub, "marks": m}, timeout=10)
    print("seeded", roll)
