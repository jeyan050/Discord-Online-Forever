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

# --- CONFIG ---
status = "online"
custom_status = "discord.gg/duelarena - 100b monthly giveaways!"

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print(f"{Fore.RED}[-] No token provided.")
    sys.exit()

# --- GLOBAL STATE ---
sequence = None
session_id = None
last_heartbeat_ack = True

# --- VALIDATE TOKEN ---
headers = {"Authorization": TOKEN, "Content-Type": "application/json"}
res = requests.get("https://canary.discordapp.com/api/v9/users/@me", headers=headers)

if res.status_code != 200:
    print(f"{Fore.RED}[-] Invalid token.")
    sys.exit()

user = res.json()
print(f"{Fore.GREEN}[+] Logged in as {user['username']} ({user['id']})")

# --- HEARTBEAT ---
async def heartbeat_loop(ws, interval):
    global sequence, last_heartbeat_ack

    try:
        while True:
            await asyncio.sleep(interval)

            if not last_heartbeat_ack:
                print(f"{Fore.RED}[!] Missed heartbeat ACK. Reconnecting...")
                await ws.close()
                return

            last_heartbeat_ack = False

            await ws.send(json.dumps({
                "op": 1,
                "d": sequence
            }))
    except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
        pass

# --- RECEIVER ---
async def receiver(ws):
    global sequence, session_id, last_heartbeat_ack

    async for message in ws:
        data = json.loads(message)

        # Track sequence
        if data.get("s") is not None:
            sequence = data["s"]

        op = data.get("op")
        t = data.get("t")

        # READY → store session
        if t == "READY":
            session_id = data["d"]["session_id"]
            print(f"{Fore.GREEN}[+] Session established")

        # RESUMED
        if t == "RESUMED":
            print(f"{Fore.GREEN}[+] Session resumed")

        # Heartbeat ACK
        if op == 11:
            last_heartbeat_ack = True

        # Reconnect request
        if op == 7:
            print(f"{Fore.YELLOW}[!] Server requested reconnect")
            await ws.close()

        # Invalid session
        if op == 9:
            print(f"{Fore.RED}[!] Invalid session")
            session_id = None
            await asyncio.sleep(2)
            await ws.close()

# --- CONNECTION ---
async def connect():
    global session_id, sequence

    async with websockets.connect(
        "wss://gateway.discord.gg/?v=9&encoding=json",
        max_size=None
    ) as ws:

        # HELLO
        hello = json.loads(await ws.recv())
        interval = hello["d"]["heartbeat_interval"] / 1000

        # RESUME or IDENTIFY
        if session_id and sequence is not None:
            payload = {
                "op": 6,
                "d": {
                    "token": TOKEN,
                    "session_id": session_id,
                    "seq": sequence
                }
            }
            print(f"{Fore.CYAN}[+] Attempting RESUME")
        else:
            payload = {
                "op": 2,
                "d": {
                    "token": TOKEN,
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
            print(f"{Fore.CYAN}[+] IDENTIFY")

        await ws.send(json.dumps(payload))

        # Run tasks
        hb = asyncio.create_task(heartbeat_loop(ws, interval))
        recv = asyncio.create_task(receiver(ws))

        done, pending = await asyncio.wait(
            [hb, recv],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining
        for task in pending:
            task.cancel()

        for task in done:
            try:
                await task
            except:
                pass

# --- MAIN LOOP ---
async def main():
    while True:
        try:
            await connect()
        except Exception as e:
            print(f"{Fore.RED}[!] Error: {e}")
        
        print(f"{Fore.YELLOW}[*] Reconnecting in 5s...\n")
        await asyncio.sleep(5)

# --- RUN ---
keep_alive()
asyncio.run(main())
