import os
import sys
import json
import asyncio
import platform
import requests
import websockets
from colorama import init, Fore
from keep_alive import keep_alive

init(autoreset=True)

status = "online"  # online/dnd/idle
custom_status = "discord.gg/duelarena - 100b monthly giveaways!"  # Custom Status

usertoken = os.getenv("TOKEN")
if not usertoken:
    print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Please add a token inside Secrets.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

validate = requests.get("https://canary.discordapp.com/api/v9/users/@me", headers=headers)
if validate.status_code != 200:
    print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Your token might be invalid. Please check it again.")
    sys.exit()

userinfo = requests.get("https://canary.discordapp.com/api/v9/users/@me", headers=headers).json()
username = userinfo["username"]
discriminator = userinfo["discriminator"]
userid = userinfo["id"]
session_id = None
seq = None

async def receiver(ws):
    global session_id, seq
    async for message in ws:
        data = json.loads(message)

        # Track sequence number
        if data.get("s") is not None:
            seq = data["s"]

        # READY event → contains session_id
        if data.get("t") == "READY":
            session_id = data["d"]["session_id"]

        # Server requests reconnect
        if data.get("op") == 7:
            await ws.close()
            break

async def heartbeat_loop(ws, interval):
    while True:
        await asyncio.sleep(interval)
        await ws.send(json.dumps({"op": 1, "d": None}))

async def onliner(token, status):
    async with websockets.connect("wss://gateway.discord.gg/?v=9&encoding=json", max_size=None) as ws:
        start = json.loads(await ws.recv())
        # heartbeat = start["d"]["heartbeat_interval"]
        heartbeat_interval = start["d"]["heartbeat_interval"] / 1000

        auth = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {
                    "$os": "Windows 10",
                    "$browser": "Google Chrome",
                    "$device": "Windows",
                },
                "presence": {"status": status, "afk": False},
            },
        }
        await ws.send(json.dumps(auth))

        if session_id:
            payload = {
                "op": 6,  # RESUME
                "d": {
                    "token": token,
                    "session_id": session_id,
                    "seq": seq
                }
            }
        else:
            payload = {
                "op": 2,  # IDENTIFY
                "d": {
                    "token": token,
                    "properties": {
                        "$os": platform.system(),
                        "$browser": "Chrome",
                        "$device": platform.system(),
                    },
                    "presence": {
                        "status": status,
                        "afk": False,
                        "activities": [
                            {
                                "type": 4,
                                "state": custom_status,
                                "name": "Custom Status",
                                "id": "custom"
                            }
                        ]
                    }
                }
            }
        
        await ws.send(json.dumps(payload))

        await asyncio.gather(
            heartbeat_loop(ws, heartbeat_interval),
            receiver(ws)
        )

# async def run_onliner():
#     if platform.system() == "Windows":
#         os.system("cls")
#     else:
#         os.system("clear")
#     print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Logged in as {Fore.LIGHTBLUE_EX}{username} {Fore.WHITE}({userid})!")
#     while True:
#         await onliner(usertoken, status)
#         await asyncio.sleep(50)

async def run_onliner():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")
        print(f"[+] Logged in as {username} ({userid})!")
    
    while True:
        try:
            await onliner(usertoken, status)
        except websockets.exceptions.ConnectionClosedOK:
            print("[*] Discord requested reconnect (1001). Reconnecting immediately...")
            await asyncio.sleep(1)

keep_alive()
asyncio.run(run_onliner())
