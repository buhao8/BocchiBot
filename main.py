import discord
import modules
import importlib
import json
import settings

commands = {}

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        args = message.content[len(settings.get()["prefix"]):].strip().split()
        command = args[0]
        del args[0]

        if command not in commands:
            return

        await commands[command].exec(self, message, args)

def load_configs():
    tmp = {}
    with open('config.json', 'r') as f:
        tmp = json.load(f)

    with open('tokens.json', 'r') as f:
        tokens = json.load(f)
        tmp["tokens"] = tokens

    settings.set(tmp)

def load_commands():
    global commands
    from os.path import dirname, basename, isfile, join
    import glob
    mods = glob.glob(join(join(dirname(__file__), 'modules'), "*.py"))
    files = [basename(f)[:-3] for f in mods if isfile(f) and not f.endswith('__init__.py')]
    for file in files:
        importlib.import_module(f"modules.{file}")
        commands[file] = eval(f'modules.{file}')

if __name__ == '__main__':
    load_configs()
    load_commands()

    intents = discord.Intents.default()
    intents.message_content = True

    client = MyClient(intents=intents)
    client.run(settings.get()["tokens"]["discord"])
