from utils import LOGGER
from youtube_search import YoutubeSearch
from contextlib import suppress
from pyrogram.types import Message
from yt_dlp import YoutubeDL
from datetime import datetime
from pyrogram import filters, enums
from config import Config
import asyncio
try:
    from PTN import parse
    PTN_AVAILABLE = True
except ImportError:
    PTN_AVAILABLE = False
    def parse(title):
        return {"title": title}
import re
from utils import (
    add_to_db_playlist, 
    clear_db_playlist, 
    delete_messages, 
    download, 
    get_duration,
    get_admins, 
    is_admin, 
    get_buttons, 
    get_link, 
    import_play_list, 
    is_audio, 
    leave_call, 
    play, 
    play_direct_file,
    chek_the_media,
    join_call,
    sleep,
    bot,
    get_playlist_str, 
    send_playlist, 
    shuffle_playlist, 
    start_stream, 
    stream_from_link, 
    chat_filter,
    c_play,
    is_ytdl_supported,
    get_song_and_artist,
    stream_while_downloading,
    get_file_size_from_message
)
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from pyrogram.errors import (
    MessageIdInvalid, 
    MessageNotModified,
    UserNotParticipant,
    PeerIdInvalid,
    ChannelInvalid
)
from pyrogram import (
    Client, 
    filters
)

admin_filter = filters.create(is_admin) 

@Client.on_message(filters.command(["play", "fplay", f"play@{Config.BOT_USERNAME}", f"fplay@{Config.BOT_USERNAME}"]))
async def play_file_directly(client, message):
    """Play files directly without playlist management"""
    print(f"Command received from {message.from_user.id} in chat type: {message.chat.type}")
    
    with suppress(MessageIdInvalid, MessageNotModified):
        # Fetch the list of admins for the current chat
        admins = await get_admins(message.chat.id)

        # Check if the command is restricted to admins only
        if Config.ADMIN_ONLY:
            # Check if the user is an admin or the message is sent via a channel
            if not (message.from_user is None and message.sender_chat or message.from_user.id in admins):
                # User is not authorized to use the command
                await message.reply("<b>Sorry! You are not authorized ❌</b>", quote=False)
                return
                
        if message.command[0] == "fplay":
            if not (message.from_user is None and message.sender_chat or message.from_user.id in admins):
                k = await message.reply("This command is only for admins.", quote=False)
                await delete_messages([message, k])
                return
                
        msg = await message.reply_text("⚡️ **Checking received input..**", quote=False)
        
        # Handle Telegram media files
        if message.reply_to_message and message.reply_to_message.video:
            await msg.edit("⚡️ **Processing Telegram Video...**")
            m_video = message.reply_to_message.video
            title = m_video.file_name or "Video"
            file_id = m_video.file_id
            unique = f"{datetime.now().strftime('%d-%m-%Y-%H:%M:%S')}_{m_video.file_size}_video"
            
        elif message.reply_to_message and message.reply_to_message.document:
            await msg.edit("⚡️ **Processing Telegram Document...**")
            m_video = message.reply_to_message.document
            if not "video" in m_video.mime_type:
                await msg.edit("The given file is invalid")
                await delete_messages([message, msg])
                return
            title = m_video.file_name or "Document"
            file_id = m_video.file_id
            unique = f"{datetime.now().strftime('%d-%m-%Y-%H:%M:%S')}_{m_video.file_size}_document"
            
        elif message.reply_to_message and message.reply_to_message.audio:
            await msg.edit("⚡️ **Processing Telegram Audio...**")
            m_video = message.reply_to_message.audio
            if m_video.title:
                title = m_video.title
                if m_video.performer:
                    title = f"{m_video.performer} - {title}"
            else:
                title = m_video.file_name or "Audio"
            file_id = m_video.file_id
            unique = f"{datetime.now().strftime('%d-%m-%Y-%H:%M:%S')}_{m_video.file_size}_audio"
            
        # Handle YouTube links and search queries
        elif message.reply_to_message and message.reply_to_message.text:
            query = message.reply_to_message.text
            await handle_youtube_or_search(query, msg, message)
            return
            
        elif " " in message.text:
            text = message.text.split(" ", 1)
            query = text[1]
            await handle_youtube_or_search(query, msg, message)
            return
            
        else:
            await msg.edit("<b>❌You didn't give me anything to play.</b>")
            await delete_messages([message, msg])
            return

        # Process Telegram media file using new streaming-while-downloading approach
        try:
            await msg.edit("🚀 **Starting streaming-while-downloading...**")
            
            # Get file size for better progress tracking
            file_size = await get_file_size_from_message(message, file_id)
            if file_size:
                size_mb = file_size / (1024 * 1024)
                await msg.edit(f"🚀 **Starting streaming-while-downloading...**\n\n📊 **File size:** {size_mb:.1f} MB")
            
            # Use the new streaming approach with file size info
            success = await stream_while_downloading(file_id, title, file_size)
            
            if success:
                await msg.edit(f"✅ **Now streaming: {title}**\n\n💡 **Tip:** The file is downloading in the background while streaming!")
                # Clean up message after a delay
                await asyncio.sleep(5)
                await msg.delete()
            else:
                await msg.edit("❌ **Failed to start streaming**")
                await delete_messages([message, msg])
                
        except Exception as e:
            LOGGER.error(f"Error processing file: {e}", exc_info=True)
            await msg.edit(f"❌ **Error: {str(e)}**")
            await delete_messages([message, msg])


