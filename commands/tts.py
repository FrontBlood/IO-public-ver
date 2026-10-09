import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass

import discord
import edge_tts
from discord.ext import commands

LOGGER = logging.getLogger(__name__)
DEFAULT_VOICE = os.getenv("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
MAX_TEXT_LENGTH = int(os.getenv("TTS_MAX_TEXT_LENGTH", "300"))
IDLE_DISCONNECT_SECONDS = int(os.getenv("TTS_IDLE_DISCONNECT_SECONDS", "120"))
CONNECT_RETRIES = max(1, int(os.getenv("TTS_CONNECT_RETRIES", "3")))
CONNECT_RETRY_DELAY = max(0.1, float(os.getenv("TTS_CONNECT_RETRY_DELAY", "1.5")))
READ1_VOICE = os.getenv("TTS_READ1_VOICE", DEFAULT_VOICE)
READ1_RATE = os.getenv("TTS_READ1_RATE", "-7%")
READ1_PITCH = os.getenv("TTS_READ1_PITCH", "+2Hz")
READ1_VOLUME = os.getenv("TTS_READ1_VOLUME", "+0%")
READ2_VOICE = os.getenv("TTS_READ2_VOICE", DEFAULT_VOICE)
READ2_RATE = os.getenv("TTS_READ2_RATE", "-10%")
READ2_PITCH = os.getenv("TTS_READ2_PITCH", "+3Hz")
READ2_VOLUME = os.getenv("TTS_READ2_VOLUME", "+0%")


@dataclass(slots=True)
class SpeechRequest:
    text: str
    voice_channel: discord.VoiceChannel
    text_channel: discord.abc.Messageable
    voice: str
    rate: str
    pitch: str
    volume: str


class GuildSpeechPlayer:
    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.queue: asyncio.Queue[SpeechRequest] = asyncio.Queue(maxsize=10)
        self.task: asyncio.Task | None = None

    def start(self) -> None:
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        try:
            while True:
                try:
                    request = await asyncio.wait_for(
                        self.queue.get(), timeout=IDLE_DISCONNECT_SECONDS
                    )
                except asyncio.TimeoutError:
                    return
                try:
                    await self._speak(request)
                except Exception:
                    LOGGER.exception("TTS playback failed in guild %s", self.guild_id)
                    await request.text_channel.send("\u274c \u8bed\u97f3\u5408\u6210\u6216\u64ad\u653e\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002")
                finally:
                    self.queue.task_done()
        finally:
            await self._disconnect()

    async def _connect(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        last_error: Exception | None = None

        for attempt in range(CONNECT_RETRIES):
            client = channel.guild.voice_client

            # Discord can leave a stale VoiceClient object behind after a
            # forced disconnect. Never return or move a client that is already
            # disconnected.
            if client is not None and not client.is_connected():
                await self._force_disconnect(client)
                client = None

            try:
                if client is None:
                    return await channel.connect(self_deaf=True)

                if client.channel != channel:
                    if client.is_playing():
                        raise RuntimeError(
                            "voice client is already playing in another channel"
                        )
                    await client.move_to(channel)

                if client.is_connected():
                    return client
                await self._force_disconnect(client)
            except (asyncio.TimeoutError, discord.DiscordException) as error:
                last_error = error
                LOGGER.warning(
                    "Voice connection attempt %s/%s failed in guild %s: %s",
                    attempt + 1,
                    CONNECT_RETRIES,
                    self.guild_id,
                    error,
                )
                if client is not None:
                    await self._force_disconnect(client)

            if attempt + 1 < CONNECT_RETRIES:
                await asyncio.sleep(CONNECT_RETRY_DELAY * (2**attempt))

        raise RuntimeError(
            f"could not connect to voice channel after {CONNECT_RETRIES} attempts"
        ) from last_error

    async def _force_disconnect(self, client: discord.VoiceClient) -> None:
        try:
            await client.disconnect(force=True)
        except (asyncio.TimeoutError, discord.DiscordException):
            LOGGER.debug("Ignoring stale voice disconnect failure", exc_info=True)

    async def _speak(self, request: SpeechRequest) -> None:
        voice_client = await self._connect(request.voice_channel)
        fd, audio_path = tempfile.mkstemp(prefix="relic_tts_", suffix=".mp3")
        os.close(fd)
        source: discord.AudioSource | None = None
        playback_started = False
        try:
            await edge_tts.Communicate(
                request.text,
                request.voice,
                rate=request.rate,
                pitch=request.pitch,
                volume=request.volume,
            ).save(audio_path)
            finished = asyncio.get_running_loop().create_future()

            def after_playback(error: Exception | None) -> None:
                def finish() -> None:
                    if finished.done():
                        return
                    if error:
                        finished.set_exception(error)
                    else:
                        finished.set_result(None)
                self.bot.loop.call_soon_threadsafe(finish)

            # TTS generation can take long enough for Discord to disconnect us.
            # Reconnect immediately before constructing/starting FFmpeg.
            if not voice_client.is_connected():
                voice_client = await self._connect(request.voice_channel)
            source = discord.FFmpegPCMAudio(audio_path)
            voice_client.play(source, after=after_playback)
            playback_started = True
            await finished
        finally:
            # FFmpegPCMAudio starts its process during construction. If play()
            # fails because the connection dropped, stop that process before
            # deleting the input file.
            if source is not None and not playback_started:
                source.cleanup()
            try:
                os.remove(audio_path)
            except FileNotFoundError:
                pass

    async def _disconnect(self) -> None:
        guild = self.bot.get_guild(self.guild_id)
        client = guild.voice_client if guild else None
        if client and client.is_connected():
            await client.disconnect(force=True)


class TextToSpeech(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, GuildSpeechPlayer] = {}

    def cog_unload(self) -> None:
        for player in self.players.values():
            if player.task and not player.task.done():
                player.task.cancel()

    @commands.command(name="\u8bfb1", aliases=["\u6717\u8bfb", "tts"])
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.member)
    async def read_one(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._enqueue(
            ctx, text,
            voice=READ1_VOICE, rate=READ1_RATE,
            pitch=READ1_PITCH, volume=READ1_VOLUME,
            command_name="\u8bfb1",
        )

    @commands.command(name="\u8bfb2")
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.member)
    async def read_two(self, ctx: commands.Context, *, text: str = "") -> None:
        await self._enqueue(
            ctx, text,
            voice=READ2_VOICE, rate=READ2_RATE,
            pitch=READ2_PITCH, volume=READ2_VOLUME,
            command_name="\u8bfb2",
        )

    async def _enqueue(
        self,
        ctx: commands.Context,
        text: str,
        *,
        voice: str,
        rate: str,
        pitch: str,
        volume: str,
        command_name: str,
    ) -> None:
        if not text.strip():
            await ctx.send(
                f"\u7528\u6cd5\uff1a`&{command_name} \u8981\u8bf4\u7684\u5185\u5bb9`"
            )
            return
        if len(text) > MAX_TEXT_LENGTH:
            await ctx.send(f"\u274c \u5185\u5bb9\u8fc7\u957f\uff0c\u8bf7\u9650\u5236\u5728 {MAX_TEXT_LENGTH} \u4e2a\u5b57\u7b26\u4ee5\u5185\u3002")
            return

        channel = ctx.author.voice.channel if ctx.author.voice else None
        if not isinstance(channel, discord.VoiceChannel):
            await ctx.send("\u274c \u8bf7\u5148\u52a0\u5165\u4e00\u4e2a\u8bed\u97f3\u9891\u9053\u3002")
            return

        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.connect or not permissions.speak:
            await ctx.send("\u274c \u6211\u6ca1\u6709\u8fde\u63a5\u6216\u8bf4\u8bdd\u6743\u9650\u3002")
            return

        player = self.players.setdefault(
            ctx.guild.id, GuildSpeechPlayer(self.bot, ctx.guild.id)
        )
        try:
            player.queue.put_nowait(
                SpeechRequest(
                    text=text.strip(),
                    voice_channel=channel,
                    text_channel=ctx.channel,
                    voice=voice,
                    rate=rate,
                    pitch=pitch,
                    volume=volume,
                )
            )
        except asyncio.QueueFull:
            await ctx.send("\u274c \u5f53\u524d\u6717\u8bfb\u961f\u5217\u5df2\u6ee1\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002")
            return

        player.start()
        position = player.queue.qsize()
        await ctx.message.add_reaction("\U0001f50a")
        if position > 1:
            await ctx.send(f"\U0001f50a \u5df2\u52a0\u5165\u961f\u5217\uff0c\u524d\u9762\u8fd8\u6709 {position - 1} \u6761\u3002")

    @read_one.error
    async def read_one_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        await self._handle_command_error(ctx, error)

    @read_two.error
    async def read_two_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        await self._handle_command_error(ctx, error)

    async def _handle_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"\u23f3 \u8bf7\u5728 {error.retry_after:.1f} \u79d2\u540e\u518d\u8bd5\u3002")
            return
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("\u274c \u8be5\u6307\u4ee4\u53ea\u80fd\u5728\u670d\u52a1\u5668\u5185\u4f7f\u7528\u3002")
            return
        raise error


def setup(bot: commands.Bot) -> None:
    @bot.listen("on_ready")
    async def _load_tts_cog() -> None:
        if bot.get_cog("TextToSpeech") is None:
            await bot.add_cog(TextToSpeech(bot))
