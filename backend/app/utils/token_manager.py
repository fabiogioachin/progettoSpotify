from cryptography.fernet import Fernet

from app.config import settings


_fernet = Fernet(settings.encryption_key)


def encrypt_token(token: str) -> str:
    return _fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()
