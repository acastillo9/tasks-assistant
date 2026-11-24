def greet(name: str) -> str:
    if not name or not name.strip():
        raise ValueError("name required")
    return f"Hello, {name}!"
