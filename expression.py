"""
Tools for building arithmetic expressions to execute with SMC.

Example expression:
>>> alice_secret = Secret()
>>> bob_secret = Secret()
>>> expr = alice_secret * bob_secret * Scalar(2)

MODIFY THIS FILE.
"""

import base64
from abc import ABC
from enum import Enum
import random
from typing import Optional

ID_BYTES = 4


class ExprType(Enum):
    ADD = 1
    SUB = 2
    MUL = 3
    SCALAR = 4
    SECRET = 5


def gen_id() -> bytes:
    id_bytes = bytearray(
        random.getrandbits(8) for _ in range(ID_BYTES)
    )
    return base64.b64encode(id_bytes)


class Expression(ABC):
    """
    Base class for an arithmetic expression.
    """

    def __init__(self, type: ExprType, id: Optional[bytes] = None):
        # If ID is not given, then generate one.
        if id is None:
            id = gen_id()
        self.id = id
        self.type = type

    def __add__(self, other):
        return AddOp(self, other)

    def __sub__(self, other):
        return SubOp(self, other)

    def __mul__(self, other):
        return MulOp(self, other)

    def __hash__(self):
        return hash(self.id)

    def prec(self) -> int:
        """Returns the precedence of the expression."""
        if self.type == ExprType.MUL:
            return 2
        elif self.type == ExprType.ADD:
            return 1
        elif self.type == ExprType.SUB:
            return 1
        return 3

    def is_term(self) -> bool:
        """Returns true iff the expression is a term."""
        return self.type == ExprType.SECRET or self.type == ExprType.SCALAR

    def child_repr(self, child) -> str:
        """Returns a correct representation of the given child expression, wrapping with parentheses if necessary."""
        child_str = repr(child)
        if child.prec() < self.prec():
            return f"({child_str})"
        return child_str


class SubOp(Expression):
    """
    Represents a subtraction operation.
    """

    def __init__(self, left: Expression, right: Expression, id: Optional[bytes] = None):
        self.left = left
        self.right = right
        super().__init__(ExprType.SUB, id)

    def __repr__(self):
        return f"{self.child_repr(self.left)} - {self.child_repr(self.right)}"


class AddOp(Expression):
    """
    Represents an addition operation.
    """

    def __init__(self, left: Expression, right: Expression, id: Optional[bytes] = None):
        self.left = left
        self.right = right
        super().__init__(ExprType.ADD, id)

    def __repr__(self):
        return f"{self.child_repr(self.left)} + {self.child_repr(self.right)}"


class MulOp(Expression):
    """
    Represents a multiplication operation.
    """

    def __init__(self, left: Expression, right: Expression, id: Optional[bytes] = None):
        self.left = left
        self.right = right
        super().__init__(ExprType.MUL, id)

    def __repr__(self):
        return f"{self.child_repr(self.left)} * {self.child_repr(self.right)}"


class Scalar(Expression):
    """
    Term representing a scalar finite field value.
    """

    def __init__(self, value: int, id: Optional[bytes] = None):
        self.value = value
        super().__init__(ExprType.SCALAR, id)

    def __repr__(self):
        return f"Scalar({repr(self.value)})"

    def __hash__(self):
        return


class Secret(Expression):
    """
    Term representing a secret finite field value (variable).
    """

    def __init__(self, value: Optional[int] = None, id: Optional[bytes] = None):
        self.value = value
        super().__init__(ExprType.SECRET, id)

    def __repr__(self):
        return f"Secret({self.value if self.value is not None else ''})"
