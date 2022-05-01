"""
Implementation of an SMC client.

MODIFY THIS FILE.
"""
# You might want to import more classes if needed.

import collections
import json
from typing import (
    Dict,
    Set,
    Tuple,
    Union
)

from communication import Communication
from expression import (
    AddOp,
    ExprType,
    Expression,
    MulOp,
    Scalar,
    Secret,
    SubOp
)
from protocol import ProtocolSpec
from secret_sharing import(
    reconstruct_secret,
    share_secret,
    Share,
)

# Feel free to add as many imports as you want.


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

    def __init__(self, client_id: str, server_host: str, server_port: int, protocol_spec: ProtocolSpec, value_dict: Dict[Secret, int]):
        self.comm = Communication(server_host, server_port, client_id)

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
            shares = share_secret(value, len(all_participants))
            # Send the shares to the corresponding participants.
            for participant, share in zip(all_participants, shares):
                self.send_secret_share(participant, secret.id, share)
        
        # Compute the expression and get the resulting share.
        result_share = self.process_expression(self.protocol_spec.expr)
        # Publish the result share.
        self.send_result_share(result_share)

        # Retrieve the other resulting shares.
        all_result_shares = []
        for participant in self.protocol_spec.participant_ids:
            share = self.retrieve_result_share(participant)
            all_result_shares.append(share)

        # Reconstruct & return.
        return reconstruct_secret(all_result_shares)

    
    def send_result_share(self, share: Share):
        label = f"result-share-{self.client_id}"
        payload = json.dumps(share).encode("utf-8")
        self.comm.publish_message(label, payload)
    
    def retrieve_result_share(self, src_id: str) -> Share:
        label = f"result-share-{self.client_id}"
        payload = self.comm.retrieve_public_message(src_id, label)
        result_dict = json.loads(payload.decode("utf-8"))
        return Share(**result_dict)


    def send_secret_share(self, dest_id: str, secret_id: int, share: Share):
        """
        Sends a secret share to the corresponding participant.
        """
        label = f"secret-share-{secret_id}"
        payload = json.dumps(share).encode("utf-8")
        self.comm.send_private_message(dest_id, label, payload)
    

    def receive_secret_share(self, secret_id: int) -> Share:
        """
        Receives a secret share meant for this party.
        """
        label = f"secret-share-{secret_id}"
        payload = self.comm.retrieve_private_message(label)
        share_dict = json.loads(payload.decode("utf-8"))
        return Share(**share_dict)


    # Suggestion: To process expressions, make use of the *visitor pattern* like so:
    def process_expression(self, expr: Expression) -> Share:
        if expr.type == ExprType.ADD:
            return self.process_add(expr)
        if expr.type == ExprType.SUB:
            return self.process_sub(expr)
        if expr.type == ExprType.MUL:
            return self.process_mul(expr)
        if expr.type == ExprType.SCALAR:
            return self.process_scalar(expr)
        if expr.type == ExprType.SECRET:
            return self.process_secret(expr)
    

    def process_secret(self, expr: Secret) -> Share:
        return self.receive_secret_share(expr.id)
    

    def process_scalar(self, expr: Scalar) -> Share:
        return Share(expr.id, expr.value, True)
    

    def process_add(self, expr: AddOp) -> Share:
        left_share = self.process_expression(expr.left)
        right_share = self.process_expression(expr.right)
        first, second = reorder_shares(left_share, right_share)
        return first + second
        
    
    def process_mul(self, expr: MulOp) -> Share:
        left_share = self.process_expression(expr.left)
        right_share = self.process_expression(expr.right)
        first, second = reorder_shares(left_share, right_share)
        return first * second


    def process_sub(self, expr: SubOp) -> Share:
        left_share = self.process_expression(expr.left)
        right_share = self.process_expression(expr.right)
        first, second = reorder_shares(left_share, right_share)
        return first - second


# Reorder the given shares such that if one of them is a scalar, it is returned as the second return value.
def reorder_shares(left_share: Share, right_share: Share) -> Tuple[Share, Share]:
    return right_share, left_share if left_share.is_scalar else left_share, right_share