from multiprocessing import  Process
from expression import Expression, MulOp, Scalar, Secret
from protocol import ProtocolSpec
from server import _set_value
from smc_party import SMCParty
from random import randint
from typing import Any, Callable, Dict, List, Tuple
import time
import signal 
from threading import Thread, Lock

"""
Bank's supported operations:

    customer's past_frauds = (bank_A_fraudulent_transactions + bank_B_fraudulent_transactions
 + bank_C_fraudulent_transactions + ...)

    customer's current_debt = (12*bank_A_loan_year*bank_A_monthly_parcel)-bank_A_total_amount_paid + 
(12*bank_B_loan_year*bank_B_monthly_parcel)-bank_B_total_amount_paid +
(12*bank_C_loan_year*bank_C_monthly_parcel)-bank_C_total_amount_paid + ...

    customer's estimated amount of money after user_picked_years = 
user_picked_years*12*( (bank_A_avg_monthly_deposits-bank_A_avg_monthly_spendings) +
(bank_B_avg_monthly_deposits-bank_B_avg_monthly_spendings)
+ (bank_C_avg_monthly_deposits-bank_C_avg_monthly_spendings) + ...)
"""

def consensus(bank_names) -> Tuple[Dict[str,List[List[Secret]]], List[Expression]]:
    """
    All banks start by reaching consensus on the Secrets and Expressions 
    that they are going to colaborate on.
    """
    secrets = dict()
    # We support 3 operations
    for name in bank_names:
        frauds=[Secret()]
        debt=[Secret(),Secret(),Secret()]
        income=[Secret(),Secret()]
        secrets[name]=[frauds,debt,income]
    secrets[bank_names[0]][2].append(Secret()) #years

    # Compute expressions
    requester = bank_names[0]
    frauds_expr = secrets[requester][0][0]
    debt_expr = ((Scalar(12)*secrets[requester][1][0]*secrets[requester][1][1]) - secrets[requester][1][2])
    income_expr = (secrets[requester][2][2]*Scalar(12))
    cumulative = (secrets[requester][2][0]-secrets[requester][2][1])
    for name in bank_names[1:]: 
        frauds_expr += secrets[name][0][0]
        debt_expr += ((Scalar(12)*secrets[name][1][0]*secrets[name][1][1]) - secrets[name][1][2]) 
        cumulative += (secrets[name][2][0]-secrets[name][2][1])
    income_expr *= cumulative

    expressions = [frauds_expr, debt_expr, income_expr]
    return secrets, expressions

