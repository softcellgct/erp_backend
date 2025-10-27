# 🔥 Ensure data is converted to dictionaries before passing to ORM
from typing import Optional
import uuid
from fastapi import Request

"""
=====================================================
#  Get User ID from Request
=====================================================
"""


async def get_user_id(req: Request) -> Optional[uuid.UUID]:
    # Assuming the user ID is stored in the request state
    return req.state.user.id if hasattr(req.state, "user") else None


"""
=====================================================
#  Get user given key from Request
=====================================================
"""


async def get_user_from_request(req: Request, key: str):
    """
    Retrieve a user attribute from the request state, supporting nested keys separated by dots.

    Args:
        req (Request): The FastAPI request object.
        key (str): The key of the user attribute to retrieve, supports dot notation for nested attributes.

    Returns:
        Optional[Any]: The value of the user attribute if it exists, otherwise None.
    """
    if not hasattr(req.state, "user"):
        return None

    value = req.state.user
    for attr in key.split("."):
        if hasattr(value, attr):
            value = getattr(value, attr)
        else:
            return None
    return value