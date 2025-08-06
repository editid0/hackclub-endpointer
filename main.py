from fastapi import FastAPI
from uuid import uuid4
import sqlite3, os, time, typing, re

app = FastAPI()
if not os.path.exists("data.db"):
    with open("data.db", "w") as f:
        pass
conn = sqlite3.connect("data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS api_keys (key TEXT PRIMARY KEY)""")
cursor.execute(
    """CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, name TEXT, meta TEXT, owner TEXT)"""
)
conn.commit()


@app.post("/key")
def generate_api_key() -> dict[str, str]:
    """This endpoint gives you an API key you can use to access the application."""
    api_key = str(uuid4())
    # add the api key to the database
    cursor.execute("INSERT INTO api_keys (key) VALUES (?)", (api_key,))
    conn.commit()
    return {"api_key": api_key}


@app.get("/key")
def validate_api_key(api_key: str) -> dict[str, bool]:
    """This endpoint checks if the API key is valid."""
    cursor.execute("SELECT * FROM api_keys WHERE key = ?", (api_key,))
    result = cursor.fetchone()
    time.sleep(0.5)  # i added this time to make it so you can't brute force api keys
    if result:
        return {"valid": True}
    else:
        return {"valid": False}


@app.post("/users")
def create_user(name: str, meta: dict[str, typing.Any] = {}) -> dict[str, str]:
    """This endpoint creates a user with a name and optional metadata."""
    user_id = str(uuid4())
    metadata_s = ""
    for k, v in meta.items():
        k = re.sub(r"""[^a-zA-Z0-9!?:,'" ]""", "", k)
        v = re.sub(r"""[^a-zA-Z0-9!?:,'" ]""", "", str(v))
        metadata_s += f"{k}={v};"
    cursor.execute(
        "INSERT INTO users (user_id, name, meta, owner) VALUES (?, ?, ?, ?)",
        (user_id, name, metadata_s, "owner_placeholder"),
    )
    conn.commit()
    return {"user_id": user_id}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: typing.Union[str, None] = None):
    return {"item_id": item_id, "q": q}