async def handle_youtube_or_search(query, msg, message):
    """Handle YouTube links and search queries"""
    try:
        # Spotify Track Handling
        if "spotify.com/track" in query:
            try:
                song_name, artist_name = get_song_and_artist(query)
                query = f"{song_name} {artist_name}"
            except Exception as e:
                await msg.edit(f"<b>❌Set valid Spotify API credentials in the config to play tracks</b>")
                await delete_messages([message, msg])
                return

        # Check if it's a YouTube link
        regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
        match = re.match(regex, query)
        
        if match:
            # YouTube link
            await msg.edit("⚡️ **Fetching Video From YouTube...**")
            url = query
            ydl_opts = {
                "quiet": True,
                "geo-bypass": True,
                "nocheckcertificate": True,
                "no_warnings": True,
                "cookiefile": Config.YT_COOKIES_PATH,
            }
            ydl = YoutubeDL(ydl_opts)
            
            try:
                info = ydl.extract_info(url, False)
                title = info["title"]
                if info['duration'] is None:
                    await msg.edit("<b>❌This is a live stream, use /stream command.</b>")
                    await delete_messages([message, msg])
                    return
                    
                # Download and play YouTube video
                await msg.edit("⚡️ **Downloading YouTube Video...**")
                file_path = await download_youtube_video(url, title)
                if file_path:
                    success = await play_direct_file(file_path, title)
                    if success:
                        await msg.edit(f"✅ **Now playing: {title}**")
                        await asyncio.sleep(3)
                        await msg.delete()
                    else:
                        await msg.edit("❌ **Failed to play YouTube video**")
                        await delete_messages([message, msg])
                else:
                    await msg.edit("❌ **Failed to download YouTube video**")
                    await delete_messages([message, msg])
                    
            except Exception as e:
                LOGGER.error(f"YouTube download error: {e}", exc_info=True)
                await msg.edit(f"❌ **YouTube Error: {str(e)}**")
                await delete_messages([message, msg])
                
        elif query.startswith("http"):
            # Direct URL
            try:
                has_audio_ = await is_audio(query)
            except:
                has_audio_ = False
                LOGGER.error("Unable to get Audio properties within time.")
                
            if has_audio_:
                try:
                    dur = await get_duration(query)
                except:
                    dur = 0
                if dur == 0:
                    await msg.edit("<b>❌This is a live stream, use /stream command.</b>")
                    await delete_messages([message, msg])
                    return 
                    
                # Play direct URL
                await msg.edit("⚡️ **Processing Direct URL...**")
                success = await play_direct_url(query, "Direct Stream")
                if success:
                    await msg.edit("✅ **Now playing direct URL**")
                    await asyncio.sleep(3)
                    await msg.delete()
                else:
                    await msg.edit("❌ **Failed to play direct URL**")
                    await delete_messages([message, msg])
            else:
                if is_ytdl_supported(query):
                    # YTDL supported URL
                    await msg.edit("⚡️ **Processing YTDL URL...**")
                    file_path = await download_ytdl_url(query)
                    if file_path:
                        success = await play_direct_file(file_path, "YTDL Stream")
                        if success:
                            await msg.edit("✅ **Now playing YTDL stream**")
                            await asyncio.sleep(3)
                            await msg.delete()
                        else:
                            await msg.edit("❌ **Failed to play YTDL stream**")
                            await delete_messages([message, msg])
                    else:
                        await msg.edit("❌ **Failed to download YTDL stream**")
                        await delete_messages([message, msg])
                else:
                    await msg.edit("<b>Invalid link ❌</b>")
                    await delete_messages([message, msg])
        else:
            # YouTube search query
            try:
                await msg.edit("⚡️ **Searching YouTube...**")
                results = YoutubeSearch(query, max_results=1).to_dict()
                url = f"https://youtube.com{results[0]['url_suffix']}"
                title = results[0]["title"][:40]
                
                # Download and play searched video
                await msg.edit("⚡️ **Downloading Searched Video...**")
                file_path = await download_youtube_video(url, title)
                if file_path:
                    success = await play_direct_file(file_path, title)
                    if success:
                        await msg.edit(f"✅ **Now playing: {title}**")
                        await asyncio.sleep(3)
                        await msg.delete()
                    else:
                        await msg.edit("❌ **Failed to play searched video**")
                        await delete_messages([message, msg])
                else:
                    await msg.edit("❌ **Failed to download searched video**")
                    await delete_messages([message, msg])
                    
            except Exception as e:
                await msg.edit("<b>Song not found.\nTry inline mode...</b>")
                LOGGER.error(str(e), exc_info=True)
                await delete_messages([message, msg])
                
    except Exception as e:
        LOGGER.error(f"Error in handle_youtube_or_search: {e}", exc_info=True)
        await msg.edit(f"❌ **Error: {str(e)}**")
        await delete_messages([message, msg])


