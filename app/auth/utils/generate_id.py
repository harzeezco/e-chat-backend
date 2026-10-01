import secrets


def generate_id(count: int) -> str:
    return secrets.token_hex(count)
