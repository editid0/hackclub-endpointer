from fastapi import FastAPI, Request
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


def get_headers(request: Request) -> dict[str, str]:
    """Get the headers from the request."""
    headers = {}
    for key, value in request.headers.items():
        headers[key] = value
    return headers


def get_key(request: Request) -> str:
    """Get the API key from the request headers."""
    return request.headers.get("X-API-Key", "")


@app.post("/key")
def generate_api_key() -> dict[str, str]:
    """This endpoint gives you an API key you can use to access the application."""
    api_key = str(uuid4())
    # add the api key to the database
    cursor.execute("INSERT INTO api_keys (key) VALUES (?)", (api_key,))
    conn.commit()
    return {"api_key": api_key}


def validate_key(api_key: str) -> bool:
    """Check if the API key is valid."""
    cursor.execute("SELECT * FROM api_keys WHERE key = ?", (api_key,))
    result = cursor.fetchone()
    return result is not None


@app.get("/key")
def validate_api_key(api_key: str) -> dict[str, bool]:
    """This endpoint checks if the API key is valid."""
    is_valid = validate_api_key(api_key)
    time.sleep(0.5)  # i added this time to make it so you can't brute force api keys
    if is_valid:
        return {"valid": True}
    else:
        return {"valid": False}


@app.post("/users")
def create_user(
    name: str,
    request: Request,
    meta: str = "",
) -> typing.Union[dict[str, str], tuple[dict[str, str], int]]:
    """This endpoint creates a user with a name and optional metadata."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    user_id = str(uuid4())
    metadata_s = ""
    metadata: typing.List[str] = meta.split(";")
    for item in metadata:
        if item.strip():
            k, v = item.split("=", 1) if "=" in item else (item, "")
            k = re.sub(r"""[^a-zA-Z0-9!?:,'" ]""", "", k)
            v = re.sub(r"""[^a-zA-Z0-9!?:,'" ]""", "", v)
            metadata_s += f"{k}={v};"
    metadata_s = metadata_s.rstrip(";")
    if len(metadata_s) > 1000:
        return {"error": "Metadata too long, must be less than 1000 characters"}, 400
    if len(name) > 100:
        return {"error": "Name too long, must be less than 100 characters"}, 400
    cursor.execute(
        "INSERT INTO users (user_id, name, meta, owner) VALUES (?, ?, ?, ?)",
        (user_id, name, metadata_s, api_key),
    )
    conn.commit()
    return {"user_id": user_id}


@app.get("/users")
def get_users(
    request: Request,
) -> typing.Union[typing.List[dict[str, typing.Any]], tuple[dict[str, str], int]]:
    """This endpoint returns a list of users."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    cursor.execute("SELECT * FROM users WHERE owner = ?", (api_key,))
    users = cursor.fetchall()
    return [{"user_id": user[0], "name": user[1], "meta": user[2]} for user in users]


@app.get("/items/{item_id}")
def read_item(item_id: int, q: typing.Union[str, None] = None):
    return {"item_id": item_id, "q": q}
