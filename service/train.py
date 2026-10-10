"""Train a small at-risk model: attendance % + average marks -> probability."""
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

rng = np.random.default_rng(42)
n = 3000
attendance = rng.uniform(40, 100, n)
marks = np.clip(rng.normal(65, 18, n), 0, 100)
score = 0.5 * (75 - attendance) + 0.5 * (60 - marks) + rng.normal(0, 5, n)
y = (score > 0).astype(int)

model = make_pipeline(StandardScaler(), LogisticRegression())
model.fit(np.column_stack([attendance, marks]), y)
print("training accuracy:", round(model.score(np.column_stack([attendance, marks]), y), 3))
joblib.dump(model, "model.joblib")
