"""
Realistic production example: Flask REST API with Pydantic validation.

This simulates a typical backend microservice with:
- Flask for HTTP routing
- Pydantic for request/response validation
- JSON serialisation
"""

from flask import Flask, jsonify, request
from pydantic import BaseModel, ValidationError
from typing import Optional
import json
import uuid
from datetime import datetime

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    name: str
    email: str
    age: Optional[int] = None

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    age: Optional[int] = None
    created_at: str

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = Flask(__name__)
_users: dict[str, dict] = {}

@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})

@app.route("/users", methods=["POST"])
def create_user():
    try:
        user = UserCreate(**request.get_json())
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 422

    user_id = str(uuid.uuid4())
    record = {
        "id": user_id,
        "name": user.name,
        "email": user.email,
        "age": user.age,
        "created_at": datetime.utcnow().isoformat(),
    }
    _users[user_id] = record
    return jsonify(UserResponse(**record).model_dump()), 201

@app.route("/users/<user_id>")
def get_user(user_id: str):
    if user_id not in _users:
        return jsonify({"error": "Not found"}), 404
    return jsonify(_users[user_id])

@app.route("/users")
def list_users():
    return jsonify(list(_users.values()))

# ---------------------------------------------------------------------------
# We don't actually start the server — just defining the app is enough
# for envcore to trace all the imports.
# ---------------------------------------------------------------------------

print(f"Flask app created with {len(app.url_map._rules)} routes")
print("Models validated OK:")
test_user = UserCreate(name="Alice", email="alice@example.com", age=30)
print(f"  → {test_user.model_dump()}")
