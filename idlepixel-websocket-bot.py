import asyncio
import os
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import websocket
import random
import sys
from datetime import datetime
from discord import SyncWebhook
import rel
import ssl


def get_env_var(env_var: str) -> str:
    try:
        return os.environ[env_var]
    except KeyError:
        print("Missing environment variable")
        raise


def set_env_consts() -> dict:
    env_const_list = {
        "IP_USERNAME": "",
        "IP_PASSWORD": "",
        "TESTING_HOOK_URL": "",
        "LBT_DISCORD_HOOK_URL": "",
        "DH_DISCORD_HOOK_URL": ""
    }

    for key in env_const_list:
        env_const_list[key] = get_env_var(key)

    return env_const_list


def is_development_mode():
    cl_args = sys.argv
    dev_mode = False

    for arg in cl_args:
        if arg == "-d":
            print("Development mode enabled.")
            dev_mode = True

    return dev_mode


async def get_signature() -> str:
    async with async_playwright() as p:
        browser_type = p.chromium
        browser = await browser_type.launch_persistent_context("persistent_context")
        page = await browser.new_page()

        await page.goto("https://idle-pixel.com/login/")
        await page.locator('[id=id_username]').fill(env_consts["IP_USERNAME"])
        await page.locator('[id=id_password]').fill(env_consts["IP_PASSWORD"])
        await page.locator("[id=login-submit-button]").click()

        page_content = await page.content()
        soup = BeautifulSoup(page_content, 'html.parser')
        script_tag = soup.find("script").text

        sig_plus_wrap = script_tag.split(";", 1)[0]

        signature = sig_plus_wrap.split("'")[1]

        return signature


def on_ws_message(ws, raw_message):
    split_message = raw_message.split("=", 1)
    if len(split_message) > 1:
        [message_type, message_data] = split_message
    else:
        message_type = raw_message
        message_data = ""

    if message_type == "SET_ITEMS":
        if development_mode:
            print(f"{message_type}: {message_data}")
    elif message_type == "CHAT":
        on_chat(message_data)
    elif message_type == "YELL":
        on_yell(message_data)
    elif message_type == "CUSTOM":
        on_custom(message_data)
    else:
        print(f"{message_type}: {message_data}")


def on_ws_error(ws, error):
    pass


def on_ws_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_ws_open(ws):
    print("Opened connection")
    ws.send(f"LOGIN={signature}")


def on_chat(data: str):
    data_split = data.split("~")
    message_data = {
        "username": data_split[0],
        "sigil": data_split[1],
        "tag": data_split[2],
        "level": data_split[3],
        "message": data_split[4].replace("@", "")
    }

    now = datetime.now()
    current_time = now.strftime("%H:%M")

    formatted_chat = f'*[{current_time}]* **{message_data["username"]}:** {message_data["message"]} '

    log_message(formatted_chat)

    handle_automod(message_data)

    if message_data["message"][0] == "!":
        handle_chat_command(player=message_data["username"], message=message_data["message"])
        if development_mode:
            print(f'Chat command received: {message_data["message"]}')


def handle_automod(data: dict):
    player = data["username"]
    message = data["message"].lower()
    for trigger in automod_flag_words:
        if trigger in message:
            message_string = f"{data['username']} sent a message with the blacklisted word: {trigger}."
            send_modmod_message(payload=message_string, command="MSG", player="ALL")
            length = "24"
            reason = f"Using the word: {trigger}"
            is_ip = "false"
            mute_player(player, length, reason, is_ip)
            send_chat_message(f"{player} has been axed from chat.")
            break


def on_yell(data: str):
    now = datetime.now()
    current_time = now.strftime("%H:%M")

    formatted_chat = f'*[{current_time}]* **SERVER MESSAGE:** {data} '

    log_message(formatted_chat)


def on_custom(data: str):
    [player, data_packet] = data.split("~")

    if data_packet == "PLAYER_OFFLINE":
        handle_player_offline(player)

        callback_id = None
        plugin = None
        command = None
        content = data_packet
    else:
        split_packet = data_packet.split(":", 3)
        callback_id = split_packet[0]
        plugin = split_packet[1]
        command = split_packet[2]

        if len(split_packet) > 3:
            content = split_packet[3]
        else:
            content = None

        if development_mode:
            print(
                f"'{plugin}' received '{command}' command with id '{callback_id}' and content '{content}' from {player}.")

    if plugin == "interactor":
        handle_interactor(player, command, content, callback_id)
    elif plugin == "MODMOD":
        handle_modmod(player, command, content, callback_id)


