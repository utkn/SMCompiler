"""
Implementation of an SMC client.

MODIFY THIS FILE.
"""
# You might want to import more classes if needed.

from typing import Any, Callable, Dict, List, Tuple

from communication import Communication
from expression import AddOp, Expression, MulOp, Scalar, Secret, SubOp
from protocol import ProtocolSpec
from secret_sharing import (
    BeaverDistributor,
    FieldElement,
    ScalarElement,
    Share,
    deserialize_share,
    reconstruct_secret,
    serialize_share,
    share_secret,
)


class SMCParty:
    """
    A client that executes an SMC protocol to collectively compute a value of an expression together
    with other clients.

    Attributes:
        client_id: Identifier of this client
        server_host: hostname of the server
        server_port: port of the server
        protocol_spec (ProtocolSpec): Protocol specification
        value_dict (dict): Dictionary assigning values to secrets belonging to this client.
    """

    def __init__(self, client_id: str, server_host: str, server_port: int, protocol_spec: ProtocolSpec,
                 value_dict: Dict[Secret, int], communication = None):
        if communication is None:
            self.comm = Communication(server_host, server_port, client_id)
        else:
            self.comm = communication

        self.client_id = client_id
        self.protocol_spec = protocol_spec
        self.value_dict = value_dict

    def run(self) -> int:
        """
        The method the client use to do the SMC.
        """
        # For each secret of this party, distribute the shares among the participants.
        for secret, value in self.value_dict.items():
            all_participants = self.protocol_spec.participant_ids
            # Get the shares.
            shares = self.share_secret(value, len(all_participants))
            # Send the shares to the corresponding participants.
            for participant, share in zip(all_participants, shares):
                self.send_secret_share(participant, secret.id, share)
        # Compute the expression and get the resulting share.
        result_share = self.process_expression(self.protocol_spec.expr)
        assert isinstance(result_share, Share)
        print(f"SMCParty: {self.client_id} has found the result share!")
        # Publish the result share.
        self.send_result_share(result_share)
        # Retrieve the other resulting shares.
        all_result_shares = self.receive_all_result_shares()
        # Reconstruct & return.
        return self.reconstruct_secret(all_result_shares)
    
    def share_secret(self, secret: int, num_shares: int) -> List[Share]:
        return share_secret(secret, num_shares)

    def reconstruct_secret(self, shares: List[Share]) -> int:
        return reconstruct_secret(shares)

    def receive_all_result_shares(self, info: str = "") -> List[Share]:
        """
        Receives all result shares meant for this party.
        """
        all_result_shares = []
        for participant in self.protocol_spec.participant_ids:
            share = self.receive_result_share(participant, info)
            all_result_shares.append(share)
        return all_result_shares

    def send_result_share(self, share: Share, info: str = ""):
        """
        Publicizes this party's result share.
        """
        label = f"result-share-{self.client_id}"
        if info != "":
            label += f"-{info}"
        print(f"SMCParty: Broadcasting result share {label}: {self.client_id} ->")
        payload = serialize_share(share)
        self.comm.publish_message(label, payload)

    def receive_result_share(self, src_id: str, info: str = "") -> Share:
        """
        Receives a single result share meant for this party.
        """
        label = f"result-share-{src_id}"
        if info != "":
            label += f"-{info}"
        print(f"SMCParty: Receiving result share {label}: -> {self.client_id}")
        payload = self.comm.retrieve_public_message(src_id, label)
        return deserialize_share(payload)

    def send_secret_share(self, dest_id: str, secret_id: bytes, share: Share):
        """
        Sends a secret share to the corresponding participant.
        """
        secret_id_int = int.from_bytes(secret_id, byteorder="big")
        label = f"secret-share-{secret_id_int}"
        print(f"SMCParty: Sending secret share {label}: {self.client_id} -> {dest_id}")
        payload = serialize_share(share)
        self.comm.send_private_message(dest_id, label, payload)

    def receive_secret_share(self, secret_id: bytes) -> Share:
        """
        Receives a secret share meant for this party.
        """
        secret_id_int = int.from_bytes(secret_id, byteorder="big")
        label = f"secret-share-{secret_id_int}"
        print(f"SMCParty: Receiving secret share {label}: -> {self.client_id}")
        payload = self.comm.retrieve_private_message(label)
        return deserialize_share(payload)

    def process_expression(self, expr: Expression) -> FieldElement:
        """
        Expression processing procedure, which uses a tree-traversal type to evaluate  
        the expression from bottom to top.
        """
        # Depending on the expression type, invoke expression-specific node visiters.
        if isinstance(expr, AddOp):
            return self.process_add(expr)
        if isinstance(expr, SubOp):
            return self.process_sub(expr)
        if isinstance(expr, MulOp):
            return self.process_mul(expr)
        if isinstance(expr, Scalar):
            return self.process_scalar(expr)
        if isinstance(expr, Secret):
            return self.process_secret(expr)
        raise RuntimeError("Unknown expression type")

    def process_secret(self, expr: Secret) -> Share:
        # Receive the secret share from the server when we encounter a `Secret` leaf.
        return self.receive_secret_share(expr.id)

    def process_scalar(self, expr: Scalar) -> ScalarElement:
        return ScalarElement(expr.value)

    def process_add(self, expr: AddOp) -> Any:
        # Simple expression + expression addition.
        left_share = self.process_expression(expr.left)
        right_share = self.process_expression(expr.right)
        result = left_share + right_share
        return result

    def process_mul(self, expr: MulOp) -> Any:
        left_share = self.process_expression(expr.left)
        right_share = self.process_expression(expr.right)
        # If either of the operands are scalars, then do simple scalar * share multiplication.
        if isinstance(left_share, ScalarElement) or isinstance(right_share, ScalarElement):
            result = left_share * right_share
            return result
        assert isinstance(left_share, Share)
        assert isinstance(right_share, Share)
        # Otherwise, do share * share multiplications
        op_id = expr.id.decode("utf-8")
        # Construct a beaver distributor.
        beaver_dist = BeaverDistributor(
            labels=(f"{op_id}", f"X-{op_id}", f"Y-{op_id}"),
            triplet_retriever=self.comm.retrieve_beaver_triplet_shares,
            blinded_share_publisher=self.send_result_share,
            blinded_value_retriever=self.receive_all_result_shares
        )
        # Perform the beaver multiplication.
        return beaver_dist.execute(left_share, right_share)

    def process_sub(self, expr: SubOp) -> Any:
        # Simple expression - expression subtraction.
        left_share = self.process_expression(expr.left)
        right_share = self.process_expression(expr.right)
        return left_share - right_share



