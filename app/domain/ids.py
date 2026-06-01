"""UUIDv7 generation — time-ordered IDs (RFC 9562).

stdlib `uuid.uuid7` only lands in Python 3.14, so we build it by hand here:
48-bit unix_ts_ms | 4-bit version(7) | 12-bit rand_a | 2-bit variant(10) | 62-bit rand_b.
Time-ordered => B-tree-friendly inserts; random tail => no collisions, no count leak.
"""

import secrets
import time
import uuid


def new_uuid7() -> uuid.UUID:
    unix_ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (
        (unix_ts_ms << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0b10 << 62)
        | rand_b
    )
    return uuid.UUID(int=value)
