from passlib.context import CryptContext
from passlib.exc import UnknownHashError

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

"""
=====================================================
# Description:
    - This file is used to hash the password using bcrypt
    - It also has a function to verify the password
=====================================================
"""


def verify_password(plain_password, hashed_password):
    """
    Safely verify a plain password against a stored hash.

    Returns False for missing/empty/invalid hashes instead of raising.
    """
    if not hashed_password:
        return False

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except UnknownHashError:
        # The stored hash is in an unknown/unsupported format.
        # Avoid raising; treat as authentication failure and return False.
        return False
    except Exception:
        # Any other error during verification should be treated as failure.
        return False


def get_password_hash(password):
    return pwd_context.hash(password)