from datetime import datetime, timedelta, timezone
import os
from typing import Optional
from jose import jwt
from components.settings import settings
import hashlib
import hmac
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


"""
=====================================================
# Create JWT token
=====================================================
"""


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


"""
=====================================================
# Decode JWT token
=====================================================
"""


def decode_token(token: str):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    # exp = payload.get("exp")
    # if exp and datetime.fromtimestamp(exp, timezone.utc)
    # < datetime.now(timezone.utc):
    #     raise ValueError("Token has expired")
    return payload


"""
=====================================================
# Hash Api key
=====================================================
"""


def hash_key(api_key: str):
    secret_key = SECRET_KEY.encode()
    hashed = hmac.new(secret_key, api_key.encode(), hashlib.sha256).digest()
    return base64.b64encode(hashed).decode()


"""
=====================================================
# Verify Api key
=====================================================
"""


def verify_key(api_key: str, hashed_key: str) -> bool:
    return hash_key(api_key) == hashed_key


"""
=====================================================
# Encrypt Secret
=====================================================
"""


def encrypt_secret(secret: str) -> str:
    """Encrypts 2FA secret using AES-256 encryption."""
    iv = os.urandom(16)
    cipher = Cipher(
        algorithms.AES(base64.b64decode(SECRET_KEY)),
        modes.CBC(iv),
        backend=default_backend(),
    )
    encryptor = cipher.encryptor()

    # Pad the secret
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(secret.encode()) + padder.finalize()

    # Encrypt
    encrypted_secret = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(iv + encrypted_secret).decode()


"""
=====================================================
# Decrypt Secret
=====================================================
"""


def decrypt_secret(encrypted_secret: str) -> str:
    """Decrypts an encrypted 2FA secret."""
    encrypted_secret = base64.b64decode(encrypted_secret)
    iv = encrypted_secret[:16]
    cipher = Cipher(
        algorithms.AES(base64.b64decode(SECRET_KEY)),
        modes.CBC(iv),
        backend=default_backend(),
    )
    decryptor = cipher.decryptor()

    padded_secret = decryptor.update(
        encrypted_secret[16:]) + decryptor.finalize()

    # Unpad the secret
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    return unpadder.update(padded_secret) + unpadder.finalize()
