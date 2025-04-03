from __future__ import annotations

import argparse
import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from disney import DisneyPlus, Data
from config import token, users, groups


API_TOKEN = token
USERS = users
GROUPS = groups

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class MyArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_message = ""

    def error(self, message):
        self.error_message = message

    def parse_args(self, *args, **kwargs):
        # Catch SystemExit exception to prevent closing the application
        try:
            return super().parse_args(*args, **kwargs)
        except SystemExit:
            return None


async def log(commands, message: Message):
    group_name = message.chat.title
    from_user = message.from_user

    if group_name:
        logging.info(f"Group: {group_name}")
    if from_user:
        logging.info(f"User: {from_user.username or from_user.first_name}")

    logging.info(f"Commands: {commands}")


async def eligible(commands, message: Message):
    await log(commands, message)

    if message.chat.id in GROUPS or message.from_user.id in USERS:
        return True
    else:
        await message.reply("You are not eligible to use this bot!")
        return False


@dp.message(Command("start"))
async def send_welcome(message: Message):
    """Handles `/start` command."""
    logging.info(f"User: {message.from_user.username}")
    logging.info("Commands: start")
    await message.answer(
        "Hi!\nI'm a Disney Plus information grabber bot! "
        "If you want to know which series are available in a specific region, this bot is for you!"
    )


@dp.message(Command("groupid"))
async def send_groupid(message: Message):
    """Sends the group ID to the user."""
    await log("groupid", message)

    await message.answer(
        f"<b>Group ID: <code>{message.chat.id}</code></b>",
        parse_mode="html",
        disable_web_page_preview=True,
    )


@dp.message(Command("userid"))
async def send_userid(message: Message):
    """Sends the user ID to the user."""
    await log("userid", message)

    await message.answer(
        f"<b>Your User ID: <code>{message.from_user.id}</code></b>",
        parse_mode="html",
        disable_web_page_preview=True,
    )


@dp.message(Command("usage", "help"))
async def send_help(message: Message):
    """Handles `/usage` or `/help` command."""
    await log("help", message)

    await message.answer(
        """
<b>Usage:</b>
<code>/check [-r &lt;regions&gt;] [-s &lt;num&gt;] [-q &lt;value&gt;] [-al &lt;lang&gt;] [-sl &lt;lang&gt;] &lt;url&gt;</code>

Finds which regions a movie or series is available in on Disney+.
For TV shows, also returns a list of seasons and the number of matching episodes in each season.

<b>Example:</b>
<code>/check -r us,fr -sl pl -al pl https://www.disneyplus.com/movies/star-wars-attack-of-the-clones-episode-ii/mgpYHGnzZW6N</code>
""",
        parse_mode="html",
        disable_web_page_preview=True,
    )


@dp.message(Command("regions"))
async def send_regions(message: Message):
    """Handles `/regions` command."""
    await log("regions", message)

    await message.answer(
        f"All the available regions ({len(bot.disney.regions)}):\n<code>{', '.join(bot.disney.regions)}</code>",
        parse_mode="html",
    )


@dp.message(Command("check"))
async def send_check(message: Message):
    """Handles `/check` command."""
    if not await eligible("check", message):
        return

    parser = MyArgumentParser(description="DSNPbot", prog="/check")
    parser.add_argument("-sl", "--slang", type=str, default=None)
    parser.add_argument("-al", "--alang", type=str, default=None)
    parser.add_argument("-ml", "--mlang", type=str, default=None)
    parser.add_argument("-r", "--regions", type=str, default=None)
    parser.add_argument("-q", "--quality", type=str, default=None)
    parser.add_argument("-s", "--seasons", type=str, default=None)
    parser.add_argument("url", type=str, default=None)

    message_text: str = message.text or ""
    args = parser.parse_args(message_text.split()[1:])  # Remove "/check" from arguments

    if parser.error_message:
        await message.answer(parser.error_message, disable_web_page_preview=True)
        return

    if args and "http" in args.url:
        if args.quality and args.quality.upper() not in ["SD", "HD", "UHD"]:
            await message.answer("Error: Invalid quality!")
        else:
            logging.info(f"URL: {args.url}")
            sent_message = await message.answer("Checking...")

            if "browse/entity" in args.url:
                await sent_message.edit_text(
                    "Error: Entity URL detected, only old URLs can be used!"
                )
                logging.warning(
                    "Error: Entity URL detected, only old URLs can be used!"
                )
                return

            try:
                data = Data(args, sent_message, bot)
                if data.id:
                    await bot.disney.get_available(data)
                    logging.info(f"Finished: {data.id}")
                else:
                    await sent_message.edit_text("Error: Failed to get title ID!")
                    logging.warning("Error: Failed to get title ID!")
            except Exception as e:
                await sent_message.edit_text(
                    f"Error: {e}", disable_web_page_preview=True
                )
                logging.error(f"Error: {e}")
    else:
        await message.answer("Error: No usable input!")


async def main():
    """Bot startup function."""

    logging.basicConfig(level=logging.INFO)

    logging.info("Starting bot...")
    bot.logging = logging.getLogger("DSNPbot")
    bot.disney = DisneyPlus(bot)
    await bot.disney.init_session(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
