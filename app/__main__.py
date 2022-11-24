import os
import random
import asyncio
from io import BytesIO
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, Sticker
from PIL import Image

from .util import generate_images

bot = AsyncTeleBot(os.getenv("AUTOSTICKER_TG_TOKEN"))
sticker_link_prefix = "https://t.me/addstickers/"


@bot.message_handler(commands=["start", "help"])
async def send_welcome(message: Message) -> None:
    await bot.reply_to(message, "Welcome to Autosticker! To get started, send me a sticker pack and I'll generate "
                                "suggestions for additional stickers.")


@bot.message_handler(func=lambda message: message.text.startswith(sticker_link_prefix))
async def create_predictions(message: Message) -> None:
    sticker_set = await bot.get_sticker_set(message.text[len(sticker_link_prefix):])

    async def get_image(sticker: Sticker) -> Image:
        file = await bot.get_file(sticker.file_id)
        file_bytes = await bot.download_file(file.file_path)
        return Image.open(BytesIO(file_bytes))

    sticker_subset = random.sample(sticker_set.stickers, 10)
    sticker_images = await asyncio.gather(*map(get_image, sticker_subset))
    new_images = await generate_images(sticker_images)

    async def send_image(image: Image) -> None:
        file = BytesIO()
        image.save(file, "PNG")
        await bot.send_photo(message.chat.id, file)

    await asyncio.gather(*map(send_image, new_images))


@bot.message_handler(func=lambda message: True)
async def fallback(message: Message) -> None:
    await bot.reply_to(message, "This command doesn't exist. Please try another command.")

asyncio.run(bot.polling())
