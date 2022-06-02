
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
def test_frauds_3_banks():
    bank_names = ["CreditBanq", "UBCS", "PostFini"] 
    frauds(bank_names, customer_name = "Utkan")

def test_frauds_5_banks():
    bank_names = ["CreditBanq", "UBCS", "PostFini", "LosPollosHermanos", "MigosBank"] 
    frauds(bank_names, customer_name = "Eduardo")

def frauds_requester(client_id,bank_names,secrets,exprs,customer_name,queue):
    bank = Bank(
        client_id,
        "localhost",
        _PORT,
        all_banks=bank_names,
        secrets=secrets,
        exprs=exprs
    )
    print(f"{client_id}: requesting {customer_name} fraud's information...")
    frauds = bank.get_total_customer_frauds(customer_name)
    queue.put(frauds)

def frauds(bank_names, customer_name = "John Doe"):
    """
    CreditBanq makes a public request, stating that he wants to gather information
    about a customer's frauds record, to all the colaborating banks.
    - All banks, come together and privately share the information they have on that client,
    in order to allow the computation of the {total amount of frauds commited in the past
    by the customer, on all of the banks}.
    """
    secrets, exprs = consensus(bank_names) 
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
    main_bank = Process(target=frauds_requester, args=(bank_names[0],bank_names,secrets,exprs,customer_name,queue))
    main_bank.start()
    # Wait for frauds' request to finish
    obtained = queue.get()
    print(f"{bank_names}: {customer_name} has {obtained} frauds in total. [expected: {expected}]")
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
def test_debt_2_banks():
    bank_names = ["UBCS", "MigosBank"]
    debt(bank_names, customer_name = "John Doe")

def test_debt_5_banks():
    bank_names = ["CreditBanq", "UBCS", "PostFini", "LosPollosHermanos", "MigosBank"]
    debt(bank_names, customer_name = "John Doe")

def debt_requester(client_id,bank_names,secrets,exprs,customer_name,queue):
    bank = Bank(
        client_id,
        "localhost",
        _PORT,
        all_banks=bank_names,
        secrets=secrets,
        exprs=exprs
    )
    print(f"{client_id}: requesting {customer_name} debt's information...")
    debt = bank.get_total_customer_debt(customer_name)
    queue.put(debt)
    
def debt(bank_names, customer_name = "John Doe"):
    secrets, exprs = consensus(bank_names) 
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
    main_bank = Process(target=debt_requester, args=(bank_names[0],bank_names,secrets,exprs,customer_name,queue))
    main_bank.start()
    # Wait for frauds' request to finish
    obtained = queue.get()
    print(f"{bank_names}: {customer_name} has {obtained} CHF total debt. [expected: {expected}]")
    main_bank.terminate()
    # Stop every process
    for bank in partner_banks: bank.terminate() 
    server.terminate()

    # Assert obtained vs expected 
    assert obtained == expected

    time.sleep(2)
    print("Server and Clients stopped.")

"""
Banks want to know an estimate of the total amount of money that a given customer can
save in X years. This information can be computed using the SMC protocol and primitives.
"""
def test_income_2_banks():
    bank_names = ["LosPollosHermanos", "MigosBank"]
    income(bank_names, customer_name = "John Doe")

def test_income_5_banks():
    bank_names = ["CreditBanq", "UBCS", "PostFini", "LosPollosHermanos", "MigosBank"]
    income(bank_names, customer_name = "John Doe")

def income_requester(client_id,bank_names,secrets,exprs,customer_name,customer_picked_years,queue):
    bank = Bank(
        client_id,
        "localhost",
        _PORT,
        all_banks=bank_names,
        secrets=secrets,
        exprs=exprs
    )
    print(f"{client_id}: requesting {customer_name}' wealth estimate after {customer_picked_years} years...")
    savings = bank.get_money_estimate(customer_name,customer_picked_years)
    queue.put(savings)
    
def income(bank_names):
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
    main_bank = Process(target=income_requester, args=(bank_names[0],bank_names,secrets,exprs,customer_name,customer_picked_years,queue))
    main_bank.start()
    # Wait for request to finish being processed
    obtained = queue.get()
    print(f"{bank_names}: {customer_name} is estimated to save {obtained} CHF in {customer_picked_years} years. [expected: {expected}]")
    main_bank.terminate()
    # Stop every process
    for bank in partner_banks: bank.terminate() 
    server.terminate()

    # Assert obtained vs expected 
    assert obtained == expected

    time.sleep(2)
    print("Server and Clients stopped.")

