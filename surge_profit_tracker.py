import decimal
import os
import json
import datetime
import math
import mysql.connector
from dotenv import load_dotenv
import surge_get_wallet_transactions

#load environment variables
load_dotenv()

ROOT_PATH = os.getenv('ROOT_PATH')

with open(ROOT_PATH+"/surge_tokens.json", "r") as surge_tokens_json:
    surge_tokens = json.load(surge_tokens_json)

def roundToNearestMinuteInterval(tx_timestamp, round_down = True):
    datetime.datetime.fromtimestamp(tx_timestamp)

    if round_down:
        rounded_down_timestamp = math.floor(tx_timestamp / 60) * 60
        datetime_time = datetime.datetime.fromtimestamp(rounded_down_timestamp)
        return datetime_time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        rounded_up_timestamp = math.ceil(tx_timestamp / 60) * 60
        datetime_time = datetime.datetime.fromtimestamp(rounded_up_timestamp)
        return datetime_time.strftime("%Y-%m-%d %H:%M:%S")

def calculateSurgeProfits(wallet_address, surge_token):
    #setup DB connection
    mydb = mysql.connector.connect(
        host = os.getenv('DB_HOST'),
        user = os.getenv('DB_USERNAME'),
        password = os.getenv('DB_PASSWORD'),
        database = os.getenv('DB_DATABASE'), 
    )

    mycursor = mydb.cursor()

    # Get All Surge Transactions
    if surge_token == "all":
        surge_transactions_json = surge_get_wallet_transactions.fetch_all_transactions(wallet_address)
        surge_transactions = surge_transactions_json
    else:
        surge_transactions_json = surge_get_wallet_transactions.fetch_transactions(wallet_address, surge_token)
        surge_transactions = json.loads(surge_transactions_json)
        
    result = {}
    for token in surge_transactions:
        result[token] = {}

        if len(surge_transactions[token]['txs']) <= 0:
            return json.dumps(result)

        fees = surge_tokens[token]['fees'] 

        tokens_inbound = 0
        tokens_outbound = 0
        total_underlying_asset_amount_purchased = 0
        total_underlying_asset_value_purchased = 0
        total_underlying_asset_amount_received = 0
        
        db_table_name = surge_tokens[token]['table_name']

        timestamp_list = []
        for t_stamp in surge_transactions[token]["timestamps"]:
            rounded_down_date = roundToNearestMinuteInterval(int(t_stamp))
            rounded_up_date = roundToNearestMinuteInterval(int(t_stamp), False)

            if rounded_down_date not in timestamp_list:
                timestamp_list.append(rounded_down_date)

            if rounded_up_date not in timestamp_list:
                timestamp_list.append(rounded_up_date)

        #Build sql in string
        sql_in = "'"
        sql_in += "','".join(timestamp_list)
        sql_in += "'"

        sql = "SELECT * FROM `"+db_table_name+"_values` WHERE `timestamp` IN("+sql_in+")"
        mycursor.execute(sql)
        myresult = mycursor.fetchall()

        token_value_data = {}
        underlying_asset_value_data = {}
        if myresult:
            for row in myresult:
                # 0 id
                # 1 timestamp
                # 2 token_value_datas
                timestamp = row[1].strftime("%Y-%m-%d %H:%M:%S")
                if timestamp not in token_value_data:
                    token_value_data[timestamp] = []
                    
                if timestamp not in underlying_asset_value_data:
                    underlying_asset_value_data[timestamp] = []

                token_value_data_json = json.loads(row[2])
                token_value_data[timestamp].append(float(token_value_data_json['token_value']))
                underlying_asset_value_data[timestamp].append(float(token_value_data_json['underlying_asset_value']))
                
        for tx in surge_transactions[token]['txs']:
            
            tx_timestamp = int(tx['timeStamp'])
            surge_token_amount = int(tx['value'])
            tx_type = tx['type']

            datetime_time = datetime.datetime.fromtimestamp(tx_timestamp)
            seconds_diff = int(datetime_time.strftime("%S"))
            seconds_multiplier = int(seconds_diff) % 5
            times = (seconds_diff - seconds_multiplier) / 5

            rounded_down_date = roundToNearestMinuteInterval(int(tx_timestamp))
            rounded_up_date = roundToNearestMinuteInterval(int(tx_timestamp), False)

            token_price_diff = token_value_data[rounded_up_date][0] - token_value_data[rounded_down_date][0]
            token_value_interval = token_price_diff / 12

            underlying_asset_value_diff = underlying_asset_value_data[rounded_up_date][0] - underlying_asset_value_data[rounded_down_date][0]
            underlying_asset_value_interval = underlying_asset_value_diff / 12

            #Get the token price at time of transaction
            token_price = token_value_data[rounded_down_date][0] + (token_value_interval * times)
            token_price_at_transaction = float(f'{token_price:.18f}')

            if tx_type == 'buy' or tx_type == 'staked':
                tx_fee = fees[tx_type]
                tokens_inbound += surge_token_amount
                underlying_asset_price = underlying_asset_value_data[rounded_down_date][0] + underlying_asset_value_interval * times
                underlying_asset_price_at_transaction = float(f'{underlying_asset_price:.18f}')
                
                underlying_asset_value_at_transaction = float(f'{token_price_at_transaction * (surge_token_amount / (1 - tx_fee)):.18f}') 
                total_underlying_asset_value_purchased += underlying_asset_value_at_transaction
                
                underlying_asset_amount_purchased = underlying_asset_price_at_transaction * underlying_asset_value_at_transaction
                total_underlying_asset_amount_purchased += underlying_asset_amount_purchased
            elif tx_type == 'sell':
                tx_fee = fees[tx_type]
                tokens_outbound += surge_token_amount
                underlying_asset_price = underlying_asset_value_data[rounded_down_date][0] + underlying_asset_value_interval * times
                underlying_asset_price_at_transaction = float(f'{underlying_asset_price:.18f}')
                underlying_asset_value_at_transaction = float(f'{token_price_at_transaction * (surge_token_amount * (1 - tx_fee)):.18f}')
                underlying_asset_amount_received = underlying_asset_price_at_transaction * underlying_asset_value_at_transaction
                
                total_underlying_asset_amount_received += underlying_asset_amount_received
            elif tx_type == 'sent':
                tx_fee = fees['transfer']
                surge_token_amount = surge_token_amount / (1 - tx_fee)
                tokens_outbound += surge_token_amount
            elif tx_type == 'received':
                tokens_inbound += surge_token_amount
            
        result[token]['total_underlying_asset_value_purchased'] = "{:,.5f}".format(total_underlying_asset_value_purchased)
        result[token]['total_underlying_asset_amount_purchased'] = '$'+"{:,.2f}".format(total_underlying_asset_amount_purchased)
        result[token]['total_underlying_asset_amount_received'] = '$'+"{:,.2f}".format(total_underlying_asset_amount_received)
        
        remaining_tokens = tokens_inbound - tokens_outbound
        current_underlying_asset_value = 0
        current_value_of_surge_underlying_asset = 0
        current_underlying_asset_value = 0

        if remaining_tokens > 0:
            sql = "SELECT * FROM `"+db_table_name+"_values` WHERE 1 ORDER BY `id` DESC LIMIT 1"
            mycursor.execute(sql)
            myresult = mycursor.fetchall()

            current_token_value_data = json.loads(myresult[0][2])
            current_token_value_data['token_value'] = float(current_token_value_data['token_value'])
            current_token_value_data['underlying_asset_value'] = float(current_token_value_data['underlying_asset_value'])

            remaining_tokens_after_sell_fee = remaining_tokens-(remaining_tokens * fees['sell'])

            current_value_of_surge_underlying_asset = remaining_tokens_after_sell_fee * current_token_value_data['token_value']
            current_underlying_asset_value = current_value_of_surge_underlying_asset * current_token_value_data['underlying_asset_value']

            current_underlying_asset_value = current_underlying_asset_value
        else:
            current_token_value_data = {"underlying_asset_value": 0, "token_value": 0}

        decimal_display = str(surge_tokens[token]['decimal_display'])
        result[token]['current_underlying_asset_price'] = "{:,.{decimal_display}f}".format(current_token_value_data['underlying_asset_value'], decimal_display=decimal_display)
        result[token]['current_underlying_asset_amount'] = "{:,.5f}".format(current_value_of_surge_underlying_asset)
        result[token]['current_underlying_asset_value'] = '$'+"{:,.2f}".format(current_underlying_asset_value)

        overall_profit_or_loss = (current_underlying_asset_value + total_underlying_asset_amount_received) - total_underlying_asset_amount_purchased
        result[token]['overall_profit_or_loss'] = '$'+"{:,.2f}".format(overall_profit_or_loss)
    
    mycursor.close()
    mydb.close()
    
    return json.dumps(result)