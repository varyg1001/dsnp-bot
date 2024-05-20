from __future__ import annotations

from types import SimpleNamespace
from typing import Optional, Any
import re

from aiogram import types
import aiohttp


async def edit_text(sent_message: types.Message, message: str) -> None:
    await sent_message.edit_text(
        message,
        parse_mode="html",
        disable_web_page_preview=True,
    )


class Data:
    TITLE_RE: list = [
        r"^https?://(?:www\.)?(?:preview\.)?(?P<site>disneyplus|starplus)\.com(?:/[a-z0-9-]+){,2}/(?P<type>movies|series)(?:/[a-zA-Z0-9%_-]+)?/(?P<id>[a-zA-Z0-9]{12})",
        r"^https?://(?:www\.)?dsny\.pl/library/[a-zA-Z]{2}(?:/[a-zA-Z]{2})?/(?P<id>[a-zA-Z0-9]{12})",
    ]

    def __init__(self, args, message, bot) -> None:
        self.bot = bot

        self.args: SimpleNamespace = args
        self.id: Optional[str] = self.get_id(self.args.url)
        if not self.disneysite:
            self._regions = ["AR", "BO", "BR", "CL", "CO", "CR", "DO", "EC", "GT", "HN", "MX", "NI", "PA", "PE", "PY", "SV", "UY", "VE"]
        self.quality: str = args.quality
        self.subtitles: Optional[set[str]] = self.args_to_set(args.slang)
        self.audios: Optional[set[str]] = self.args_to_set(args.alang)
        self.message = message
        self.regions_in: Optional[list[str]] = (
            args.regions.split(",") if args.regions else None
        )
        self.seasons_in: Optional[list[int]] = self.seasons_to_list(args.seasons)
        self.mlang: Optional[str] = args.mlang

        self.seasons: dict[str, str] = dict()
        self.regions_all: list[str] = list()
        self.regions: list[str] = list()
        self.change: int = 0
        self.header: str = ""
        self.last_message: str = ""
        self.checked = [0, 0]
        self.progress_string: str = ""

        self.advandec = self.subtitles or self.audios or False
        self.all = (self.subtitles and self.audios) or False

    def seasons_to_list(self, args: str) -> Optional[list[int]]:
        if not args:
            return None
        elif "-" in args:
            start, end = args.split("-")
            return [int(start), int(end) + 1]
        else:
            return [int(args), int(args) + 1]

    def args_to_set(self, args: str) -> Optional[set[str]]:
        return set(args.split(",")) if args else None

    def get_id(self, url):
        id: Optional[str] = None
        for regex in self.TITLE_RE:
            if m := re.search(regex, url):
                if id:
                    # More than one match
                    id = None
                    break
                self.series: bool = m.group("type") == "series"
                self.disneysite: bool = m.group("site") == "disneyplus"
                id = m.group("id")
                break

        if hasattr(self, "disneysite"):
            self.bot.logging.error("Failed to url!")

        return id

    def generate_progress_bar(self, value, maximum):
        filled_length: float = 10 * value / maximum
        filled_char: str = "━"
        end_char: str = "╸"
        empty_char: str = " "
        bar: str = ""

        if filled_length % 1 >= 0.5:
            bar = f"{filled_char * int(filled_length)}{end_char + empty_char * (9 - int(filled_length))}"
        else:
            bar = f"{filled_char * int(filled_length)}{empty_char * (10 - int(filled_length))}"

        return "<code>[" + bar + "]</code>"

    @property
    def render(self) -> str:
        if self.checked[0] != self.checked[1]:
            front: str = f"🕐 Checking regions...   {self.generate_progress_bar(self.checked[0], self.checked[1])}   {self.checked[0]}/{self.checked[1]} ({self.checked[0]/self.checked[1]:.0%})\n\n{self.header}\n\n"
        else:
            front = f"✅ Checked {self.checked[0]} (100%)\n\n{self.header}\n\n"

        available: str = f"Available in {len(self.regions)} regions\n\n"

        def get_sub(num, size):
            if self.advandec:
                return ", ".join(
                    x
                    for x in [
                        f"{num[0]}/{size}"
                        if self.all or (self.audios and not self.subtitles)
                        else "",
                        f"{num[1]}/{size} - full"
                        if self.all or (not self.audios and self.subtitles)
                        else "",
                        f"{num[2]}/{size} - forced"
                        if num[2] != 0
                        and (self.all or (not self.audios and self.subtitles))
                        else "",
                    ]
                    if x
                )
            else:
                return size

        if self.series:
            seasons = sorted(self.seasons.items(), key=lambda x: x[1][2])

            return (
                front
                + available
                + "\n".join(
                    [
                        (
                            f"<code>{', '.join(season[1][0])}</code>  –  "
                            + f'{",  ".join(f"<b>{x[0]}</b> ({get_sub(x[2], x[1])})" for x in season[1][1])}'
                        )
                        for season in seasons
                    ]
                )
            )
        else:
            return front + available + f"<code><b>{', '.join(self.regions)}</b></code>"

    def add(self, region: str) -> None:
        self.regions.append(region)
        self.change += 1

    async def get_lang(self, session, region, id):
        async with session.get(
            f"https://disney.content.edge.bamgrid.com/svc/content/DmcEpisodes/version/5.1/region/{region}/audience/k-false,l-true/maturity/1899/language/en/seasonId/{id}/pageSize/-1/page/1"
        ) as req:
            audio: int = 0
            forced: int = 0
            sub: int = 0
            data_full = (
                (await req.json())
                .get("data", {})
                .get("DmcEpisodes", {})
                .get("videos", {})
            )
            if data_full:
                for video in data_full:
                    video_data = video["mediaMetadata"]
                    quality: str = video_data["format"]
                    audios: set[str] = set(
                        (
                            x["language"]
                            if "-" not in x["language"]
                            else x["language"].split("-")[0]
                        )
                        for x in video_data["audioTracks"]
                    )
                    subtitles: set[str] = set(
                        (
                            x["language"]
                            if "-" not in x["language"]
                            else x["language"].split("-")[0]
                        )
                        for x in video_data["captions"]
                        if x["trackType"] in ("NORMAL", "SDH")
                    )
                    subtitles_forced: set[str] = set(
                        x["language"]
                        for x in video_data["captions"]
                        if x["trackType"] == "FORCED"
                    )
                    if self.quality and self.quality.upper() != quality:
                        continue
                    if self.audios and self.audios.issubset(audios):
                        audio += 1
                    if self.subtitles and self.subtitles.issubset(subtitles):
                        sub += 1
                    if self.subtitles and self.subtitles.issubset(subtitles_forced):
                        forced += 1
            return (audio, sub, forced)

    async def get_data(self, regions: list[str], session: Any) -> None:
        if self.regions_in:
            regions = self.regions_in
        self.checked[1] = len(regions)

        for n, region in enumerate(regions, start=1):
            self.checked[0] = n
            region = region.upper()
            async with session.get(
                "https://{site}.content.edge.bamgrid.com/svc/content/{type}/version/5.1/region/{region}/audience/k-false,l-true/maturity/1899/language/en/encoded{encoded}/{id}".format(
                    type=["DmcVideoBundle", "DmcSeriesBundle"][self.series],
                    site=["star", "disney"][self.disneysite],
                    region=region,
                    encoded=["FamilyId", "SeriesId"][self.series],
                    id=self.id,
                )
            ) as req:
                subtitles = set()
                subtitles_forced: set[str] = set()

                if self.series:
                    try:
                        data_full = (
                            (await req.json())
                            .get("data", {})
                            .get("DmcSeriesBundle", {})
                        )
                        if data := data_full.get("seasons", {}).get("seasons", []):
                            self.regions_all.append(region)
                            self.regions.append(region)
                            if not self.header:
                                title = data_full["episodes"]["videos"][0]["text"][
                                    "title"
                                ]
                                self.header = f'<a href="https://{["starplus", "disneyplus"][self.disneysite]}.com/series/{title["slug"]["series"]["default"]["content"]}/{self.id}">{title["full"]["series"]["default"]["content"]}</a>'
                            eps: list = [
                                (
                                    x["seasonSequenceNumber"],
                                    x["episodes_meta"]["hits"],
                                    await self.get_lang(session, region, x["seasonId"]),
                                )
                                for x in data
                                if not self.seasons_in
                                or x["seasonSequenceNumber"]
                                in range(self.seasons_in[0], self.seasons_in[1])
                            ]
                            if eps:
                                if str(eps) in self.seasons.keys():
                                    self.seasons[str(eps)][0].append(region)
                                else:
                                    self.seasons[str(eps)] = (
                                        [region],
                                        eps,
                                        sum(x[1] for x in eps),
                                    )
                            self.change += 1
                    except Exception as e:
                        self.bot.logging.error(f"Failed to get series info: {e}")

                else:
                    try:
                        data = (
                            (await req.json())
                            .get("data", {})
                            .get("DmcVideoBundle", {})
                            .get("video", {})
                        )
                        if data:
                            self.regions_all.append(region)
                            if not self.header:
                                title = data["text"]["title"]
                                self.header = f'<a href="https://disneyplus.com/movies/{title["slug"]["program"]["default"]["content"]}/{self.id}">{title["full"]["program"]["default"]["content"]}</a>'
                            video_data = data.get("mediaMetadata")
                            quality: str = video_data["format"]
                            audios: set = set(
                                x["language"] for x in video_data["audioTracks"]
                            )
                            subtitles = set(
                                x["language"]
                                for x in video_data["captions"]
                                if x["trackType"] != "FORCED"
                            )
                            subtitles_forced = set(
                                x["language"]
                                for x in video_data["captions"]
                                if x["trackType"] == "FORCED"
                            )
                            if self.quality and self.quality.upper() != quality:
                                continue
                            if self.advandec:
                                if self.subtitles and self.audios:
                                    if (
                                        self.subtitles.issubset(subtitles)
                                        or self.subtitles.issubset(subtitles_forced)
                                    ) and self.audios.issubset(audios):
                                        self.add(region)
                                elif self.subtitles and not self.audios:
                                    if self.subtitles.issubset(
                                        subtitles
                                    ) or self.subtitles.issubset(subtitles_forced):
                                        self.add(region)
                                elif self.audios and not self.subtitles:
                                    if self.audios.issubset(audios):
                                        self.add(region)
                            else:
                                self.change += 1
                                self.regions = self.regions_all

                    except Exception as e:
                        self.bot.logging.error(f"Failed to get series info {e}")
                change_ = 6 if self.series else 11
                if (
                    self.change == 1 or self.change > change_ or region == regions[-1].upper()
                ) and self.regions:
                    message: str = self.render
                    if message != self.last_message:
                        await edit_text(self.message, message)
                        self.change = 2
                        self.last_message = message


