"""
Unit tests for the trusted parameter generator.
Testing ttp is not obligatory.

MODIFY THIS FILE.
"""
from secret_sharing import reconstruct_secret, default_q
from ttp import TrustedParamGenerator


def test_ttp_basic():
    ttp = TrustedParamGenerator()
    ttp.add_participant("Eduardo")
    ttp.add_participant("Utkan")
    ttp.add_participant("Lady Gaga")

    a1, b1, c1 = ttp.retrieve_share("Utkan", "op1")
    a2, b2, c2 = ttp.retrieve_share("Eduardo", "op1")
    a3, b3, c3 = ttp.retrieve_share("Lady Gaga", "op1")

    a = reconstruct_secret([a1, a2, a3])
    b = reconstruct_secret([b1, b2, b3])
    c = reconstruct_secret([c1, c2, c3])

    assert (a * b) % default_q == c % default_q