async def download_youtube_video(url, title):
    """Download YouTube video and return file path"""
    try:
        ydl_opts = {
            "quiet": True,
            "geo-bypass": True,
            "nocheckcertificate": True,
            "no_warnings": True,
            "cookiefile": Config.YT_COOKIES_PATH,
            "outtmpl": f"./downloads/%(title)s.%(ext)s"
        }
        ydl = YoutubeDL(ydl_opts)
        info = ydl.extract_info(url, False)
        file_path = ydl.download([url])
        return file_path
    except Exception as e:
        LOGGER.error(f"YouTube download error: {e}", exc_info=True)
        return None


async def download_ytdl_url(url):
    """Download YTDL supported URL and return file path"""
    try:
        ydl_opts = {
            "quiet": True,
            "geo-bypass": True,
            "nocheckcertificate": True,
            "no_warnings": True,
            "outtmpl": f"./downloads/%(title)s.%(ext)s"
        }
        ydl = YoutubeDL(ydl_opts)
        info = ydl.extract_info(url, False)
        file_path = ydl.download([url])
        return file_path
    except Exception as e:
        LOGGER.error(f"YTDL download error: {e}", exc_info=True)
        return None


async def play_direct_url(url, title):
    """Play direct URL without downloading"""
    try:
        # Get media info
        link, seek, pic, width, height = await chek_the_media(url, title=title)
        if not link:
            LOGGER.warning("Unsupported URL format")
            return False
            
        # Join call and play
        await sleep(1)
        if Config.STREAM_LINK:
            Config.STREAM_LINK = False
            
        LOGGER.info(f"STARTING PLAYING: {title}")
        await join_call(link, seek, pic, width, height)
        return True
        
    except Exception as e:
        LOGGER.error(f"Error playing direct URL: {e}", exc_info=True)
        return False

