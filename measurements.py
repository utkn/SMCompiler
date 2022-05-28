import argparse
from cmath import sqrt
import csv
import enum
from functools import reduce, wraps
from glob import glob
import os
import statistics
import sys
from communication import Communication
from expression import Scalar, Secret
import time

from multiprocessing import Process, Queue
from protocol import ProtocolSpec
from server import run
from smc_party import SMCParty
from secret_sharing import default_q

MEASUREMENT_FILE_FIELD_NAMES = ["name", "tag", "time (ms)", "output size (bytes)", "input size (bytes)"]

def with_measurement(proc, writer, measurement_name: str, tag: str):
    """
    Method wrapper to measure (1) the time it takes to execute the method (in ms), (2) output size (in bytes), (3) input size (in bytes)
    """
    @wraps(proc)
    def wrapped(*args, **kwargs):
        t0 = time.time()
        output = proc(*args, **kwargs)
        t1 = time.time()
        td = (t1 - t0) * 1000
        input_size = sum(sys.getsizeof(arg) for arg in args) + sum(sys.getsizeof(arg) for arg in kwargs.values())
        output_size = sys.getsizeof(output)
        writer.writerow({k: v for k, v in zip(MEASUREMENT_FILE_FIELD_NAMES, [measurement_name, tag, td, output_size, input_size])})
        return output
    return wrapped

class MeasuredInstance(object):
    """
    Object wrapper to measure all the methods of an object.
    """
    def __init__(self, target, measurement_writer, tag: str = "none"):
        self.measurement_writer = measurement_writer
        self.target = target
        self.tag = tag

    def __getattribute__(self, attr_name):
        target = object.__getattribute__(self, "target")
        measurement_writer = object.__getattribute__(self, "measurement_writer")
        tag = object.__getattribute__(self, "tag")
        proc = target.__getattribute__(attr_name)
        wrapped = with_measurement(proc, measurement_writer, "{}.{}".format(type(target).__name__, attr_name), tag)
        return wrapped

class MeasuredSMCParty(SMCParty):
    """
    A subclass of SMCParty that measures all the method calls through `self`.
    """
    def __init__(self, measurement_writer, tag: str = "none", **args):
        self.measurement_writer = measurement_writer
        self.tag = tag
        super().__init__(**args)

    def __getattribute__(self, attr_name):
        measurement_writer = object.__getattribute__(self, "measurement_writer")
        tag = object.__getattribute__(self, "tag")
        target = object.__getattribute__(self, attr_name)
        # Return the wrapped method if the requested attribute is indeed a method.
        # We should not try to wrap a field, e.g., `self.client_id`
        if callable(target):
            wrapped = with_measurement(target, measurement_writer, "{}.{}".format("SMCParty", attr_name), tag)
            return wrapped
        else:
            return target

def measured_smc_client(experiment_id, experiment_argument, current_run, queue, client_id, prot, value_dict):
    filename = f"{experiment_argument}-{current_run}-{client_id}"
    file = open(f"measurements/{experiment_id}/raw/{filename}.csv", "w")
    writer = csv.DictWriter(file, fieldnames=MEASUREMENT_FILE_FIELD_NAMES)
    writer.writeheader()
    # Create a measured `Communication` instance to directly measure the sizes of the sent/received objects.
    comm = MeasuredInstance(Communication("localhost", 5000, client_id), writer)
    # Create a measured SMC party to measure the running time. Supply the measured `Communication` as the
    # communication instance.
    cli = MeasuredSMCParty(writer, "",  
        client_id=client_id,
        server_host="localhost",
        server_port=5000,
        protocol_spec=prot,
        value_dict=value_dict,
        communication=comm)
    res = cli.run()
    queue.put(res)
    print(f"{client_id} has finished!")
    file.close()
    # Now, aggregate the raw data.
    file = open(f"measurements/{experiment_id}/raw/{filename}.csv", "r")
    reader = csv.DictReader(file, fieldnames=MEASUREMENT_FILE_FIELD_NAMES)
    total_run_time = 0
    total_bytes_in = 0
    total_bytes_out = 0
    for row in reader:
        if row["name"] == "SMCParty.run":
            total_run_time = float(row["time (ms)"])
        if row["name"] in {"Communication.send_private_message", 
                            "Communication.publish_message"}:
            total_bytes_out += int(row["input size (bytes)"])
        if row["name"] in {"Communication.retrieve_private_message", 
                            "Communication.retrieve_public_message", 
                            "Communication.retrieve_beaver_triplet_shares"}:
            total_bytes_in += int(row["output size (bytes)"])
    file.close()
    file = open(f"measurements/{experiment_id}/totals/{filename}-totals.txt", "w")
    file.write(f"{total_run_time}|{total_bytes_in}|{total_bytes_out}")
    file.close()

def smc_server(args):
    run("localhost", 5000, args)


def run_processes(experiment_id, experiment_argument, current_run, server_args, *client_args):
    queue = Queue()
    server = Process(target=smc_server, args=(server_args,))
    clients = [Process(target=measured_smc_client, args=(experiment_id, experiment_argument, current_run, queue, *args)) for args in client_args]
    server.start()
    time.sleep(3)
    for client in clients:
        client.start()
    results = list()
    for client in clients:
        client.join()
    for client in clients:
        results.append(queue.get())
    server.terminate()
    server.join()
    # To "ensure" the workers are dead.
    time.sleep(2)
    print("Server stopped.")
    return results


def suite(experiment_id, experiment_argument, current_run, parties, expr, expected):
    participants = list(parties.keys())
    prot = ProtocolSpec(expr=expr, participant_ids=participants)
    clients = [(name, prot, value_dict) for name, value_dict in parties.items()]
    results = run_processes(experiment_id, experiment_argument, current_run, participants, *clients)
    for result in results:
        assert result % default_q == expected % default_q


