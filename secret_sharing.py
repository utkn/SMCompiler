"""
Secret sharing scheme.
"""

import random
from typing import List, Tuple

default_q = 331


def rand_Zq(q = default_q):
    return random.randint(0, q-1)

class Share:
    """
    A secret share in a finite field.
    """

    def __init__(self, index: int, value: int, is_scalar: bool = False):
        self.value = value
        self.index = index
        self.is_scalar = is_scalar


    def __repr__(self):
        # Helps with debugging.
        return f"Share({self.value})"


    def __add__(self, other):
        """
        Performs share + share operation.
        """
        assert isinstance(other, Share)
        assert not other.is_scalar or not self.is_scalar 
        left, right = reorder_shares(self, other)
        # If the right is a non-scalar, then do share + share addition.
        if not right.is_scalar:
            assert left.index == right.index
            return Share(left.index, left.value + right.value)
        # Otherwise, do share + scalar addition
        # Only do the addition if this share is the first share.
        if left.index == 0:
            return Share(left.index, left.value + right.value)
        return Share(left.index, left.value)


    def __sub__(self, other):
        """
        Performs share - share operation.
        """
        assert isinstance(other, Share)
        assert not other.is_scalar and not self.is_scalar 
        assert self.index == other.index
        return Share(self.index, self.value - other.value)


    def __mul__(self, other):
        """
        Either multiplies another share or a scalar.
        """
        assert isinstance(other, Share)
        assert not other.is_scalar or not self.is_scalar 
        left, right = reorder_shares(self, other)
        # If the right is a non-scalar, then do share * share multiplication.
        if not right.is_scalar:
            raise RuntimeError("scalar * scalar not allowed implicitly!")
        # Otherwise, do share * scalar multiplication.
        return Share(left.index, left.value * right.value)


def share_secret(secret: int, num_shares: int) -> List[Share]:
    """Generate secret shares."""
    # Calculate s_i for i \in [1, N-1]
    share_values = [rand_Zq() for _ in range(num_shares-1)]
    # Calculate s_0 and prepend.
    share_values = [(secret - sum(share_values)) % default_q] + share_values
    # Return the shares s_0, s_1, ..., s_{N-1}
    return [Share(i, s) for i, s in enumerate(share_values)]


def reconstruct_secret(shares: List[Share]) -> int:
    """Reconstruct the secret from shares."""
    return sum([s.value for s in shares]) % default_q


def serialize_share(share: Share) -> bytes:
    s = f"{share.index}|{share.value}|{1 if share.is_scalar else 0}"
    return s.encode("utf-8")


def unserialize_share(b: bytes) -> Share:
    fields = b.decode("utf-8").split("|")
    return Share(int(fields[0]), int(fields[1]), fields[2] == "1")

# Reorder the given shares such that if one of them is a scalar, it is returned as the second return value.
def reorder_shares(left_share: Share, right_share: Share) -> Tuple[Share, Share]:
    return (right_share, left_share) if left_share.is_scalar else (left_share, right_share)