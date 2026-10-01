from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password_hash(password: str, hash_password: str) -> bool:
    return password_hash.verify(password, hash_password)
