"""
Realistic production example: Data science / ML pipeline.

This simulates a typical ML workflow with:
- NumPy for numerical computation
- Pandas for data manipulation
- Scikit-learn for model training
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler
import json

# ---------------------------------------------------------------------------
# Generate synthetic dataset
# ---------------------------------------------------------------------------

print("Generating synthetic dataset...")
np.random.seed(42)
n_samples = 1000

data = pd.DataFrame({
    "feature_1": np.random.randn(n_samples),
    "feature_2": np.random.randn(n_samples) * 2,
    "feature_3": np.random.exponential(1, n_samples),
    "feature_4": np.random.uniform(-1, 1, n_samples),
})
data["target"] = (
    (data["feature_1"] + data["feature_2"] * 0.5 > 0).astype(int)
)

print(f"Dataset: {data.shape[0]} samples, {data.shape[1]} columns")
print(f"Target distribution:\n{data['target'].value_counts().to_string()}")

# ---------------------------------------------------------------------------
# Train / test split
# ---------------------------------------------------------------------------

X = data[["feature_1", "feature_2", "feature_3", "feature_4"]]
y = data["target"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y,
)

# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

print("\nTraining RandomForestClassifier...")
model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
model.fit(X_train_scaled, y_train)

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

y_pred = model.predict(X_test_scaled)
accuracy = accuracy_score(y_test, y_pred)

print(f"\nAccuracy: {accuracy:.4f}")
print(f"\nClassification Report:")
print(classification_report(y_test, y_pred))

# Feature importance
importances = dict(zip(X.columns, model.feature_importances_))
print("Feature importances:")
for name, imp in sorted(importances.items(), key=lambda x: -x[1]):
    print(f"  {name}: {imp:.4f}")

# ---------------------------------------------------------------------------
# Save results (simulated)
# ---------------------------------------------------------------------------

results = {
    "accuracy": accuracy,
    "n_estimators": 100,
    "feature_importances": {k: round(v, 4) for k, v in importances.items()},
}
print(f"\nResults: {json.dumps(results, indent=2)}")
