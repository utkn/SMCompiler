
from multiprocessing import Process, Queue
import time

from expression import Secret
from server import run
from use_case import Bank, consensus


_PORT=5000
def smc_server(args):
    run("localhost", _PORT, args)

def run_server(participants):
    server = Process(target=smc_server, args=(participants,))
    server.start()
    return server

def default_bank(client_id,bank_names,secrets,exprs):
    # this bank only colaborates (doesn't make requests)
    bank = Bank(
        client_id,
        "localhost",
        _PORT,
        all_banks=bank_names,
        secrets=secrets,
        exprs=exprs
    )

# Tests
"""
Banks want to know wether a customer has had fraudulent transactions in the past, in any Bank.
- They can compute this information together without compromising the intutional privacy guarantees 
of these banking institutions, which means that the amount of frauds is computed without leaking 
information about, in which bank, those frauds were detected in the past.
"""

def frauds_1(client_id,bank_names,secrets,exprs,customer_name,queue):
    bank = Bank(
        client_id,
        "localhost",
        _PORT,
        all_banks=bank_names,
        secrets=secrets,
        exprs=exprs
    )
    frauds = bank.get_total_customer_frauds(customer_name)
    queue.put(frauds)

def test_frauds_1():
    """
    CreditBanq makes a public request, stating that he wants to gather information
    about a customer's frauds record, to all the colaborating banks.
    - All banks, come together and privately share the information they have on that client,
    in order to allow the computation of the {total amount of frauds commited in the past
    by the customer, on all of the banks}.
    """
    bank_names = ["CreditBanq", "UBCS", "PostFini", "LosPollosHermanos", "MigosBank"] 
    secrets, exprs = consensus(bank_names) 
    customer_name = "John Doe"
    expected = int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%5
    # Start trusted Server
    server = run_server(bank_names)
    time.sleep(2)
    # Colaborating banks
    partner_banks = []
    for name in bank_names[1:]:
        partner_banks.append(Process(target=default_bank, args=(name,bank_names,secrets,exprs)))
        # Compute expected result! (for testing purposes, the result depends on the banks' names)
        expected+=int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%5
    for bank in partner_banks: bank.start() 
    time.sleep(1)
    # Requester bank
    queue = Queue()
    main_bank = Process(target=frauds_1, args=(bank_names[0],bank_names,secrets,exprs,customer_name,queue))
    main_bank.start()
    # Wait for frauds' request to finish
    obtained = queue.get()
    print(f"{bank_names[0]}: {customer_name} has {obtained} frauds in total. [expected: {expected}]")
    main_bank.terminate()
    # Stop every process
    for bank in partner_banks: bank.terminate() 
    server.terminate()

    # Assert obtained vs expected 
    assert obtained == expected

    time.sleep(2)
    print("Server and Clients stopped.")

"""
Banks want to know the total amount (in money) of debt that a given customer has.
- They can compute this information together using the SMC protocol and primitives.
"""
def debt_1(client_id,bank_names,secrets,exprs,customer_name,queue):
    bank = Bank(
        client_id,
        "localhost",
        _PORT,
        all_banks=bank_names,
        secrets=secrets,
        exprs=exprs
    )
    debt = bank.get_total_customer_debt(customer_name)
    queue.put(debt)
    
def test_debt_1():
    bank_names = ["CreditBanq", "UBCS", "PostFini", "LosPollosHermanos", "MigosBank"]
    secrets, exprs = consensus(bank_names) 
    customer_name = "John Doe"
    bank_monthly_parcel = 10+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%100
    bank_loan_years = 1+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%8
    bank_paid_loan = 10+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%100
    expected = (12*bank_monthly_parcel*bank_loan_years) - bank_paid_loan
    # Start trusted Server
    server = run_server(bank_names)
    time.sleep(2)
    # Colaborating banks
    partner_banks = []
    for name in bank_names[1:]:
        partner_banks.append(Process(target=default_bank, args=(name,bank_names,secrets,exprs)))
        # Compute expected result! (for testing purposes, the result depends on the banks' names)
        bank_monthly_parcel = 10+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%100
        bank_loan_years = 1+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%8
        bank_paid_loan = 10+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%100
        expected+=(12*bank_monthly_parcel*bank_loan_years) - bank_paid_loan
    for bank in partner_banks: bank.start() 
    time.sleep(1)
    # Requester bank
    queue = Queue()
    main_bank = Process(target=debt_1, args=(bank_names[0],bank_names,secrets,exprs,customer_name,queue))
    main_bank.start()
    # Wait for frauds' request to finish
    obtained = queue.get()
    print(f"{bank_names[0]}: {customer_name} has {obtained} CHF total debt. [expected: {expected}]")
    main_bank.terminate()
    # Stop every process
    for bank in partner_banks: bank.terminate() 
    server.terminate()

    # Assert obtained vs expected 
    assert obtained == expected

    time.sleep(2)
    print("Server and Clients stopped.")

"""
Banks want to know the total amount (in money) of debt that a given customer has.
- They can compute this information together using the SMC protocol and primitives.
"""
def income_1(client_id,bank_names,secrets,exprs,customer_name,customer_picked_years,queue):
    bank = Bank(
        client_id,
        "localhost",
        _PORT,
        all_banks=bank_names,
        secrets=secrets,
        exprs=exprs
    )
    
    frauds = bank.get_money_estimate(customer_name,customer_picked_years)
    queue.put(frauds)
    
def test_income_1():
    bank_names = ["CreditBanq", "UBCS"]#, "PostFini", "LosPollosHermanos", "MigosBank"]
    secrets, exprs = consensus(bank_names) 
    customer_name = "John Doe"
    customer_picked_years = 10 #years
    deposits = 500+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%500
    expenses = 10+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%400
    expected = (12*customer_picked_years)
    cumulative = deposits-expenses
    # Start trusted Server
    server = run_server(bank_names)
    time.sleep(2)
    # Colaborating banks
    partner_banks = []
    for name in bank_names[1:]:
        partner_banks.append(Process(target=default_bank, args=(name,bank_names,secrets,exprs)))
        # Compute expected result! (for testing purposes, the result depends on the banks' names)
        deposits = 500+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%500
        expenses = 10+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%400
        cumulative += deposits-expenses
    expected*=cumulative
    for bank in partner_banks: bank.start() 
    time.sleep(1)
    # Requester bank
    queue = Queue()
    main_bank = Process(target=income_1, args=(bank_names[0],bank_names,secrets,exprs,customer_name,customer_picked_years,queue))
    main_bank.start()
    # Wait for request to finish being processed
    obtained = queue.get()
    print(f"{bank_names[0]}: {customer_name} is estimated to save {obtained} CHF in {customer_picked_years} years. [expected: {expected}]")
    main_bank.terminate()
    # Stop every process
    for bank in partner_banks: bank.terminate() 
    server.terminate()

    # Assert obtained vs expected 
    assert obtained == expected

    time.sleep(2)
    print("Server and Clients stopped.")


if __name__ == "__main__":
    #test_frauds_1()
    #test_debt_1()
    test_income_1()