@Client.on_message(filters.command(["leave", f"leave@{Config.BOT_USERNAME}"]) & admin_filter & chat_filter)
async def leave_voice_chat(_, m: Message):
    if not Config.CALL_STATUS:        
        k = await m.reply("<b>❌Not joined any voice chat.</b>", quote=False)
        await delete_messages([m, k])
        return
    await leave_call()
    k = await m.reply("<b>⚡️Successfully left voice chat.</b>", quote=False)
    await delete_messages([m, k])

@Client.on_message(filters.command(["shuffle", f"shuffle@{Config.BOT_USERNAME}"]) & admin_filter & chat_filter)
async def shuffle_play_list(client, m: Message):
    if not Config.CALL_STATUS:
        k = await m.reply("<b>❌Not joined any voice chat.</b>", quote=False)
        await delete_messages([m, k])
        return
    else:
        if len(Config.playlist) > 2:
            k = await m.reply_text("✅Playlist shuffled.", quote=False)
            await shuffle_playlist()
            await delete_messages([m, k])            
        else:
            k = await m.reply_text("❌You can't shuffle playlist with less than 3 songs.", quote=False)
            await delete_messages([m, k])

@Client.on_message(filters.command(["clearplaylist", f"clearplaylist@{Config.BOT_USERNAME}"]) & admin_filter & chat_filter)
async def clear_play_list(client, m: Message):
    if not Config.playlist:
        k = await m.reply("<b>❌Playlist is empty 🤷‍♂️</b>", quote=False)  
        await delete_messages([m, k])
        return
    Config.playlist.clear()
    k = await m.reply_text("<b>Music playlist cleared ✅</b>", quote=False)
    await clear_db_playlist(all=True)
    if Config.IS_LOOP and not (Config.YPLAY or Config.CPLAY):
        await start_stream()
    else:
        await leave_call()
    await delete_messages([m, k])

@Client.on_message(filters.command(["cplay", f"cplay@{Config.BOT_USERNAME}"]) & admin_filter & chat_filter)
async def channel_play_list(client, m: Message):
    with suppress(MessageIdInvalid, MessageNotModified):
        k = await m.reply("<b>⚡️Setting up for channel play...</b>", quote=False)
        if " " in m.text:
            you, me = m.text.split(" ", 1)
            if me.startswith("-100"):
                try:
                    me = int(me)
                except:
                    await k.edit("<b>❌Invalid chat id given</b>", quote=False)
                    await delete_messages([m, k])
                    return
                try:
                    await client.get_chat_member(int(me), Config.USER_ID)
                except (ValueError, PeerIdInvalid, ChannelInvalid):
                    LOGGER.error(f"Given channel is private and @{Config.BOT_USERNAME} is not an admin over there.", exc_info=True)
                    await k.edit(f"❌Given channel is private and @{Config.BOT_USERNAME} is not an admin over there. If the channel is not private, please provide the username of the channel.")
                    await delete_messages([m, k])
                    return
                except UserNotParticipant:
                    LOGGER.error("Given channel is private and USER account is not a member of the channel.")
                    await k.edit("❌Given channel is private and USER account is not a member of the channel.")
                    await delete_messages([m, k])
                    return
                except Exception as e:
                    LOGGER.error(f"Errors occurred while getting data about the channel - {e}", exc_info=True)
                    await k.edit(f"❌Something went wrong- {e}")
                    await delete_messages([m, k])
                    return
                await k.edit("⚡️Searching files from channel, this may take some time, depending on the number of files in the channel.")
                st, msg = await c_play(me)
                if st == False:
                    await k.edit(msg)
                else:
                    await k.edit(f"⚡️Successfully added {msg} files to playlist.")
            elif me.startswith("@"):
                me = me.replace("@", "")
                try:
                    chat = await client.get_chat(me)
                except Exception as e:
                    LOGGER.error(f"Errors occurred while fetching info about the channel - {e}", exc_info=True)
                    await k.edit(f"❌Errors occurred while getting data about the channel - {e}")
                    await delete_messages([m, k])
                    return
                await k.edit("⚡️Searching files from channel, this may take some time, depending on the number of files in the channel.")
                st, msg = await c_play(me)
                if st == False:
                    await k.edit(msg)
                    await delete_messages([m, k])
                else:
                    await k.edit(f"⚡️Successfully added {msg} files from {chat.title} to playlist")
                    await delete_messages([m, k])
            else:
                await k.edit("❌The given channel is invalid. For private channels, it should start with -100 and for public channels, it should start with @\nExamples - `/cplay @VCPlayerFiles or /cplay -100125369865\n\nFor private channels, both bot and the USER account should be members of the channel.")
                await delete_messages([m, k])
        else:
            await k.edit("❌You didn't give me any channel. Give me a channel id or username from which I should play files. \nFor private channels, it should start with -100 and for public channels, it should start with @\nExamples - `/cplay @VCPlayerFiles or /cplay -100125369865\n\nFor private channels, both bot and the USER account should be members of the channel.")
            await delete_messages([m, k])

