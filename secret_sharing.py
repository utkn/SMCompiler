"""
Secret sharing scheme.
"""

import random
from abc import ABC
from typing import List, Tuple

default_q = 10337


def rand_Zq(q=default_q):
    """Returns a random element from Z_q."""
    return random.randint(0, q - 1)


class FieldElement(ABC):
    """
    An element in a finite field. Can either be a share or a scalar.
    """

    def __init__(self, value: int):
        self.value = value % default_q

    def __add__(self, other):
        """
        Performs element + element operation.
        """
        assert isinstance(other, FieldElement)
        # Scalar + scalar
        if isinstance(self, ScalarElement) and isinstance(other, ScalarElement):
            return ScalarElement(self.value + other.value)
        # Scalar + share or share + scalar
        if isinstance(self, ScalarElement) or isinstance(other, ScalarElement):
            share, scalar = reorder_elements(self, other)
            assert isinstance(share, Share)
            if share.index == 0:
                return Share(share.index, share.value + scalar.value)
            return Share(share.index, share.value)
        # Share + share
        assert isinstance(self, Share)
        assert isinstance(other, Share)
        assert self.index == other.index
        return Share(self.index, self.value + other.value)

    def __sub__(self, other):
        """
        Performs element - element operation.
        """
        assert isinstance(other, FieldElement)
        # Scalar - scalar
        if isinstance(self, ScalarElement) and isinstance(other, ScalarElement):
            return ScalarElement(self.value - other.value)
        # Share - scalar
        if isinstance(self, Share) and isinstance(other, ScalarElement):
            return ScalarElement(-other.value) + self
        # Scalar - share
        if isinstance(self, ScalarElement) and isinstance(other, Share):
            raise RuntimeError("Implicit scalar - share not defined!")
        # Share - share
        assert isinstance(self, Share)
        assert isinstance(other, Share)
        assert self.index == other.index
        return Share(self.index, self.value - other.value)

    def __mul__(self, other):
        """
        Performs element * element operation.
        """
        assert isinstance(other, FieldElement)
        # Scalar * scalar
        if isinstance(self, ScalarElement) and isinstance(other, ScalarElement):
            return ScalarElement(self.value * other.value)
        # Scalar * share or share * scalar
        if isinstance(self, ScalarElement) or isinstance(other, ScalarElement):
            share, scalar = reorder_elements(self, other)
            assert isinstance(share, Share)
            return Share(share.index, scalar.value * share.value)
        # Share * share
        assert isinstance(self, Share)
        assert isinstance(other, Share)
        assert self.index == other.index
        raise RuntimeError("Implicit share * share not allowed!")


class ScalarElement(FieldElement):
    """
    A scalar in a finite field.
    """

    def __init__(self, value: int):
        super().__init__(value)

    def __repr__(self):
        return f"Scalar({self.value})"


class Share(FieldElement):
    """
    A secret share in a finite field.
    """

    def __init__(self, index: int, value: int):
        self.index = index
        super().__init__(value)

    def __repr__(self):
        return f"Share({self.value})"


def share_secret(secret: int, num_shares: int) -> List[Share]:
    """Generate secret shares from the given secret."""
    # Calculate s_i for i \in [1, N-1]
    share_values = [rand_Zq() for _ in range(num_shares - 1)]
    # Calculate s_0 and prepend.
    share_values = [(secret - sum(share_values)) % default_q] + share_values
    # Return the shares s_0, s_1, ..., s_{N-1}
    return [Share(i, s) for i, s in enumerate(share_values)]


def reconstruct_secret(shares: List[Share]) -> int:
    """Reconstruct the secret from the given shares."""
    return sum([s.value for s in shares]) % default_q


def serialize_share(share: Share) -> bytes:
    """Converts a share to its byte representation to be sent over the wire."""
    s = f"{share.index}|{share.value}"
    return s.encode("utf-8")


def unserialize_share(b: bytes) -> Share:
    """Reconstructs a share from its byte representation received over the wire."""
    fields = b.decode("utf-8").split("|")
    return Share(int(fields[0]), int(fields[1]))


def reorder_elements(left: FieldElement, right: FieldElement) -> Tuple[FieldElement, FieldElement]:
    """Reorders two elements such that if one of them is a scalar, it is returned as the second return value."""
    return (right, left) if isinstance(left, ScalarElement) else (left, right)
