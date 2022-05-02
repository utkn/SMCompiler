"""
Secret sharing scheme.
"""

import random
from typing import List

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
        Either adds another share or a scalar.
        """
        assert isinstance(other, Share)
        # If the other is a non-scalar, then do share + share addition.
        if not other.is_scalar:
            assert self.index == other.index
            return Share(self.index, self.value + other.value)
        # Otherwise, do share + scalar addition
        # Only do the addition if this share is the first share.
        if self.index == 0:
            return Share(self.index, self.value + other.value)
        return Share(self.index, self.value)


    def __sub__(self, other):
        """
        Either subtracts another share or a scalar.
        """
        assert isinstance(other, Share)
        # If the other is a non-scalar, then do share - share subtraction.
        if not other.is_scalar:
            assert self.index == other.index
            return Share(self.index, self.value - other.value)
        raise RuntimeError("scalar - share is not allowed!")


    def __mul__(self, other):
        """
        Either multiplies another share or a scalar.
        """
        assert isinstance(other, Share)
        # If the other is a non-scalar, then do share * share multiplication.
        if not other.is_scalar:
            assert self.index == other.index
            raise NotImplementedError("You need to implement this method.")
        # Otherwise, do share * scalar multiplication.
        return Share(self.index, self.value * other.value)


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