@Client.on_message(filters.command(["yplay", f"yplay@{Config.BOT_USERNAME}"]) & admin_filter & chat_filter)
async def yt_play_list(client, m: Message):
    with suppress(MessageIdInvalid, MessageNotModified):
        if m.reply_to_message is not None and m.reply_to_message.document:
            if m.reply_to_message.document.file_name != "YouTube_PlayList.json":
                k = await m.reply("❌Invalid playlist file given. Use @GetPlayListBot or search for a playlist in @DumpPlaylist to get a playlist file.")
                await delete_messages([m, k])
                return
            ytplaylist = await m.reply_to_message.download()
            status = await m.reply("✅Trying to get details from playlist.", quote=False)
            n = await import_play_list(ytplaylist)
            if not n:
                await status.edit("❌Errors occurred while importing playlist.", quote=False)
                await delete_messages([m, status])
                return
            if Config.SHUFFLE:
                await shuffle_playlist()
            pl = await get_playlist_str()
            if m.chat.type == "private":
                await status.edit(pl, disable_web_page_preview=True, reply_markup=await get_buttons())        
            elif not Config.LOG_GROUP and m.chat.type == "supergroup":
                if Config.msg.get("playlist") is not None:
                    await Config.msg['playlist'].delete()
                Config.msg['playlist'] = await status.edit(pl, disable_web_page_preview=True, reply_markup=await get_buttons())
                await delete_messages([m])
            else:
                await delete_messages([m, status])
        else:
            k = await m.reply("❌No playlist file given. Use @GetPlayListBot or search for a playlist in @DumpPlaylist to get a playlist file.")
            await delete_messages([m, k])

@Client.on_message(filters.command(["stream", f"stream@{Config.BOT_USERNAME}"]) & admin_filter & chat_filter)
async def stream(client, m: Message):
    try:
        with suppress(MessageIdInvalid, MessageNotModified):
            msg = await m.reply("<b>Checking the received input...</b>", quote=False)
            if m.reply_to_message and m.reply_to_message.text:
                link = m.reply_to_message.text
            elif " " in m.text:
                text = m.text.split(" ", 1)
                link = text[1]
            else:
                k = await msg.edit("<b>❌ Provide a link to stream!</b>")
                await delete_messages([m, k])
                return
            regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
            match = re.match(regex, link)
            if match:
                stream_link = await get_link(link)
                if not stream_link:
                    k = await msg.edit("<b>❌ This is an invalid link.</b>")
                    await delete_messages([m, k])
                    return
            else:
                stream_link = link
            try:
                is_audio_ = await is_audio(stream_link)
            except:
                is_audio_ = False
                LOGGER.error("Unable to get Audio properties within time.")
            if not is_audio_:
                k = await msg.edit("<b>❌ This is an invalid link, provide me a direct link or a YouTube link.</b>")
                await delete_messages([m, k])
                return
            try:
                dur = await get_duration(stream_link)
            except:
                dur = 0
            if dur != 0:
                k = await msg.edit("<b>❌ This is not a live stream, use /play command.</b>")
                await delete_messages([m, k])
                return
            k, msg_ = await stream_from_link(stream_link)
            if k == False:
                k = await msg.edit(msg_)
                await delete_messages([m, k])
                return
            if Config.msg.get('player'):
                await Config.msg['player'].delete()
            Config.msg['player'] = await msg.edit(f"<b>🎸 [Streaming]({stream_link}) started.</b>", disable_web_page_preview=True, reply_markup=await get_buttons())
            await delete_messages([m])
    except Exception as e:
        LOGGER.error(f"Error in stream command: {e}", exc_info=True)
        k = await m.reply("<b>❌ An error occurred while processing the stream.</b>", quote=False)
        await delete_messages([m, k])

