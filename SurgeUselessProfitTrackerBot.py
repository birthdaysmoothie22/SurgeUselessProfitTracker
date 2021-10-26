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

#load environment variables
load_dotenv()

ROOT_PATH = os.getenv('ROOT_PATH')
SURGE_PROFIT_TRACKER_BOT_KEY = os.getenv('SURGE_PROFIT_TRACKER_BOT_KEY')
OWNER_DISCORD_ID = int(os.getenv('OWNER_DISCORD_ID'))

logging.basicConfig(filename=ROOT_PATH+"/error_log.log",
    format='%(levelname)s %(asctime)s :: %(message)s',
    level=logging.ERROR)

with open(ROOT_PATH+"/surge_tokens.json", "r") as surge_tokens_json:
    surge_tokens = json.load(surge_tokens_json)

def createCalcResultEmbedMessage(token, result):
    embed = False

    data = json.loads(result)
    if len(data[token]) > 0:
        embed = discord.Embed(
            title="**Surge "+surge_tokens[token]['symbol']+" Details**",
            description="", 
            color=surge_tokens[token]['color'])
        embed.set_thumbnail(url=surge_tokens[token]['icon'])
        embed.add_field(name="**Total Amount Bought in USD**", value=data[token]['total_underlying_asset_amount_purchased'], inline=False)
        if token != 'SurgeUSD':
            embed.add_field(name="**Total Amount Bought in "+surge_tokens[token]['symbol']+"**", value=data[token]['total_underlying_asset_value_purchased'], inline=False)
        embed.add_field(name="**Total Amount Sold in USD**", value=data[token]['total_underlying_asset_amount_received'], inline=False)
        embed.add_field(name="**Current Value After Sell Fee in USD**", value=data[token]['current_underlying_asset_value'], inline=False)
        if token != 'SurgeUSD':
            embed.add_field(name="**Current Value After Sell Fee in "+surge_tokens[token]['symbol']+"**", value=data[token]['current_underlying_asset_amount'], inline=False)
            embed.add_field(name="**Current "+surge_tokens[token]['symbol']+" Price:**", value=data[token]['current_underlying_asset_price'], inline=False)
        embed.add_field(name="**Overall +/- Profit in USD**", value=data[token]['overall_profit_or_loss'], inline=False)
        
        embed_disclaimer_text = "This bot gives you a close approximation of your overall accrual of Surge Token value. This is accomplished by pulling buyer transaction history and tracking historical price data on both the Surge Token and it's backing asset. Due to volatility of the backing asset, the price average between milliseconds of every transaction is used to attain the historical value. Because of this, the reflected value may not be 100% accurate. Estimated accuracy is estimated to be within 90-100%."
        embed_disclaimer_text +="\n\nPlease contact birthdaysmoothie#9602 if you have any question, issues, or data-related concerns."
        embed_disclaimer_text +="\n\nPricing data powered by Binance and Coingecko APIs."
        embed_disclaimer_text +="\nTransaction data powered by BscScan APIs"
        embed.set_footer(text=embed_disclaimer_text)

    return embed

def createCustomHelpEmbedMessage():
    embed = discord.Embed(
        title="Available SurgeUseless Profit Tracker Bot Commands",
        description="Here are all the available commands for the SurgeUseless Profit Tracker Bot.", 
        color=0x22B4AB)
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/902346003229843518/902346661332930621/sUselesslogo.png")
    embed.add_field(name="calculate, calc", value="Calculates your overall Surge Useless Token value.  Requires you to provide your BEP-20 public wallet address.", inline=False)
    # embed.add_field(name="calculate_manual, calc_manual", value="Calculates your overall Surge Token value.  You must provide the token you wish to caluclate and your public wallet address.  Example: !calculate_manual SurgeADA 0x00a...", inline=False)
    # embed.add_field(name="list", value="View available tokens to choose from.", inline=False)
    # embed.add_field(name="remove_daily", value="Be removed from the daily report list.", inline=False)

    return embed

def checkUserRoles(ctx):
    return True