def handle_chat_command(player: str, message: str):
    reply_string = ""
    reply_needed = False
    split_message = message.split(" ", 1)
    command = split_message[0]
    if len(split_message) > 1:
        payload = split_message[1]
    else:
        payload = None

    if replace_nadebot:
        if command in nadebot_commands:
            reply_string = f"Sorry {player}, " + nadebot_reply
            reply_needed = True

    if command[:7] == "!luxbot":
        if player in whitelisted_accounts:
            try:
                sub_command = command.split(":", 1)[1]
            except KeyError:
                sub_command = None
                reply_string = f"Sorry {player}, that is an invalid LuxBot command format."
                reply_needed = True

            if sub_command == "echo":
                reply_string = f"Echo: {player}: {payload}"
                reply_needed = True
            elif sub_command == "easter":
                reply_string = f"https://greasyfork.org/en/scripts/463496-idlepixel-easter-2023-tracker"
                reply_needed = True
            elif sub_command == "scripts":
                reply_string = f"https://idle-pixel.wiki/index.php/Scripts"
                reply_needed = True
            elif sub_command == "vega":
                vega_links = {
                    "santa": "https://prnt.sc/iLEELtvirILy",
                    "paper": "https://prnt.sc/5Ga3Tsl0oay6",
                    "face": "https://prnt.sc/WbVMwBw63d9g",
                    "attack": "https://prnt.sc/dASKN1prvBJ9",
                    "kitten": "https://prnt.sc/rp_t4eiSGM1h",
                    "hide": "https://prnt.sc/aPvMRNNkbbEE",
                    "beans": "https://prnt.sc/_XCgGFh3jIbv",
                    "borgor": "https://prnt.sc/HwewSCtGlJvM",
                    "banana": "https://prnt.sc/pSs3rVcPlfHE",
                    "gamer": "https://prnt.sc/yEQaV346hY7c",
                    "peer": "https://prnt.sc/LgPFXqfyk3Gi",
                    "axolotl": "https://prnt.sc/ev3f_BkI6CsN",
                    "noodle": "https://prnt.sc/TTYHSPbazWbJ",
                    "reader": "https://prnt.sc/N3oVzhnb3N80",
                    "shutout": "https://prnt.sc/i06Ff5mifQNC",
                }
                if payload is not None:
                    try:
                        reply_string = vega_links[payload]
                    except KeyError:
                        reply_string = "Invalid Vega."
                else:
                    random_vega = random.choice(list(vega_links))
                    reply_string = f"Your random Vega is: {random_vega}: {vega_links[random_vega]}"

                reply_needed = True
            elif sub_command == "import":
                if payload == "antigravity":
                    reply_string = "https://xkcd.com/353"
                    reply_needed = True
            else:
                if sub_command is not None:
                    reply_string = f"Sorry {player}, that is an invalid LuxBot command."
                    reply_needed = True
        elif player in ignore_accounts:
            pass
        else:
            reply_string = f"Sorry {player}, you are not authorized to issue LuxBot commands."
            reply_needed = True

    if reply_needed:
        send_chat_message(reply_string)


def handle_player_offline(player: str):
    if player in online_mods:
        try:
            online_mods.remove(player)
        except ValueError:
            pass
        send_modmod_message(payload=f"{player} has logged out!", command="MSG", player="ALL")


def poll_online_mods():
    send_modmod_message(command="HELLO", player="ALL", payload="0:0")


def mute_player(player: str, length: str, reason: str, is_ip: str):
    # websocket.send("MUTE=" + username_target + "~" + hours + "~" + reason + "~" + is_ip);
    mute_string = f"MUTE={player}~{length}~{reason}~{is_ip}"
    ws.send(f"{mute_string}")


