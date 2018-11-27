
from django.conf import settings

import hashlib
import base64

from typing import Optional


def initial_password(email: str) -> Optional[str]:
    """Given an email address, returns the initial password for that account, as
       created by populate_db."""

    if settings.INITIAL_PASSWORD_SALT is not None:
        encoded_key = (settings.INITIAL_PASSWORD_SALT + email).encode("utf-8")
        digest = hashlib.sha256(encoded_key).digest()
        return base64.b64encode(digest)[:16].decode('utf-8')
    else:
        # None as a password for a user tells Django to set an unusable password
        return None
