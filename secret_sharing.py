"""
Secret sharing scheme.
"""

import random
from abc import ABC
from typing import List, Tuple, Any, Callable

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


class BeaverDistributor:
    def __init__(self,
                 labels: Tuple[str, str, str],
                 triplet_retriever: Callable[[str], Tuple[int, int, int]],
                 blinded_share_publisher: Callable[[Share, str], None],
                 blinded_value_retriever: Callable[[str], List[Share]]):
        # Assign the labels.
        self.retrieve_triplet_label, self.X_label, self.Y_label = labels
        # Assign the calls.
        self.triplet_retriever = triplet_retriever
        self.blinded_share_publisher = blinded_share_publisher
        self.blinded_value_retriever = blinded_value_retriever

    def retrieve_triplet_shares(self, participant_index: int) -> Tuple[Share, Share, Share]:
        a, b, c = self.triplet_retriever(self.retrieve_triplet_label)
        return Share(participant_index, a), Share(participant_index, b), Share(participant_index, c)

    def publish_blinded_shares(self, X_share: Share, Y_share: Share):
        self.blinded_share_publisher(X_share, self.X_label)
        self.blinded_share_publisher(Y_share, self.Y_label)

    def receive_blinded_values(self) -> Tuple[ScalarElement, ScalarElement]:
        X_result_shares = self.blinded_value_retriever(self.X_label)
        Y_result_shares = self.blinded_value_retriever(self.Y_label)
        X = ScalarElement(reconstruct_secret(X_result_shares))
        Y = ScalarElement(reconstruct_secret(Y_result_shares))
        return X, Y

    def execute_start(self, x: Share, y: Share) -> Tuple[Share, Share, Share]:
        # Receive the Beaver triplet.
        a, b, c = self.retrieve_triplet_shares(x.index)
        assert x.index == y.index and x.index == a.index and a.index == b.index and b.index == c.index
        # Blind the [x] and [y] by [x - a], [y - b]
        X_share = x - a
        Y_share = y - b
        assert isinstance(X_share, Share) and isinstance(Y_share, Share)
        # Publicize our blinded shares.
        self.publish_blinded_shares(X_share, Y_share)
        # Return the intermediate state.
        return c, x, y

    def execute_end(self, state) -> Share:
        c, x, y = state
        # Receive the blinded X = (x - a) and Y = (y - a).
        X, Y = self.receive_blinded_values()
        # [z] = [c] + [x] * (y - b) + [y] * (x - a) - X * Y
        result = c + x * Y + y * X - X * Y
        return result

    def execute(self, x: Share, y: Share) -> Share:
        state = self.execute_start(x, y)
        return self.execute_end(state)
