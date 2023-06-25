from __future__ import annotations

import argparse
import logging

from aiogram import Bot, Dispatcher, executor, types

from disney import DisneyPlus, Data
from config import token

API_TOKEN = token

# Configure logging
logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description='DSNPbot', prog='/check')
parser.add_argument(
    '-s', '--subtitles',
    type=str,
    default=None,
)
parser.add_argument(
    '-l', '--meta-lang',
    type=str,
    default=None,
)
parser.add_argument(
    '-a', '--audios',
    type=str,
    default=None,
)
parser.add_argument(
    '-r', '--regions',
    type=str,
    default=None,
)
parser.add_argument(
    '-q', '--quality',
    type=str,
    default=None,
)
parser.add_argument(
    '-season',
    type=str,
    default=None,
)
parser.add_argument(
    "url",
    type=str,
    default=None,
)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/start` or `/help` command
    """
    await message.reply(
        "Hi!\nI'm a Disney Plus information grabber bot! If you want to know which series are available at a specific region, this bot is for you!"
    )


@dp.message_handler(commands=["regions"])
async def send_regions(message: types.Message):
    """
    This handler will be called when user sends `/regions` command
    """
    await message.reply(
        f"All the available regions ({len(bot.disney.regions)}):\n<code>{', '.join(bot.disney.regions)}</code>",
        parse_mode="html",
    )


@dp.message_handler(commands=["check"])
async def send_check(message: types.Message):
    """
    This handler will be called when user sends `/check` command
    """

    try:
        args = message.get_args()
        if args and "http" in args:
            args = parser.parse_args(args.split())
            if args.quality and args.quality.upper() not in ["SD", "HD", "UHD"]:
                await message.reply("Error: Invalid quality!")
            else:
                bot.logging.info(f"URL: {args.url}")
                sent_message: types.Message = await message.reply("Checking...")
                data = Data(args, sent_message)
                if data.id:
                    await bot.disney.get_available(data)
                    bot.logging.info(f"Finished: {data.id}")
                else:
                    await sent_message.edit_text("Error: Failed to get title id!")
                    bot.logging.warning("Error: Failed to get title id!")
        else:
            await message.reply("Error: No usable input!")
    except Exception as e:
        message.reply(e)

if __name__ == '__main__':
    bot.logging = logging.getLogger("DSNPbot")
    bot.disney = DisneyPlus(bot)
    executor.start_polling(dp, on_startup=bot.disney.init_session)
