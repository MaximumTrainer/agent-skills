import datetime
import random

from fastapi import FastAPI, HTTPException

from app.config import MAX_UPLOAD_BYTES, REQUEST_TIMEOUT_MS

app = FastAPI()

_STORE = {}


@app.post("/activities")
def create_activity(body: dict):
    if len(body.get("payload", "")) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="too large")
    activity_id = str(random.randint(1, 10**9))
    _STORE[activity_id] = {
        "id": activity_id,
        "received_at": datetime.datetime.now().isoformat(),
        "payload": body["payload"],
    }
    return _STORE[activity_id]


@app.get("/activities/{activity_id}")
def get_activity(activity_id: str):
    return _STORE[activity_id]
