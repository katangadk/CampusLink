"""Authentication primitives; no plaintext session or recovery tokens in the database."""
import hashlib
import hmac
import re
import secrets
from datetime import date, datetime
from zoneinfo import ZoneInfo

USERNAME = re.compile(r'^[a-z0-9_]{3,24}$')


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f'scrypt${salt.hex()}${digest.hex()}'


def check_password(password: str, encoded: str) -> bool:
    try:
        _, salt, expected = encoded.split('$')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def age(dob: str | None) -> int:
    if not dob:
        return 0
    born = date.fromisoformat(dob)
    today = datetime.now(ZoneInfo('Africa/Lusaka')).date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


class LocalEligibility:
    """Replace this adapter with a reviewed eligibility provider before public launch.

    Local/staging test accounts are NEVER verified students or verified adults. Adult access
    is assigned by explicit fixtures or the separate local test declaration flow.
    A birth-date update by itself never grants this flag. Hosted visitors open
    the website directly; private features require individual account sessions.
    A production eligibility provider is not configured.
    """
    def student(self, user):
        return bool(user['local_test'])

    def adult(self, user):
        return self.student(user) and bool(user['adult_test']) and age(user['dob']) >= 18