class DisneyPlus:
    def __init__(self, bot) -> None:
        self.session = None
        self.bot = bot
        self._regions: list[str] = list()

    async def init_session(self, bot) -> None:
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                "sec-ch-ua": '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            }
        )

        self._regions = ["AD", "AG", "AI", "AL", "AR", "AS", "AT", "AU", "AW", "BA", "BB", "BE", "BG", "BL", "BM", "BO", "BQ", "BR", "BS", "BZ", "CA", "CC", "CH", "CK", "CL", "CO", "CR", "CW", "CX", "CZ", "DE", "DK", "DM", "DO", "EC", "EE", "ES", "FI", "FK", "FO", "FR", "GB", "GD", "GF", "GG", "GI", "GL", "GP", "GR", "GS", "GT", "GU", "GY", "HK", "HN", "HR", "HT", "HU", "IE", "IM", "IO", "IS", "IT", "JE", "JM", "JP", "KN", "KR", "KY", "LC", "LI", "LT", "LU", "LV", "MC", "ME", "MF", "MH", "MK", "MP", "MQ", "MS", "MT", "MU", "MX", "NC", "NF", "NI", "NL", "NO", "NU", "NZ", "PA", "PE", "PF", "PL", "PM", "PN", "PR", "PT", "PY", "RE", "RO", "RS", "SE", "SG", "SH", "SI", "SJ", "SK", "SM", "SR", "SV", "SX", "TC", "TF", "TK", "TR", "TT", "TW", "UM", "US", "UY", "VA", "VC", "VE", "VG", "VI", "WF", "YT"] # dsnp

        #async with self.session.get(
        #    "https://cdn.registerdisney.go.com/jgc/v9/client/DTCI-DISNEYPLUS.GC.WEB-PROD/configuration/site",
        #) as req:
        #    try:
        #        self._regions = (
        #            (await req.json())
        #            .get("data", {})
        #            .get("compliance", {})
        #            .get("countries", [])
        #        )
        #    except Exception as e:
        #        self.bot.logging.error(f"Failed to get regions {e}")

    @property
    def regions(self) -> list[str]:
        return self._regions

    async def get_redirect_url(self, url):
        async with self.session.get(
            f"https://api.redirect-checker.net/?url={url}"
        ) as req:
            req = await req.json()
            if req.get("result") != "success":
                self.bot.logging.error("Failed to get url!")
            try:
                redirect_url = req["data"][0]["response"]["info"]["redirect_url"]

                return redirect_url
            except Exception:
                self.bot.logging.error("Failed to get url!")


    async def get_available(self, data: Data) -> None:
        await data.get_data(self._regions, self.session)
        if not data.regions:
            await edit_text(data.message, "Not available in any region.")