def handle_interactor(player: str, command: str, content: str, callback_id: str):
    interactor_commands = ["echo", "chatecho", "relay", "whitelist", "blacklist", "togglenadebotreply", "nadesreply", "help"]
    if player in whitelisted_accounts:
        if command == "echo":
            send_custom_message(player, content)
        elif command == "chatecho":
            chat_string = f"{player} echo: {content}"
            send_chat_message(chat_string)
        elif command == "relay":
            recipient = content.split(":")[0]
            message = content.split(":")[1]
            send_custom_message(recipient, message)
        elif command == "whitelist":
            whitelisted_accounts.append(content.strip())
            send_custom_message(player, f"{content} has been temporarily whitelisted to issue interactor commands.")
        elif command == "blacklist":
            whitelisted_accounts.remove(content.strip())
            send_custom_message(player, f"{content} has been removed from the interactor whitelist.")
        elif command == "togglenadebotreply":
            global replace_nadebot
            replace_nadebot = not replace_nadebot
            if replace_nadebot:
                status = "on"
            else:
                status = "off"
            send_custom_message(player, f"Nadebot replies are now {status}.")
        elif command == "nadesreply":
            global nadebot_reply
            nadebot_reply = content
            send_custom_message(player, f"New NadeBot reply set. New reply is:")
            send_custom_message(player, f"Sorry <player>, {nadebot_reply}.")
        elif command == "speak":
            send_chat_message(content)
        elif command == "help":
            if content is None:
                help_string = "Command List"
                for com in interactor_commands:
                    help_string += f" | {com}"
                send_custom_message(player, help_string)
                send_custom_message(player, "help:command will give a brief description of the command.")
            elif content == "echo":
                help_string = "Echos message as custom. (echo:message)"
                send_custom_message(player, help_string)
            elif content == "chatecho":
                help_string = "Echos message into chat. (chatecho:message)"
                send_custom_message(player, help_string)
            elif content == "relay":
                help_string = "Passes on message to another account. (relay:account:message)"
                send_custom_message(player, help_string)
            elif content == "whitelist":
                help_string = "Temporarily adds account to whitelist. (whitelist:account)"
                send_custom_message(player, help_string)
                whitelist_string = "Whitelisted accounts"
                for account in whitelisted_accounts:
                    whitelist_string += f" | {account}"
                send_custom_message(player, whitelist_string)
            elif content == "blacklist":
                help_string = "Temporarily removes account from whitelist. (blacklist:account)"
                send_custom_message(player, help_string)
            elif content == "togglenadebotreply":
                help_string = "Toggles bot responses to Nadess bot commands."
                send_custom_message(player, help_string)
            elif content == "nadesreply":
                help_string = "Sets a new reply string for Nadess bot commands. (nadesreply:reply_string) Current string is:"
                send_custom_message(player, help_string)
                send_custom_message(player, f"Sorry <player>, {nadebot_reply}.")
            elif content == "help":
                help_string = "Lists commands or gives a description of a command. (help:command)"
                send_custom_message(player, help_string)
            else:
                help_string = "Invalid help command. Should be of format (help:command)"
                send_custom_message(player, help_string)
        else:
            send_custom_message(player, f"{command} is not a valid interactor command.")
    else:
        send_custom_message(player, "403: Interactor request denied. Account not approved.")


def handle_modmod(player: str, command: str, content: str, callback_id: str):
    online_mods.add(player)
    if command == "HELLO":
        if content == "1:0":
            send_modmod_message(payload=f"{player} has logged in!", command="MSG", player="ALL")
        elif content == "0:0":
            if player == "luxferre":
                poll_online_mods()
    elif command == "MODCHAT":
        send_modmod_message(payload=f"{player}: {content}", command="MSG", player="ALL")
    elif command == "MODLIST":
        mod_string = "Mod accounts online at last poll"
        for mod in online_mods:
            capital_mod = ""
            for word in mod.split(" "):
                capital_mod += f"{word.capitalize()} "
            mod_string += f" | {capital_mod}"
        send_modmod_message(payload=mod_string, command="MSG", player=player)


def send_modmod_message(**kwargs):
    payload = kwargs.get("payload", None)
    command = kwargs.get("command", None)
    player = kwargs.get("player", None)
    message = f"MODMOD:{command}:{payload}"
    if player == "ALL":
        for account in online_mods.copy():
            send_custom_message(account, message)
    else:
        send_custom_message(player, message)


def send_custom_message(player: str, content: str):
    custom_string = f"CUSTOM={player}~{content}"
    ws.send(f"{custom_string}")


def send_chat_message(chat_string: str):
    chat_string = f"CHAT={chat_string}"
    ws.send(chat_string)


def log_message(message: str):
    if development_mode:
        testing_webhook.send(message)

        with open('chat.log', 'a', encoding="utf-8") as the_file:
            the_file.write(message + '\n')
    else:
        dh_webhook.send(message)
        lbt_webhook.send(message)


if __name__ == "__main__":
    env_consts = set_env_consts()
    development_mode = is_development_mode()
    online_mods = set()
    whitelisted_accounts = ["lux", "axe", "luxferre", "luxchatter", "godofnades", "amyjane1991"]
    ignore_accounts = ["flymanry"]
    nadebot_commands = ["!bigbone", "!combat", "!dhm", "!dho", "!event", "!rocket", "!wiki", "!xp", "!help"]
    automod_flag_words = ["nigger", "nigga", "niga", "fag", "chink", "beaner", ]

    nadebot_reply = "Nades's  bot is offline atm."

    replace_nadebot = False

    lbt_webhook = SyncWebhook.from_url(env_consts["LBT_DISCORD_HOOK_URL"])
    dh_webhook = SyncWebhook.from_url(env_consts["DH_DISCORD_HOOK_URL"])
    if development_mode:
        testing_webhook = SyncWebhook.from_url(env_consts["TESTING_HOOK_URL"])

    signature = asyncio.run(get_signature())
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp("wss://server1.idle-pixel.com",
                                on_open=on_ws_open,
                                on_message=on_ws_message,
                                on_error=on_ws_error,
                                on_close=on_ws_close)

    ws.run_forever(dispatcher=rel,
                   reconnect=5,
                   sslopt={"cert_reqs": ssl.CERT_NONE})  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly, no SSL cert
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