async def calculateProfits(ctx, token, wallet_address):
    await ctx.author.send("I'm creating your report now:")
    result = surge_profit_tracker.calculateSurgeProfits(wallet_address, token)
    embed = createCalcResultEmbedMessage(token, result)
    if embed != False:
        await ctx.author.send(embed=embed)
    else: 
        await ctx.author.send("No transaction data for "+token)
    return

bot = commands.Bot(command_prefix='', owner_id=OWNER_DISCORD_ID, help_command=None)

@bot.event
async def on_ready():
    print('We have logged in as {0.user}'.format(bot))
    DiscordComponents(bot)

@bot.command(aliases=['Calculate', 'calc'])
@commands.dm_only()
async def calculate(ctx):
    if checkUserRoles(ctx):
        try:
            message = 'Please enter your public BEP-20 wallet address:\n'
            await ctx.author.send(message)

            def check_message_2(msg):
                return msg.author == ctx.author and len(msg.content) > 0

            try:
                wallet_address = await bot.wait_for("message", check=check_message_2, timeout = 30) # 30 seconds to reply
            except asyncio.TimeoutError:
                await ctx.send("Sorry, you either didn't reply with your wallet address or didn't reply in time!")
                return
				
            await calculateProfits(ctx, 'SurgeUSLS', wallet_address.content)
            #@todo give the user the option to pick another token without asking them for their wallet again
            return
        except discord.NotFound:
            return # not sure what to do here...
        except asyncio.TimeoutError:
            await ctx.author.send("Sorry, you didn't reply in time!")
            await message.delete()
            return
        except Exception as e:
            #addErrorToLog(e, wallet_address.content)
            err_msg = str(e)+" : "+wallet_address.content
            logging.error(err_msg)
            await ctx.author.send("Sorry, something went wrong, please try again later.")
            return
    else:
        await ctx.author.send("You are not authorized to use this bot.")

# @bot.command(aliases=['Calculate_manual', 'calc_manual'])
# @commands.dm_only()
# async def calculate_manual(ctx, token, wallet_address):
#     if checkUserRoles(ctx):
#         if token in surge_tokens:
#             await calculateProfits(ctx, token, wallet_address)
#             return
#         else:
#             await ctx.author.send("That is not a valid Surge token. Please type !list to see available tokens to calculate.")
#             return
#     else:
#         await ctx.author.send("You are not authorized to use this bot.")

# @calculate_manual.error
# async def on_command_error(ctx, error):
#     if isinstance(error, commands.MissingRequiredArgument):
#         await ctx.author.send("I did not get the required details for this request. A proper request looks like this !calculate_manual *token* *wallet_address*")

# @bot.command(aliases=['Remove_daily'])
# @commands.dm_only()
# async def remove_daily(ctx):
#     with open(ROOT_PATH+"/daily_report_list.json", "r") as daily_report_list_json:
#         daily_report_list = json.load(daily_report_list_json)
    
#     if str(ctx.author.id) in daily_report_list:
#         daily_report_list.pop(str(ctx.author.id))
#         with open(ROOT_PATH+"/daily_report_list.json", "w") as daily_report_list_json:
#             json.dump(daily_report_list, daily_report_list_json)

#         await ctx.author.send("You have been removed from the daily report.")
#     else:
#         await ctx.author.send("You are not in the daily report list.")

#     return

# @bot.command(aliases=['List'])
# @commands.dm_only()
# async def list(ctx):
#     message = 'Here are a list of available tokens to calculate: \n'
#     message += ' >>> '
#     for token in surge_tokens:
#         message += token+"\n"
#     await ctx.author.send(message)

@bot.command(aliases=['Help'])
@commands.dm_only()
async def help(ctx):
    help_embed = createCustomHelpEmbedMessage()
    await ctx.author.send(embed=help_embed)

# start owner commands only
# @bot.command(aliases=['Restart'])
# @commands.is_owner()
# @commands.dm_only()
# async def restart(ctx):
#     await ctx.author.send("Bot is restarting")
#     os.system("pm2 restart SurgeProfitTrackerBot --interpreter python3")

#     return

bot.run(SURGE_PROFIT_TRACKER_BOT_KEY)