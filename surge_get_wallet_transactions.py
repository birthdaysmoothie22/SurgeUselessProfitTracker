import os
import json
import requests
import time
import random
from dotenv import load_dotenv

#load environment variables
load_dotenv()

API_KEYS_BSC = os.getenv('API_KEYS_BSC')
API_KEY_LIST = API_KEYS_BSC.split(",")

ROOT_PATH = os.getenv('ROOT_PATH')

with open(ROOT_PATH+"/surge_tokens.json", "r") as surge_tokens_json:
    surge_tokens = json.load(surge_tokens_json)

rate_limit = 0

# BSC Scan API has a limit of 5/second
# This makes sure we are not hitting that limit
def checkRateLimit():
    global rate_limit

    rate_limit += 1

    if rate_limit % 5 == 0:
        time.sleep(1)
        rate_limit = 0

# Fetch all transactions for all surge tokens for a specific wallet
def fetch_all_transactions(wallet_address):
    output = {}
    for token in surge_tokens:
        result = fetch_transactions(wallet_address, token)
        result = json.loads(result)
        output[token] = result[token]
    #return json.dumps(output)
    return output

# Fetch transactions for a specific surge token from a specific wallet
def fetch_transactions(wallet_address, surge_token, uri="https://api.bscscan.com/api"):
    output = {
        surge_token: {
            "txs": {},
            "timestamps": []
        }
    }

    surge_fund_address = "0x95c8ee08b40107f5bd70c28c4fd96341c8ead9c7"

    if surge_token in surge_tokens:
        wallet_address = wallet_address.lower()
        contract_address = surge_tokens[surge_token]['address']

        api_key = random.choice(API_KEY_LIST)

        payload = {"module": "account", "action": "tokentx", "contractaddress": contract_address, "address": wallet_address, "apikey": api_key}
        # buy = []
        # sell = []
        # received = []
        # sent = []
        # staked = []

        txs = []
        checkRateLimit()
        r = requests.get(uri, params=payload)
        if 200 <= r.status_code < 300 and r.json()["status"] == "1" and r.json()["message"] == "OK":
            result = r.json()['result']
            for tx in result:
                tx_type = ""
                if tx["to"] == wallet_address and tx["from"] == contract_address:
                    if 'allows_staking' in surge_tokens[surge_token] and surge_tokens[surge_token]['allows_staking']:
                        api_key = random.choice(API_KEY_LIST)

                        log_payload = {"module": "logs", "action": "getLogs", "address": contract_address,
                                    "topic0": "0x1c54f863308f3c46dc337349cd7c614a0aea0216aaf309e650c41479696ff927", "apikey": api_key,
                                    "fromBlock": tx["blockNumber"], "toBlock": tx["blockNumber"]
                                    }
                        checkRateLimit()
                        log = requests.get(uri, params=log_payload)
                        if len(log.json()['result']) == 0:
                            tx_type = "buy"
                        if len(log.json()['result']) != 0:
                            tx_type = "staked"
                    else:
                        tx_type = "buy"
                if tx["to"] == wallet_address and tx["from"] != contract_address:
                    tx_type = "received"
                if tx["to"] == contract_address and tx["from"] == wallet_address:
                    tx_type = "sell"
                if tx["to"] != contract_address and tx["to"] != surge_fund_address and tx["from"] == wallet_address:
                    tx_type = "sent"

                if len(tx_type):
                    txs.append({"timeStamp": tx["timeStamp"], "value": tx["value"], "type": tx_type})
                    output[surge_token]['txs'] = txs
                    output[surge_token]['timestamps'].append(tx["timeStamp"])
            return json.dumps(output)
        else:
            return json.dumps(output)
    else:
        raise ValueError("Invalid surge token supplied: "+surge_token)