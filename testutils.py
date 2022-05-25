from typing import Tuple, List

from secret_sharing import Share, BeaverDistributor
from ttp import TrustedParamGenerator


class TestBeaverServer:
    """
    Represents a local Beaver multiplication server for testing purposes.
    """
    def __init__(self, num_clients: int):
        self.ttp = TrustedParamGenerator()
        self.published_shares = {}
        self.num_clients = num_clients

    def retrieve_triplets(self, op_id: str, client_id: str) -> Tuple[int, int, int]:
        shares = self.ttp.retrieve_share(client_id, op_id)
        return shares[0].value, shares[1].value, shares[2].value

    def publish_share(self, share: Share, label: str, client_id: str, client_index: int):
        if label not in self.published_shares:
            self.published_shares[label] = [None] * self.num_clients
        self.published_shares[label][client_index] = share

    def retrieve_shares(self, label: str) -> List[Share]:
        assert label in self.published_shares
        return self.published_shares[label]


def create_test_beaver_distributor(server: TestBeaverServer, client_id: str, client_index: int,
                                   op_id: str) -> BeaverDistributor:
    """Creates a Beaver client (i.e., distributor) for a given server."""
    return BeaverDistributor(labels=(op_id, f"{op_id}-X", f"{op_id}-Y"),
                             triplet_retriever=lambda label: server.retrieve_triplets(label, client_id),
                             blinded_share_publisher=lambda share, label: server.publish_share(share, label, client_id,
                                                                                               client_index),
                             blinded_value_retriever=lambda label: server.retrieve_shares(label))
