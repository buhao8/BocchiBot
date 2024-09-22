import discord
from discord.ext import commands
import settings
from pprint import pprint
import io
import random
import asyncio

class ML(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def gen_img(self, ctx, *, prompt):
        if not is_owner(ctx.author.id):
            await ctx.reply("You are not in the sudoers file.  This incident will be reported.")
            return
        print("calling api")
        images, seed = await call_api(prompt)
        for node_id in images.keys():
            node_data = images[node_id]
            for image_meta, prompt_id, image in node_data:
                imageio = io.BytesIO(image)
                file = discord.File(imageio, filename=image_meta['filename'])
                await ctx.reply(f'seed={seed} prompt_id={prompt_id}', file=file)

def is_owner(author):
    return author == int(settings.get()["owner"])

from websockets.asyncio.client import connect
import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import httpx
import json
import urllib.request
import urllib.parse

server_address = "192.168.0.174:8188"
#client_id = str(uuid.uuid4())
client_id = "775e1553-91ed-46b2-b85e-c2651f62419e"
#client_id = "3fb14a7c-7ef2-4e0a-b262-4e2bbd40435b"

async def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    #data = json.dumps(p).encode('utf-8')
    #req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    try:
        async with httpx.AsyncClient() as client:
            print(json.dumps(p, indent=4))
            response = await client.post(f'http://{server_address}/prompt', json=p, timeout=None)
    except:
        print("httpx.AsyncClient().post exception in queue_prompt")
        raise
    print(response.text)
    return json.loads(response.text)

async def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    #with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get('http://{}/view?{}'.format(server_address, url_values))
    except:
        print("httpx.AsyncClient().post exception in get_image")
        raise
    return response.content


def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

async def get_images(ws, prompt):
    prompt_id = (await queue_prompt(prompt))['prompt_id']
    output_images = {}
    while True:
        out = await ws.recv()
        if isinstance(out, str):
            print(out)
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        print(json.dumps(node_output, indent=4))
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                image_data = await get_image(image['filename'], image['subfolder'], image['type'])
                images_output.append([image, prompt_id, image_data])
        output_images[node_id] = images_output

    return output_images

async def call_api(input_prompt):
    prompt_text = """
    {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 1,
                "denoise": 1,
                "latent_image": [
                    "5",
                    0
                ],
                "model": [
                    "4",
                    0
                ],
                "negative": [
                    "7",
                    0
                ],
                "positive": [
                    "6",
                    0
                ],
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": 8566257,
                "steps": 20
            }
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "flux1-dev-fp8.safetensors"
            }
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "batch_size": 1,
                "height": 512,
                "width": 512
            }
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [
                    "4",
                    1
                ],
                "text": "masterpiece best quality girl"
            }
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": [
                    "4",
                    1
                ],
                "text": "bad hands, text, watermark"
            }
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [
                    "3",
                    0
                ],
                "vae": [
                    "4",
                    2
                ]
            }
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "ComfyUI",
                "images": [
                    "8",
                    0
                ]
            }
        }
    }
    """

    prompt = json.loads(prompt_text)
    #set the text prompt for our positive CLIPTextEncode
    prompt["6"]["inputs"]["text"] = input_prompt

    #set the seed for our KSampler node
    prompt["3"]["inputs"]["seed"] = random.randint(0, 125081275981579185)
    #prompt["3"]["inputs"]["seed"] = 12230496372440832
    #prompt["3"]["inputs"]["seed"] = 85527259360220103

    #ws = websocket.WebSocket()
    async with connect("ws://{}/ws?clientId={}".format(server_address, client_id)) as ws:
        images = await get_images(ws, prompt)
        return [images, prompt["3"]["inputs"]["seed"]]

async def setup(client):
    await client.add_cog(ML(client))
