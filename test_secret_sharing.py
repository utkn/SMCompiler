"""
Unit tests for the secret sharing scheme.
Testing secret sharing is not obligatory.

MODIFY THIS FILE.
"""


import itertools

from secret_sharing import reconstruct_secret, share_secret, default_q, ScalarElement

secrets = [0, 1, 4, 88, 92, 99, 123, 128, 999, 81923, 788723, 230987032]
num_parties = [2, 3, 4, 8, 16, 32, 64, 67]


def test_secret_sharing_reconstruction():
    for secret, N in itertools.product(secrets, num_parties):
        secret = secret % default_q
        print(f"test_secret_sharing_reconstruction: Testing for s = {secret}, N = {N}")
        shares = share_secret(secret, N)
        assert len(shares) == N
        for i in range(N):
            assert shares[i].index == i
        assert reconstruct_secret(shares) == secret


def test_secret_sharing_addition():
    for (s1, s2), N in itertools.product(itertools.product(secrets, secrets), num_parties):
        s1 = s1 % default_q
        s2 = s2 % default_q
        print(f"test_secret_sharing_addition: Testing for s1 = {s1}, s2 = {s2}, N = {N}")
        # Test for share + share
        shares1 = share_secret(s1, N)
        shares2 = share_secret(s2, N)
        result = []
        for i in range(N):
            r1 = shares1[i] + shares2[i]
            r2 =  shares2[i] + shares1[i]
            assert r1.value == r2.value
            result.append(r1)
        assert reconstruct_secret(result) == (s1 + s2) % default_q
        # Test for share + scalar
        result = []
        for i in range(N):
            r1 = shares1[i] + ScalarElement(s2)
            r2 = ScalarElement(s2) + shares1[i]
            assert r1.value == r2.value
            result.append(r1)
        assert reconstruct_secret(result) == (s1 + s2) % default_q


def test_secret_sharing_subtraction():
    for (s1, s2), N in itertools.product(itertools.product(secrets, secrets), num_parties):
        s1 = s1 % default_q
        s2 = s2 % default_q
        print(f"test_secret_sharing_subtraction: Testing for s1 = {s1}, s2 = {s2}, N = {N}")
        # Test for share - share
        shares1 = share_secret(s1, N)
        shares2 = share_secret(s2, N)
        result = []
        for i in range(N):
            result.append(shares1[i] - shares2[i])
        assert reconstruct_secret(result) == (s1 - s2) % default_q
        # Test for share - scalar
        result = []
        for i in range(N):
            r1 = shares1[i] - ScalarElement(s2)
            r2 = ScalarElement(-s2) + shares1[i]
            assert r1.value == r2.value
            result.append(r1)
        assert reconstruct_secret(result) == (s1 - s2) % default_q


def test_secret_sharing_multiplication():
    for (s1, s2), N in itertools.product(itertools.product(secrets, secrets), num_parties):
        s1 = s1 % default_q
        s2 = s2 % default_q
        print(f"test_secret_sharing_multiplication: Testing for s1 = {s1}, s2 = {s2}, N = {N}")
        # Test for scalar * share
        shares1 = share_secret(s1, N)
        result = []
        for i in range(N):
            r1 = shares1[i] * ScalarElement(s2)
            r2 = ScalarElement(s2) * shares1[i]
            assert r1.value == r2.value
            result.append(r1)
        assert reconstruct_secret(result) == (s1 * s2) % default_q


if __name__ == "__main__":
    test_secret_sharing_reconstruction()
    test_secret_sharing_addition()
    test_secret_sharing_subtraction()
    test_secret_sharing_multiplication()