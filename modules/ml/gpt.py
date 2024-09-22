#import requests
import httpx
import asyncio

history = []
async def process(bot_id, ctx):
    if ctx.author.id == bot_id:
        return
    url = "http://127.0.0.1:5000/v1/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }

    global history

    user_message = ctx.content

    if user_message == ".clear":
        history = []
        await ctx.channel.send("History cleared")
        return

    history.append({"role": "user", "content": user_message})
    data = {
        "mode": "chat-instruct",
        "character": "bocchi",
        "max_tokens": 200,
        "instruction_template": "Llama-v3",
        "temperature": 0.6,
        "messages": history
    }

    async with ctx.channel.typing():
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data, timeout=None)
            assistant_message = response.json()['choices'][0]['message']['content']
            history.append({"role": "assistant", "content": assistant_message})
            print('bocchi says: ' + assistant_message)
            if len(assistant_message) > 0:
                await ctx.channel.send(assistant_message[:2000])
        await asyncio.sleep(1)
