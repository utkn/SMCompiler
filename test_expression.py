"""
Unit tests for expressions.
Testing expressions is not obligatory.

MODIFY THIS FILE.
"""

from expression import Secret, Scalar


def test_expr_construction():
    a = Secret(1)
    b = Secret(2)
    c = Secret(3)
    assert repr(a + b) == "Secret(1) + Secret(2)"
    assert repr(b * a) == "Secret(2) * Secret(1)"
    assert repr(a * b * c) == "Secret(1) * Secret(2) * Secret(3)"
    assert repr(a * (b + c * Scalar(4))) == "Secret(1) * (Secret(2) + Secret(3) * Scalar(4))"
    assert repr((a + b) * c * Scalar(4) + Scalar(3)) == "(Secret(1) + Secret(2)) * Secret(3) * Scalar(4) + Scalar(3)"


if __name__ == "__main__":
    test_expr_construction()