# Varying number of parties with addition of their secrets.
def experiment_1(current_run: int, num_parties: int):
    # 1 + 2 + ... + (N-1) + N
    secrets = [Secret() for _ in range(num_parties)]
    expr = reduce(lambda x, y: x + y, secrets)
    parties = {f"P{i}": {} for i in range(num_parties)}
    for i, secret in  enumerate(secrets):
        parties[f"P{i}"][secret] = i + 1
    expected = sum((i + 1 for i in range(num_parties)))
    suite(1, num_parties, current_run, parties, expr, expected)

# Fixed number of parties (5) with varying number of (N * 5) secret additions.
def experiment_2(current_run: int, addition_per_secret: int):
    # (1 + ... + 1) + (2 + ... + 2) + ... + (5 + ... + 5)
    num_parties = 5
    secrets = [[Secret()] * addition_per_secret for _ in range(num_parties)]
    expr = reduce(lambda x, y: x + y, (reduce(lambda x, y: x + y, client_secrets) for client_secrets in secrets))
    parties = {f"P{i}": {} for i in range(num_parties)}
    for i, client_secrets in  enumerate(secrets):
        for secret in client_secrets:
            parties[f"P{i}"][secret] = i + 1
    expected = sum((addition_per_secret * (i + 1) for i in range(num_parties)))
    suite(2, addition_per_secret, current_run, parties, expr, expected)

# Fixed number of parties (5) with varying number of (N * 5) secret multiplications.
def experiment_3(current_run: int, mult_per_secret: int):
    # (1 * ... * 1) + (2 * ... * 2) + ... + (5 * ... * 5)
    num_parties = 5
    secrets = [[Secret()] * mult_per_secret for _ in range(num_parties)]
    expr = reduce(lambda x, y: x + y, (reduce(lambda x, y: x * y, client_secrets) for client_secrets in secrets))
    parties = {f"P{i}": {} for i in range(num_parties)}
    for i, client_secrets in  enumerate(secrets):
        for secret in client_secrets:
            parties[f"P{i}"][secret] = i + 1
    expected = sum(((i + 1) ** mult_per_secret for i in range(num_parties)))
    suite(3, mult_per_secret, current_run, parties, expr, expected)

# Fixed number of parties (5) with varying number of (N) scalar additions.
def experiment_4(current_run: int, num_additions: int):
    # 1 + 2 + 3 + 4 + 5 + (Scalar(5) + Scalar(5) + ... + Scalar(5))
    num_parties = 5
    secrets = [Secret() for _ in range(num_parties)]
    expr = reduce(lambda x, y: x + y, secrets) + reduce(lambda x, y: x + y, [Scalar(5)] * num_additions)
    parties = {f"P{i}": {} for i in range(num_parties)}
    for i, secret in  enumerate(secrets):
        parties[f"P{i}"][secret] = i + 1
    expected = 15 + num_additions * 5
    suite(4, num_additions, current_run, parties, expr, expected)


# Fixed number of parties (5) with varying number of (N) scalar multiplications.
def experiment_5(current_run: int, num_mults: int):
    # 1 + 2 + 3 + 4 + 5 + (Scalar(5) * Scalar(5) * ... * Scalar(5))
    num_parties = 5
    secrets = [Secret() for _ in range(num_parties)]
    expr = reduce(lambda x, y: x + y, secrets) + reduce(lambda x, y: x * y, [Scalar(5)] * num_mults)
    parties = {f"P{i}": {} for i in range(num_parties)}
    for i, secret in  enumerate(secrets):
        parties[f"P{i}"][secret] = i + 1
    expected = 15 + 5 ** num_mults
    suite(5, num_mults, current_run, parties, expr, expected)

EXPERIMENTS = {
    "1": experiment_1,
    "2": experiment_2,
    "3": experiment_3,
    "4": experiment_4,
    "5": experiment_5
}

# Takes measurements.
def cmd_measure(runs, experiment_id, experiment_arg):
    for i in range(runs):
        print("*** RUN", i + 1)
        EXPERIMENTS[experiment_id](i + 1, experiment_arg)
    # Now, aggregate over all parties over all runs.
    filepaths = glob(f"./measurements/{experiment_id}/totals/{experiment_arg}-*.txt")
    total_run_time = []
    total_bytes_in = []
    total_bytes_out = []
    for path in filepaths:
        file = open(path, "r")
        fields = file.readline().split("|")
        total_run_time.append(float(fields[0]))
        total_bytes_in.append(int(fields[1]))
        total_bytes_out.append(int(fields[2]))
        file.close()
    file = open(f"./measurements/{experiment_id}/results-{experiment_arg}.txt", "w")
    for measurement_name, measurement_data in zip(["run_time", "bytes_in", "bytes_out"], [total_run_time, total_bytes_in, total_bytes_out]):
        stdev = statistics.stdev(measurement_data)
        mean = statistics.mean(measurement_data)
        file.write(f"{measurement_name} => Avg = {mean}, Stdev = {stdev}\n")
    file.close()

if __name__ == "__main__":
    sys.setrecursionlimit(5000)
    for experiment_id in EXPERIMENTS.keys():
        try:
            os.makedirs(f"./measurements/{experiment_id}/raw")
            os.makedirs(f"./measurements/{experiment_id}/totals")
        except:
            pass
    parser = argparse.ArgumentParser(description="Measurements")
    parser.add_argument("-r", "--runs", type=int, default=10, help="number of runs for measurements")
    parser.add_argument("-e", "--experiment", type=str, required=True, help="Experiment ID")
    parser.add_argument("-a", "--argument", type=int, required=True, help="Experiment argument")
    args = parser.parse_args()
    cmd_measure(args.runs, args.experiment, args.argument)