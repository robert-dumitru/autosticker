import os
import logging
import random
import asyncio
from io import BytesIO
import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message, Sticker
from PIL import Image

from .util import generate_images
from .cfg import MAX_INPUT_IMAGES

# set this to a higher level if you don't want so many logging messages
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
telebot.logger.setLevel(logging.DEBUG)

bot = AsyncTeleBot(os.getenv("AUTOSTICKER_TG_TOKEN"))
sticker_link_prefix = "https://t.me/addstickers/"


@bot.message_handler(commands=["start", "help"])
async def send_welcome(message: Message) -> None:
    logging.debug(f"Captured start message: {message.text}")
    await bot.reply_to(
        message,
        "Welcome to Autosticker! To get started, send me a sticker pack and I'll generate "
        "suggestions for additional stickers.",
    )


@bot.message_handler(func=lambda message: message.text.startswith(sticker_link_prefix))
async def create_predictions(message: Message) -> None:
    logging.debug(f"Captured prediction request: {message.text}")
    sticker_set = await bot.get_sticker_set(message.text[len(sticker_link_prefix) :])

    async def get_image(sticker: Sticker) -> Image:
        file = await bot.get_file(sticker.file_id)
        file_bytes = await bot.download_file(file.file_path)
        logging.debug(f"Downloaded sticker: {sticker.file_unique_id}")
        return Image.open(BytesIO(file_bytes))

    # select 8 random stickers for cost-cutting reasons
    if len(sticker_set.stickers) <= MAX_INPUT_IMAGES:
        sticker_subset = sticker_set.stickers
    else:
        sticker_subset = random.sample(sticker_set.stickers, MAX_INPUT_IMAGES)

    sticker_images = await asyncio.gather(*map(get_image, sticker_subset))
    new_images = await generate_images(sticker_images)
    logging.debug(f"Got {len(new_images)} predictions")

    async def send_image(image: Image) -> None:
        file = BytesIO()
        file.name = "image.png"
        image.save(file, "PNG")
        file.seek(0)
        await bot.send_photo(message.chat.id, photo=file)

    await asyncio.gather(*map(send_image, new_images))


@bot.message_handler(func=lambda message: True)
async def fallback(message: Message) -> None:
    logging.debug(f"Captured unknown message: f{message.text}")
    await bot.reply_to(
        message, "This command doesn't exist. Please try another command."
    )


asyncio.run(bot.polling())