admincmds = [
    "yplay", "leave", "pause", "resume", "skip", "restart", "volume", "shuffle", 
    "clearplaylist", "export", "import", "update", "replay", "logs", "stream", 
    "fplay", "schedule", "record", "slist", "cancel", "cancelall", "vcpromote", 
    "vcdemote", "refresh", "rtitle", "seek", "vcmute", "unmute",
    f"yplay@{Config.BOT_USERNAME}", f"leave@{Config.BOT_USERNAME}", 
    f"pause@{Config.BOT_USERNAME}", f"resume@{Config.BOT_USERNAME}", 
    f"skip@{Config.BOT_USERNAME}", f"restart@{Config.BOT_USERNAME}", 
    f"volume@{Config.BOT_USERNAME}", f"shuffle@{Config.BOT_USERNAME}", 
    f"clearplaylist@{Config.BOT_USERNAME}", f"export@{Config.BOT_USERNAME}", 
    f"import@{Config.BOT_USERNAME}", f"update@{Config.BOT_USERNAME}", 
    f"replay@{Config.BOT_USERNAME}", f"logs@{Config.BOT_USERNAME}", 
    f"stream@{Config.BOT_USERNAME}", f"fplay@{Config.BOT_USERNAME}", 
    f"schedule@{Config.BOT_USERNAME}", f"record@{Config.BOT_USERNAME}", 
    f"slist@{Config.BOT_USERNAME}", f"cancel@{Config.BOT_USERNAME}", 
    f"cancelall@{Config.BOT_USERNAME}", f"vcpromote@{Config.BOT_USERNAME}", 
    f"vcdemote@{Config.BOT_USERNAME}", f"refresh@{Config.BOT_USERNAME}", 
    f"rtitle@{Config.BOT_USERNAME}", f"seek@{Config.BOT_USERNAME}", 
    f"mute@{Config.BOT_USERNAME}", f"vcunmute@{Config.BOT_USERNAME}"
]

allcmd = ["play", "player", f"play@{Config.BOT_USERNAME}", f"player@{Config.BOT_USERNAME}"] + admincmds

@Client.on_message(filters.command(admincmds) & ~admin_filter & chat_filter)
async def notforu(client, m: Message):
    try:
        k = await client.send_message(
            chat_id=m.chat.id,
            text="<b>Sorry! You are not authorized ❌</b>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton('Join Now ✅', url='https://t.me/ModVip_rm')]
            ])
        )
        await delete_messages([m, k])
    except Exception as e:
        LOGGER.error(f"Error in notforu handler: {e}", exc_info=True)

@Client.on_message(filters.command(allcmd) & filters.group)
async def group_command_handler(client, m: Message):
    try:
        if m.from_user and m.from_user.id in Config.SUDO:
            buttons = [
                [
                    InlineKeyboardButton('⚡️ Change Bot Settings', url='https://github.com/abirxdhack/TelecastBot'),
                ],
                [
                    InlineKeyboardButton('❌ Cancel', callback_data='closesudo'),
                ]
            ]
            await m.reply(
                "⚙️ You are a SUDO user. You can configure bot settings. Would you want to access the source code to make changes?",
                quote=True,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            buttons = [
                [
                    InlineKeyboardButton('⚡️ Make Own Bot', url='https://github.com/abirxdhack/TelecastBot'),
                    InlineKeyboardButton('✅ Join Here', url='https://t.me/ModVip_rm'),
                ]
            ]
            await m.reply(
                "<b>🎶 You can use this bot in this group! To create your own bot, check out the [SOURCE CODE](https://github.com/abirxdhack/TelecastBot) to make your own.</b>",
                quote=True,
                disable_web_page_preview=False,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        await delete_messages([m])
    except Exception as e:
        LOGGER.error(f"Error in group_command_handler: {e}", exc_info=True)
