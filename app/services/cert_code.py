import random
import string


def generate_cert_code(length: int = 12) -> str:
    """
    Generate a human-readable cert code like XXXX-XXXX-XXXX
    using uppercase letters and digits, avoiding ambiguous chars (0, O, I, 1).
    """
    charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(random.choices(charset, k=length))
    # Split into groups of 4
    return "-".join(raw[i : i + 4] for i in range(0, length, 4))
