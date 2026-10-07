from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.encryption_key.encode())


def encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()
