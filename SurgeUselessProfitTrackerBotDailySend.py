import os
import json
import logging
import time
import datetime
from discord.client import Client
import pytz
import asyncio
import discord
from discord.ext import tasks, commands
from discord_components import *
from dotenv import load_dotenv
import surge_profit_tracker
import surge_profit_tracker_queue

#load environment variables
load_dotenv()

ROOT_PATH = os.getenv('ROOT_PATH')
SURGE_PROFIT_TRACKER_BOT_KEY = os.getenv('SURGE_PROFIT_TRACKER_BOT_KEY')
OWNER_DISCORD_ID = int(os.getenv('OWNER_DISCORD_ID'))

logging.basicConfig(filename=ROOT_PATH+"/error_log_daily_send.log",
    format='%(levelname)s %(asctime)s :: %(message)s',
    level=logging.WARNING)

with open(ROOT_PATH+"/surge_tokens.json", "r") as surge_tokens_json:
    surge_tokens = json.load(surge_tokens_json)

def createCalcResultEmbedMessage(token, result):
    embed = False

    data = json.loads(result)
    if len(data[token]) > 0:
        embed = discord.Embed(
            title="Surge "+surge_tokens[token]['symbol']+" Details",
            description="", 
            color=surge_tokens[token]['color'])
        embed.set_thumbnail(url=surge_tokens[token]['icon'])
        embed.add_field(name="Total Amount Bought in USD", value=data[token]['total_underlying_asset_amount_purchased'], inline=False)
        if token != 'SurgeUSD':
            embed.add_field(name="Total Amount Bought in "+surge_tokens[token]['symbol'], value=data[token]['total_underlying_asset_value_purchased'], inline=False)
        embed.add_field(name="Total Amount Sold in USD", value=data[token]['total_underlying_asset_amount_received'], inline=False)
        embed.add_field(name="Current Value After Sell Fee in USD", value=data[token]['current_underlying_asset_value'], inline=False)
        if token != 'SurgeUSD':
            embed.add_field(name="Current Value After Sell Fee in "+surge_tokens[token]['symbol'], value=data[token]['current_underlying_asset_amount'], inline=False)
            embed.add_field(name="Current "+surge_tokens[token]['symbol']+" Price:", value=data[token]['current_underlying_asset_price'], inline=False)
        embed.add_field(name="Overall +/- Profit in USD", value=data[token]['overall_profit_or_loss'], inline=False)
        
        embed_disclaimer_text = "This bot gives you a close approximation of your overall accrual of Surge Token value. This is accomplished by pulling buyer transaction history and tracking historical price data on both the Surge Token and it's backing asset. Due to volatility of the backing asset, the price average between milliseconds of every transaction is used to attain the historical value. Because of this, the reflected value may not be 100% accurate. Estimated accuracy is estimated to be within 90-100%."
        embed_disclaimer_text +="\n\nPlease contact birthdaysmoothie#9602 if you have any question, issues, or data-related concerns."
        embed_disclaimer_text +="\n\nPricing data powered by Binance and Coingecko APIs."
        embed_disclaimer_text +="\nTransaction data powered by BscScan APIs"
        embed.set_footer(text=embed_disclaimer_text)

    return embed

async def calculateAllProfits(user, wallet_address):
    await user.send("I'm creating your reports now:")
    for token in surge_tokens:
        result = surge_profit_tracker.calculateSurgeProfits(wallet_address, token)
        embed = createCalcResultEmbedMessage(token, result)
        if embed != False:
            await user.send(embed=embed)
    
    await user.send("All your reports are complete.")
    return

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    owner = client.get_user(OWNER_DISCORD_ID)
    with open(ROOT_PATH+"/daily_report_list.json", "r") as daily_report_list_json:
        daily_report_list = json.load(daily_report_list_json)

    await owner.send("Running daily reports now - sending to "+str(len(daily_report_list))+" users")

    for user_id in daily_report_list:
        user = client.get_user(int(user_id))
        await calculateAllProfits(user, daily_report_list[user_id])
        time.sleep(1)

    await owner.send("Daily reports all sent")
    exit()

client.run(SURGE_PROFIT_TRACKER_BOT_KEY)