# Bank extends SMCParty
class Bank(SMCParty):
    """
    Bank extends SMCParty that executes an SMC protocol to collectively compute a value of an expression together
    with other clients.

    Attributes:
        client_id: Identifier of this client
        server_host: hostname of the server
        server_port: port of the server
        all_banks: names of all colaborating banks
        secrets: maps client_ids to its secret's references per operation
        exprs: list with consensus expression per operation
    """
    def __init__(self, client_id: str, server_host: str, server_port: int, all_banks: List[str], secrets: Dict[str,List[List[Secret]]], exprs: List[Expression] ,protocol_spec = None, value_dict = None, communication = None):
        self.partner_banks = all_banks.copy()
        self.partner_banks.remove(client_id)
        self.secrets = secrets
        self.exprs = exprs
        self.all_banks=all_banks
        super().__init__(client_id, server_host, server_port, protocol_spec, value_dict, communication)
        self.worker_lock = Lock()
        self.workers = []
        self.sub_workers = []
        for bank_name in self.partner_banks:
            # One process per partner bank
            p = Thread(target=self.colaborate, args=(bank_name,),daemon=False)
            self.workers.append(p)
            p.start()
        
    def get_total_customer_frauds(self, customer_name: str) -> int:
        """
        Computes the total amount of fraudulent transactions associated with the customer, by sharing info with other banks.
        
        Arguments:
            customer_name: Name of the customer being analyzed 
        """
        self.worker_lock.acquire()
        #request all banks for fraud info on the customer
        self.comm.publish_message("fraudreq",bytes(customer_name, 'utf-8'))
        # wait 1 sec for responses
        time.sleep(len(self.partner_banks)) 
        # this bank's secret
        bank_secret = self.secrets[self.client_id][0][0] 

        expr = self.exprs[0]
        # Update Bank's value_dict attr
        frauds_count = self.get_costumer_frauds(customer_name)
        self.value_dict = {bank_secret : frauds_count}
        print(f"{self.client_id}: (frauds:{self.value_dict[bank_secret]})")
        # Update Bank's protocol_spec attr
        self.protocol_spec = ProtocolSpec(expr=expr, participant_ids=self.all_banks)
        
        # Run SMC 
        total_frauds_count = self.run()
         
        self.worker_lock.release()
        return total_frauds_count
          
    def get_total_customer_debt(self, customer_name: str) -> int:
        """
        Computes the total amount of customer's current debt, from shared information.
        
        Arguments:
            customer_name: Name of the customer being analyzed 
        """
        self.worker_lock.acquire()

        #request all banks for fraud info on the customer
        self.comm.publish_message("debtreq",bytes(customer_name, 'utf-8'))
        # wait 1 sec for responses
        time.sleep(len(self.partner_banks)) 
        # - Bank's secrets
        # loan's monthly parcel (money amount)
        bank_monthly_parcel = self.secrets[self.client_id][1][0] 
        # the total amount of years to pay the loan given by this bank
        bank_loan_years = self.secrets[self.client_id][1][1]
        # the amount of money that has already been paid by the costumer to amortize the loan
        bank_paid_loan = self.secrets[self.client_id][1][2] 
        expr = self.exprs[1]
        # Update Bank's value_dict attr
        self.value_dict = {
            bank_monthly_parcel: self.get_costumer_monthly_parcel(customer_name),
            bank_loan_years: self.get_costumer_loan_years(customer_name),
            bank_paid_loan: self.get_costumer_paid_loan(customer_name),
            }
        print(f"{self.client_id}: (month_parcel:{self.value_dict[bank_monthly_parcel]}, total_loan_years:{self.value_dict[bank_loan_years]}, already_paid:{self.value_dict[bank_paid_loan]})")
        # Update Bank's protocol_spec attr
        self.protocol_spec = ProtocolSpec(expr=expr, participant_ids=self.all_banks)
        
        # Run SMC 
        total_debt = self.run()
         
        self.worker_lock.release()
        print(f"{self.client_id}: total_debt: {total_debt}")
        
        return total_debt

    def get_money_estimate(self, customer_name: str, years: int):
        """
        Computes an estimate of the total amount of money the customer will have after years, based on its current deposits and spendings
        
        Arguments:
            customer_name: Name of the customer being analyzed 
            years: amount of years for which the estimate is being calculated
        """
        self.worker_lock.acquire()

        #request all banks for fraud info on the customer
        self.comm.publish_message("estimatereq",bytes(customer_name, 'utf-8'))

        # wait 1 sec for responses
        time.sleep(len(self.partner_banks)) 
        # - Bank's secrets
        # average amount of money that the customer deposits per month
        bank_avg_monthly_deposits = self.secrets[self.client_id][2][0] 
        # average amount of money that the customer spends per month
        bank_avg_monthly_spendings = self.secrets[self.client_id][2][1] 
        years_secret=self.secrets[self.client_id][2][2] 
        expr = self.exprs[2]
        # Update Bank's value_dict attr
        self.value_dict = {
            years_secret : years,
            bank_avg_monthly_deposits: self.get_costumer_avg_monthly_deposits(customer_name),
            bank_avg_monthly_spendings: self.get_costumer_avg_monthly_spendings(customer_name),
            }
        print(f"{self.client_id}: (deposits:{self.value_dict[bank_avg_monthly_deposits]},spendings:{self.value_dict[bank_avg_monthly_spendings]})")
        # Update Bank's protocol_spec attr
        self.protocol_spec = ProtocolSpec(expr=expr, participant_ids=self.all_banks)
        
        # Run SMC 
        total_estimate = self.run()
        self.worker_lock.release()
        
        return total_estimate

    def colaborate(self, bank_name):
        req_labels = ["fraudreq", "debtreq", "estimatereq"] 
        for i in range(len(req_labels)):
            p = Thread(target=self.process_request, args=(bank_name,req_labels,i),daemon=False)
            self.sub_workers.append(p)
            p.start()

    def process_request(self, bank_name ,req_labels, label_ind):
        label = req_labels[label_ind]
        last = bytes() 
        time.sleep(len(self.partner_banks))
        while True:      
            req = self.comm.retrieve_public_message(bank_name, label)
            if last==req: time.sleep(10) ; continue 
            if label_ind == 0:
                #share fraud info
                self.worker_lock.acquire()
                bank_secret = self.secrets[self.client_id][0][0]
                expr = self.exprs[0]
                time.sleep(len(self.partner_banks))
                # Update Bank's value_dict attr
                frauds_count = self.get_costumer_frauds(req.decode('utf-8'))
                self.value_dict = {bank_secret : frauds_count}
                print(f"{self.client_id}: (frauds:{self.value_dict[bank_secret]})")
                # Update Bank's protocol_spec attr
                self.protocol_spec = ProtocolSpec(expr=expr, participant_ids=self.all_banks)
                # Run SMC 
                total_frauds_count = self.run()
                 
                print(f"{self.client_id}: total_fraud: {total_frauds_count}")
            elif label_ind == 1:
                #share debt info
                self.worker_lock.acquire()
                # loan's monthly parcel (money amount)
                bank_monthly_parcel = self.secrets[self.client_id][1][0]
                # the total amount of years to pay the loan given by this bank
                bank_loan_years = self.secrets[self.client_id][1][1] 
                # the amount of money that has already been paid by the costumer to amortize the loan
                bank_paid_loan = self.secrets[self.client_id][1][2] 
                expr = self.exprs[1]
                time.sleep(len(self.partner_banks))
                # Update Bank's value_dict attr
                self.value_dict = {
                    bank_monthly_parcel: self.get_costumer_monthly_parcel(req.decode('utf-8')),
                    bank_loan_years: self.get_costumer_loan_years(req.decode('utf-8')),
                    bank_paid_loan: self.get_costumer_paid_loan(req.decode('utf-8')),
                    }

                print(f"{self.client_id}: (month_parcel:{self.value_dict[bank_monthly_parcel]}, total_loan_years:{self.value_dict[bank_loan_years]}, already_paid:{self.value_dict[bank_paid_loan]})")
                # Update Bank's protocol_spec attr
                self.protocol_spec = ProtocolSpec(expr=expr, participant_ids=self.all_banks)
                # Run SMC 
                total_debt = self.run()
                 
                print(f"{self.client_id}: total_debt: {total_debt}")
            elif label_ind == 2:
                self.worker_lock.acquire()
                # share estimate earnings info
                # average amount of money that the customer deposits per month
                bank_avg_monthly_deposits = self.secrets[self.client_id][2][0] 
                # average amount of money that the customer spends per month
                bank_avg_monthly_spendings = self.secrets[self.client_id][2][1] 
                expr = self.exprs[2]
                # Update Bank's value_dict attr
                self.value_dict = {
                    bank_avg_monthly_deposits: self.get_costumer_avg_monthly_deposits(req.decode('utf-8')),
                    bank_avg_monthly_spendings: self.get_costumer_avg_monthly_spendings(req.decode('utf-8')),
                    }
                print(f"{self.client_id}: (deposits:{self.value_dict[bank_avg_monthly_deposits]},spendings:{self.value_dict[bank_avg_monthly_spendings]})")
                # Update Bank's protocol_spec attr
                self.protocol_spec = ProtocolSpec(expr=expr, participant_ids=self.all_banks)
                # Run SMC 
                total_estimate = self.run()
                 
                print(f"{self.client_id}: earnings: {total_estimate}")
            else:
                self.worker_lock.release()
                break    
            self.worker_lock.release()
            time.sleep(3) 

    # -- Dummy methods
    def get_costumer_frauds(self, customer_name: str):
        # query DB with log of costumer frauds and return count
        #return randint(0,5)
        return int.from_bytes(bytes(self.client_id+customer_name,'utf-8'), byteorder="big")%5

    def get_costumer_monthly_parcel(self, customer_name: str):
        # query DB 
        #return randint(50,250)
        return 10+int.from_bytes(bytes(self.client_id+customer_name,'utf-8'), byteorder="big")%100

    def get_costumer_loan_years(self, customer_name: str):
        # query DB 
        #return randint(2,10)
        return 1+int.from_bytes(bytes(self.client_id+customer_name,'utf-8'), byteorder="big")%8

    def get_costumer_paid_loan(self, customer_name: str):
        # query DB 
        #return randint(50,100)
        return 10+int.from_bytes(bytes(self.client_id+customer_name,'utf-8'), byteorder="big")%100

    def get_costumer_avg_monthly_deposits(self, customer_name: str):
        # query DB 
        #return randint(500,1000)
        return 500+int.from_bytes(bytes(self.client_id+customer_name,'utf-8'), byteorder="big")%500
    
    def get_costumer_avg_monthly_spendings(self, customer_name: str):
        # query DB 
        #return randint(10,500)
        return 10+int.from_bytes(bytes(self.client_id+customer_name,'utf-8'), byteorder="big")%400
    
    
