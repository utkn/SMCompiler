"""
Trusted parameters generator.

MODIFY THIS FILE.
"""

import collections
from typing import (
    Dict,
    List,
    Set,
    Tuple,
)

from communication import Communication
from secret_sharing import (
    rand_Zq,
    share_secret,
    default_q,
    Share,
)


class TrustedParamGenerator:
    """
    A trusted third party that generates random values for the Beaver triplet multiplication scheme.
    """

    def __init__(self):
        self.participant_ids: List[str] = []
        self.generated_shares: Dict[str, Tuple[List[Share], List[Share], List[Share]]] = dict()

    def add_participant(self, participant_id: str) -> None:
        """
        Add a participant.
        """
        # WARNING: Order must be the same as the participant order!
        self.participant_ids.append(participant_id)

    def retrieve_share(self, client_id: str, op_id: str) -> Tuple[Share, Share, Share]:
        """
        Retrieve a triplet of shares for a given client_id.
        """
        assert client_id in self.participant_ids
        # If no triplets were generated for the given operation, generate the shares.          
        if op_id not in self.generated_shares:
            # Choose random a, b.
            s_a = rand_Zq()
            s_b = rand_Zq()
            # Compute c = a * b.
            s_c = s_a * s_b % default_q
            # Create the shares.
            a_shares = share_secret(s_a, len(self.participant_ids))
            b_shares = share_secret(s_b, len(self.participant_ids))
            c_shares = share_secret(s_c, len(self.participant_ids))
            self.generated_shares[op_id] = (a_shares, b_shares, c_shares)
        # Get the appropriate shares.
        shares = self.generated_shares.get(op_id)
        assert shares is not None
        i = self.participant_ids.index(client_id)
        # Return the triplet.
        return shares[0][i], shares[1][i], shares[2][i]
