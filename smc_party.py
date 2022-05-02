"""
Implementation of an SMC client.

MODIFY THIS FILE.
"""
# You might want to import more classes if needed.

import collections
import json
from typing import (
    Dict,
    List,
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
    serialize_share,
    share_secret,
    Share,
    unserialize_share,
    default_q
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
        print(f"SMCParty: {self.client_id} has found the result share!")
        # Publish the result share.
        self.send_result_share(result_share)
            
        # Retrieve the other resulting shares.
        all_result_shares = self.receive_all_result_shares()

        # Reconstruct & return.
        return reconstruct_secret(all_result_shares)

    
    def receive_all_result_shares(self, info: str = "") -> List[Share]:
        all_result_shares = []
        for participant in self.protocol_spec.participant_ids:
            share = self.receive_result_share(participant, info)
            all_result_shares.append(share)
        return all_result_shares


    def send_result_share(self, share: Share, info: str = ""):
        label = f"result-share-{self.client_id}"
        if info != "":
            label += f"-{info}"
        print(f"SMCParty: Broadcasting result share {label}: {self.client_id} ->")
        payload = serialize_share(share)
        self.comm.publish_message(label, payload)
    

    def receive_result_share(self, src_id: str, info: str = "") -> Share:
        label = f"result-share-{src_id}"
        if info != "":
            label += f"-{info}"
        print(f"SMCParty: Receiving result share {label}: -> {self.client_id}")
        payload = self.comm.retrieve_public_message(src_id, label)
        return unserialize_share(payload)


    def send_secret_share(self, dest_id: str, secret_id: bytes, share: Share):
        """
        Sends a secret share to the corresponding participant.
        """
        secret_id = int.from_bytes(secret_id, byteorder="big")
        label = f"secret-share-{secret_id}"
        print(f"SMCParty: Sending secret share {label}: {self.client_id} -> {dest_id}")
        payload = serialize_share(share)
        self.comm.send_private_message(dest_id, label, payload)
    

    def receive_secret_share(self, secret_id: bytes) -> Share:
        """
        Receives a secret share meant for this party.
        """
        secret_id = int.from_bytes(secret_id, byteorder="big")
        label = f"secret-share-{secret_id}"
        print(f"SMCParty: Receiving secret share {label}: -> {self.client_id}")
        payload = self.comm.retrieve_private_message(label)
        return unserialize_share(payload)


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
        return left_share + right_share
        
    
    def process_mul(self, expr: MulOp) -> Share:
        left_share = self.process_expression(expr.left)
        right_share = self.process_expression(expr.right)
        # If either of the operands are scalars, then do simple scalar * share multiplication.
        if left_share.is_scalar or right_share.is_scalar:
            return left_share * right_share
        # Otherwise, do share * share multiplications
        # The operation ID is always the minimum ID of the child expressions.
        op_id = min(int.from_bytes(expr.left.id, byteorder="big"), int.from_bytes(expr.right.id, byteorder="big"))
        # Receive the Beaver triplet.
        a, b, c = self.comm.retrieve_beaver_triplet_shares(f"{op_id}")
        # Convert the triplet into shares.
        a, b, c = Share(left_share.index, a), Share(left_share.index, b), Share(left_share.index, c)
        X_share = left_share - a
        Y_share = right_share - b
        self.send_result_share(X_share, info=f"{op_id}-X")
        self.send_result_share(Y_share, info=f"{op_id}-Y")
        X_shares = self.receive_all_result_shares(info=f"{op_id}-X")
        Y_shares = self.receive_all_result_shares(info=f"{op_id}-Y")
        X = reconstruct_secret(X_shares)
        Y = reconstruct_secret(Y_shares)
        X = Share(left_share.index, X, True)
        Y = Share(left_share.index, Y, True)
        result = c + (left_share * Y) + (right_share * X)
        if left_share.index == 0:
            result.value = (result.value - (X.value * Y.value)) % default_q
        return result
        

    def process_sub(self, expr: SubOp) -> Share:
        left_share = self.process_expression(expr.left)
        right_share = self.process_expression(expr.right)
        return left_share - right_share