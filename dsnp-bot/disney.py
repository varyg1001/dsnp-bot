from __future__ import annotations

from types import SimpleNamespace
from typing import Optional
import re

from aiogram import types
import aiohttp


async def edit_text(sent_message: types.Message, message: str) -> None:
    await sent_message.edit_text(
            message,
            parse_mode="html",
            disable_web_page_preview=True,
        )


class Data():

    TITLE_RE: list = [
        r"^https?://(?:www\.)?(?:preview\.)?disneyplus\.com(?:/[a-z0-9-]+){,2}/(?P<type>movies|series)(?:/[a-zA-Z0-9%_-]+)?/(?P<id>[a-zA-Z0-9]{12})",
        r"^https?://(?:www\.)?dsny\.pl/library/[a-zA-Z]{2}(?:/[a-zA-Z]{2})?/(?P<id>[a-zA-Z0-9]{12})",
    ]

    def __init__(self, args, message) -> None:
        self.args: SimpleNamespace = args
        self.series: bool = True
        self.id: Optional[str] = self.get_id(self.args.url)
        self.quality: str = args.quality
        self.subtitles: Optional[set[str]] = set(args.subtitles.split(",")) if args.subtitles else None
        self.audios: Optional[set[str]] = set(args.audios.split(",")) if args.audios else None
        self.message = message
        print(type(self.message))
        self.regions_in: Optional[list[str]] = args.regions.split(",") if args.regions else None

        self.seasons = dict()
        self.regions_all = list()
        self.regions = list()
        self.change: int = 0
        self.header: str = ""
        self.last_message: str = ""

        self.advandec = self.subtitles or self.audios or False

    def get_id(self, url):
        id: Optional[str] = None
        for regex in self.TITLE_RE:
            if m := re.search(regex, url):
                if id:
                    # More than one match
                    id = None
                    break
                if m.group("type") == "movies":
                    self.series = False
                id = m.group("id")
                break

        return id

    @property
    def render(self) -> str:
        if self.series:
            seasons = sorted(self.seasons.items(), key=lambda x: x[1][2])
            return self.header + "\n".join([
                (f"<code>{', '.join(season[1][0])}</code>  –  {',  '.join(f'<b>{x[0]}</b> ({x[1]})' for x in season[1][1])}") for season in seasons
            ])
        else:
            return self.header + f"<code>{', '.join(self.regions)}</code>  –  ({len(self.regions_all)}{f'/{len(self.regions)}' if self.advandec  else ''})"

    def add(self, region: str) -> None:
        self.regions.append(region)
        self.change += 1

    async def get_series(self, regions: list[str], session: aiohttp.ClientSession, bot) -> None:
        "https://disney.content.edge.bamgrid.com/svc/content/DmcEpisodes/version/5.1/region/HU/audience/k-false,l-true/maturity/1899/language/en/seasonId/55a2a3fd-75bd-4226-bf3f-c2a9b2c9dc67/pageSize/-1/page/1"
        if self.regions_in:
            regions = self.regions_in
        for region in regions:
            region = region.upper()
            async with session.get("https://disney.content.edge.bamgrid.com/svc/content/{type}/version/5.1/region/{region}/audience/k-false,l-true/maturity/1899/language/en/encoded{encoded}/{id}".format(type=["DmcVideoBundle", "DmcSeriesBundle"][self.series], region=region, encoded=["FamilyId", "SeriesId"][self.series], id=self.id)) as req:
                if self.series:
                    try:
                        data_full = (await req.json()).get("data", {}).get("DmcSeriesBundle", {})
                        if data := data_full.get("seasons", {}).get("seasons", []):
                            self.regions_all.append(region)
                            self.regions.append(region)
                            if not self.header:
                                title = data_full["episodes"]["videos"][0]["text"]["title"]
                                self.header = f'<a href="https://disneyplus.com/series/{title["slug"]["series"]["default"]["content"]}/{self.id}">{title["full"]["series"]["default"]["content"]}</a>\n\n'
                            eps = [(x["seasonSequenceNumber"], x["episodes_meta"]["hits"]) for x in data]
                            if str(eps) in self.seasons.keys():
                                self.seasons[str(eps)][0].append(region)
                            else:
                                self.seasons[str(eps)] = ([region], eps, sum(x[1] for x in eps))
                            self.change += 1
                    except Exception as e:
                        bot.logging.error(f"Failed to get series info {e}")
                else:
                    try:
                        data = (await req.json()).get("data", {}).get("DmcVideoBundle", {}).get("video", {})
                        if data:
                            self.regions_all.append(region)
                            if not self.header:
                                title = data["text"]["title"]
                                self.header = f'<a href="https://disneyplus.com/movies/{title["slug"]["program"]["default"]["content"]}/{self.id}">{title["full"]["program"]["default"]["content"]}</a>\n\n'
                            video_data = data.get("mediaMetadata")
                            quality: str = video_data["format"]
                            audios: set = set(x["language"] for x in video_data["audioTracks"])
                            subtitles: set = set(x["language"] for x in video_data["captions"] if x["trackType"] not in "FORCED")
                            if self.quality and self.quality.upper() != quality:
                                continue
                            if self.advandec:
                                if self.subtitles and self.audios:
                                    if self.subtitles.issubset(subtitles) and self.audios.issubset(audios):
                                        self.add(region)
                                elif self.subtitles and not self.audios:
                                    if self.subtitles.issubset(subtitles):
                                        self.add(region)
                                elif self.audios and not self.subtitles:
                                    if self.audios.issubset(audios):
                                        self.add(region)
                            else:
                                self.change += 1
                                self.regions = self.regions_all

                    except Exception as e:
                        bot.logging.error(f"Failed to get series info {e}")

                if (self.change == 1 or self.change > 6 or region == regions[-1].upper()) and self.regions:
                    message: str = self.render
                    if message != self.last_message:
                        await edit_text(self.message, message)
                        self.change = 2
                        self.last_message = message


class DisneyPlus():

    def __init__(self, bot) -> None:
        self.session
        self.bot = bot
        self._regions = list()

    async def init_session(self, bot) -> None:
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                "sec-ch-ua": '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
        )

        async with self.session.get("https://cdn.registerdisney.go.com/jgc/v8/client/DTCI-DISNEYPLUS.GC.WEB-PROD/configuration/site") as req:
            try:
                self._regions = (await req.json()).get("data", {}).get("compliance", {}).get("countries", [])
            except Exception as e:
                self.bot.logging.error(f"Failed to get regions {e}")

    @property
    def regions(self) -> list[str]:
        return self._regions

    async def get_available(self, data: Data) -> None:
        await data.get_series(self._regions, self.session, self.bot)
        if not data.regions:
            await edit_text(data.message, "Not available in any region.")
