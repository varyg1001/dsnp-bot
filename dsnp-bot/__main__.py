from __future__ import annotations

import argparse
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, executor, types

from disney import DisneyPlus, Data
from config import token

class MyArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super(MyArgumentParser, self).__init__(*args, **kwargs)

        self.error_message = ''

    def error(self, message):
        self.error_message = message

    def parse_args(self, *args, **kwargs):
        # catch SystemExit exception to prevent closing the application
        result = None
        try:
            result = super().parse_args(*args, **kwargs)
        except SystemExit:
            pass
        return result

API_TOKEN = token

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/start` or `/help` command
    """
    await message.reply(
        "Hi!\nI'm a Disney Plus information grabber bot! If you want to know which series are available at a specific region, this bot is for you!"
    )

@dp.message_handler(commands=["usage", "help"])
async def send_welcome(message: types.Message):
    """
    This handler will be called when user sends `/usage` or `/help` command
    """
    await message.reply(
"""
<b>Usage:</b>
<code>/check [-r &lt;regions&gt;] [-s &lt;num&gt;] [-q &lt;value&gt;] [-al &lt;lang&gt;] [-sl &lt;lang&gt;] &lt;url&gt;</code>

Finds which regions a movie or series is available in on Disney+.
For TV shows, also returns a list of seasons and the number of matching episodes in each season.

<b>Options:</b>
<code>-r </code>/<code> --regions</code>
Comma-separated list of 2-letter country codes to limit the search to. Default is to check all regions.
<code>-s </code>/<code> --season</code>
Limit search to the specified season(s). Default is to check all seasons. (Examples: -s 1, -s 1-2)
<code>-q </code>/<code> --quality</code>
Only show movies/episodes that have the specified quality. Possible values are SD, HD, UHD.
<code>-al </code>/<code> --alang</code>
Only show movies/episodes that have the specified audio track (2-letter language code).
<code>-sl </code>/<code> --slang</code>
Only show movies/episodes that have the specified subtitle track (2-letter language code).

<b>Example:</b>
<code>/check -r hu,en -s hu -a hu https://www.disneyplus.com/hu-hu/series/548-nap-egy-szekta-fogsagaban/7bwY59faYVNN</code>
""",
        parse_mode="html",
        disable_web_page_preview=True,
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

    parser = MyArgumentParser(argparse.ArgumentParser(description='DSNPbot', prog='/check'))
    parser.add_argument(
        '-sl', '--slang',
        type=str,
        default=None,
    )
    parser.add_argument(
        '-al', '--alang',
        type=str,
        default=None,
    )
    parser.add_argument(
        '-ml', '--mlang',
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
        '-s', '--seasons',
        type=str,
        default=None,
    )
    parser.add_argument(
        "url",
        type=str,
        default=None,
    )

    message_in: Optional[str] = message.get_args()
    args = parser.parse_args(message_in.split())
    if parser.error_message:
        await message.reply(parser.error_message, disable_web_page_preview=True)
        del message_in
    elif message_in and "http" in message_in:
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


if __name__ == '__main__':
    bot.logging = logging.getLogger("DSNPbot")
    bot.disney = DisneyPlus(bot)
    executor.start_polling(dp, on_startup=bot.disney.init_session)
