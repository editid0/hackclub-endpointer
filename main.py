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
cursor.execute(
    """CREATE TABLE IF NOT EXISTS balances(api_key TEXT, user_id TEXT, balance INTEGER, balance_id TEXT PRIMARY KEY)"""
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


@app.post(
    "/key",
    summary="Generate API key",
    description="This endpoint generates an API key for you to use.",
)
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


@app.get(
    "/key",
    summary="Validate API key",
    description="This endpoint checks if the API key is valid.",
)
def validate_api_key(api_key: str) -> dict[str, bool]:
    """This endpoint checks if the API key is valid."""
    is_valid = validate_key(api_key)
    time.sleep(0.5)  # i added this time to make it so you can't brute force api keys
    if is_valid:
        return {"valid": True}
    else:
        return {"valid": False}


@app.post(
    "/users",
    summary="Create a user",
    description="This endpoint creates a user with a name and optional metadata.",
)
def create_a_user(
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


@app.get(
    "/users",
    summary="Get all user's from your API key",
    description="This endpoint returns all users associated with the API key.",
)
def get_all_users_from_key(
    request: Request,
) -> typing.Union[typing.List[dict[str, typing.Any]], tuple[dict[str, str], int]]:
    """This endpoint returns a list of users."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    cursor.execute("SELECT * FROM users WHERE owner = ?", (api_key,))
    users = cursor.fetchall()
    return [{"user_id": user[0], "name": user[1], "meta": user[2]} for user in users]


@app.get(
    "/users/{user_id}",
    summary="Get a specific user by user id",
    description="This endpoint returns a user from a user id.",
)
def get_specific_user(
    user_id: str, request: Request
) -> typing.Union[dict[str, typing.Any], tuple[dict[str, str], int]]:
    """This endpoint returns a user by user_id."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    cursor.execute(
        "SELECT * FROM users WHERE user_id = ? AND owner = ?", (user_id, api_key)
    )
    user = cursor.fetchone()
    if user is None:
        return {"error": "User not found"}, 404
    return {"user_id": user[0], "name": user[1], "meta": user[2]}


@app.put(
    "/users/{user_id}",
    summary="Update a user's name or metadata",
    description="This endpoint updates a user's name or meta, if you only want to update one, don't pass the other one, if you want both, pass both.",
)
def update_a_user(
    user_id: str,
    request: Request,
    name: typing.Optional[str] = None,
    meta: str = "",
) -> typing.Union[dict[str, str], tuple[dict[str, str], int]]:
    """This endpoint updates a user's name or meta."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    if meta:
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
            return {
                "error": "Metadata too long, must be less than 1000 characters"
            }, 400
    if name:
        if len(name) > 100:
            return {"error": "Name too long, must be less than 100 characters"}, 400
    if meta and not name:
        cursor.execute(
            "UPDATE users SET meta = ? WHERE user_id = ? AND owner = ?",
            (metadata_s, user_id, api_key),
        )
    elif name and not meta:
        cursor.execute(
            "UPDATE users SET name = ? WHERE user_id = ? AND owner = ?",
            (name, user_id, api_key),
        )
    elif name and meta:
        if len(name) > 100:
            return {"error": "Name too long, must be less than 100 characters"}, 400
        if len(metadata_s) > 1000:
            return {
                "error": "Metadata too long, must be less than 1000 characters"
            }, 400
        cursor.execute(
            "UPDATE users SET name = ?, meta = ? WHERE user_id = ? AND owner = ?",
            (name, metadata_s, user_id, api_key),
        )
    conn.commit()
    if cursor.rowcount == 0:
        return {"error": "User not found"}, 404
    return {"message": "User updated successfully"}


@app.delete(
    "/users/{user_id}",
    summary="Delete a user",
    description="This endpoint deletes a user by user id.",
)
def delete_a_user(
    user_id: str, request: Request
) -> typing.Union[dict[str, str], tuple[dict[str, str], int]]:
    """This endpoint deletes a user by user_id."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    cursor.execute(
        "DELETE FROM users WHERE user_id = ? AND owner = ?",
        (user_id, api_key),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return {"error": "User not found"}, 404
    return {"message": "User deleted successfully"}


@app.get(
    "/balances",
    summary="Get all balances",
    description="This endpoint returns all balances for the user associated with the API key.",
)
def get_api_key_balances(
    request: Request,
) -> typing.Union[list[dict[str, typing.Union[str, int]]], tuple[dict[str, str], int]]:
    """This endpoint returns who owes who money, so if bob owes you like £50, it'll show bob £50, if you owe bob £40, it'll show bob -£40, if both, it'll show both transactions."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    cursor.execute("SELECT * FROM balances WHERE api_key = ?", (api_key,))
    balances = cursor.fetchall()
    return [
        {"user_id": balance[1], "balance": balance[2], "balance_id": balance[3]}
        for balance in balances
    ]


@app.post(
    "/balances",
    summary="Add a balance for a user",
    description="This endpoint adds a balance for a user, this is basically a transaction.",
)
def add_a_balance(
    user_id: str,
    balance: int,
    request: Request,
) -> typing.Union[dict[str, str], tuple[dict[str, str], int]]:
    """This endpoint adds a balance for a user."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    balance_id = str(uuid4())
    cursor.execute(
        "INSERT INTO balances (api_key, user_id, balance, balance_id) VALUES (?, ?, ?, ?)",
        (api_key, user_id, balance, balance_id),
    )
    conn.commit()
    return {"message": "Balance added successfully", "balance_id": balance_id}


@app.get(
    "/balances/{balance_id}",
    summary="Get a specific balance by it's ID",
    description="This endpoint returns a balance from the balance ID, which you can get from /balances.",
)
def get_a_balance(
    balance_id: str, request: Request
) -> typing.Union[dict[str, typing.Any], tuple[dict[str, str], int]]:
    """This endpoint returns a balance from the balance id."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    cursor.execute(
        "SELECT * FROM balances WHERE balance_id = ? AND api_key = ?",
        (balance_id, api_key),
    )
    balance = cursor.fetchone()
    if balance is None:
        return {"error": "Balance not found"}, 404
    return {"user_id": balance[1], "balance": balance[2], "balance_id": balance[3]}


@app.delete(
    "/balances/{balance_id}",
    summary="Delete a user's balance",
    description="This endpoint deletes a balance from the balance id, which you can get from /balances.",
)
def delete_a_balance(
    balance_id: str, request: Request
) -> typing.Union[dict[str, str], tuple[dict[str, str], int]]:
    """This endpoint deletes a balance from the balance id."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    cursor.execute(
        "DELETE FROM balances WHERE balance_id = ? AND api_key = ?",
        (balance_id, api_key),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return {"error": "Balance not found"}, 404
    return {"message": "Balance deleted successfully"}


@app.put(
    "/balances/{balance_id}",
    summary="Update a user's balance",
    description="This endpoint updates a user's balance, you can only update the balance, not the user_id or balance_id.",
)
def update_a_balance(
    balance_id: str, new_balance: int, request: Request
) -> typing.Union[dict[str, str], tuple[dict[str, str], int]]:
    """This endpoint updates a user's balance."""
    api_key = get_key(request)
    if not validate_key(api_key):
        return {"error": "Invalid API key"}, 401
    cursor.execute(
        "UPDATE balances SET balance = ? WHERE balance_id = ? AND api_key = ?",
        (new_balance, balance_id, api_key),
    )
    conn.commit()
    if cursor.rowcount == 0:
        return {"error": "Balance not found"}, 404
    return {"message": "Balance updated successfully"}