"""
This test instanciates 5 different banks that colaborate between each other.
1 of the banks, requests frauds' information of a customer, debt's info, and requests an estimation of savings of a customer after 10 years.
All banks must be able to colaborate between each others sharing information and computing the result of all operations. 
The requests are made sequentially.
"""
def test_all_info_5_banks():
    bank_names = ["CreditBanq", "UBCS", "PostFini", "LosPollosHermanos", "MigosBank"]
    all_info(bank_names)

"""
Same as test_all_info_5_banks() but only 2 banks are instanciated
"""
def test_all_info_2_banks():
    bank_names = ["PostFini", "LosPollosHermanos"]
    all_info(bank_names)
# - Auxiliar functions for this test suite
def all_requester(client_id,bank_names,secrets,exprs,customer_name,customer_picked_years,queue):
    bank = Bank(
        client_id,
        "localhost",
        _PORT,
        all_banks=bank_names,
        secrets=secrets,
        exprs=exprs
    )
    print(f"{client_id}: Requesting fraud information of {customer_name}..")
    fraud = bank.get_total_customer_frauds(customer_name)
    queue.put(fraud)
    time.sleep(10)
    print(f"{client_id}: Requesting debt information of {customer_name}..")
    debt = bank.get_total_customer_debt(customer_name)
    queue.put(debt)
    print(f"{client_id}: Requesting savings estimation of {customer_name} for {customer_picked_years} years..")
    time.sleep(10)
    saving = bank.get_money_estimate(customer_name,customer_picked_years)
    queue.put(saving)

def all_info(bank_names, customer_name = "John Doe"):
    secrets, exprs = consensus(bank_names) 
    customer_picked_years = 10 #years
    expected_fraud = int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%5
    bank_monthly_parcel = 10+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%100
    bank_loan_years = 1+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%8
    bank_paid_loan = 10+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%100
    expected_debt = (12*bank_monthly_parcel*bank_loan_years) - bank_paid_loan
    deposits = 500+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%500
    expenses = 10+int.from_bytes(bytes(bank_names[0]+customer_name,'utf-8'), byteorder="big")%400
    expected_income = (12*customer_picked_years)
    cumulative = deposits-expenses
    # Start trusted Server
    server = run_server(bank_names)
    time.sleep(2)
    # Colaborating banks and expected results
    partner_banks = []
    for name in bank_names[1:]:
        partner_banks.append(Process(target=default_bank, args=(name,bank_names,secrets,exprs)))
        # Compute expected result! (for testing purposes, the result depends on the banks' names)
        deposits = 500+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%500
        expenses = 10+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%400
        cumulative += deposits-expenses
        bank_monthly_parcel = 10+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%100
        bank_loan_years = 1+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%8
        bank_paid_loan = 10+int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%100
        expected_debt+=(12*bank_monthly_parcel*bank_loan_years) - bank_paid_loan
        expected_fraud+=int.from_bytes(bytes(name+customer_name,'utf-8'), byteorder="big")%5
    expected_income*=cumulative
    for bank in partner_banks: bank.start() 
    time.sleep(1)
    # Requester bank
    queue = Queue()
    main_bank = Process(target=all_requester, args=(bank_names[0],bank_names,secrets,exprs,customer_name,customer_picked_years,queue))
    main_bank.start()
    # Wait for results
    obtained_fraud = queue.get()
    obtained_debt = queue.get()
    obtained_income = queue.get()
    print(f"{bank_names}: \n\t{customer_name} has {obtained_fraud} frauds in total. [expected: {expected_fraud}]\n\t{customer_name} has {obtained_debt} CHF total debt. [expected: {expected_debt}]\n\t{customer_name} is estimated to save {obtained_income} CHF in {customer_picked_years} years. [expected: {expected_income}]")
    main_bank.terminate()
    # Stop every process
    for bank in partner_banks: bank.terminate() 
    server.terminate()

    # Assert obtained vs expected 
    assert obtained_fraud == expected_fraud
    assert obtained_debt == expected_debt
    assert obtained_income == expected_income

    time.sleep(2)
    print("Server and Clients stopped.")


if __name__ == "__main__":
    test_frauds_3_banks()
    test_frauds_5_banks()
    test_debt_2_banks()
    test_debt_5_banks()
    test_income_2_banks()
    test_income_5_banks()
    test_all_info_2_banks()
    test_all_info_5_banks()

