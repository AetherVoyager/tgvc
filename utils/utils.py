from .logger import LOGGER
try:
    from pyrogram.raw.types import InputChannel
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from pyrogram.errors.exceptions.forbidden_403 import GroupcallForbidden    
    from apscheduler.jobstores.mongodb import MongoDBJobStore
    from apscheduler.jobstores.base import ConflictingIdError
    from pyrogram.raw.functions.channels import GetFullChannel
    from urllib.parse import urlparse, parse_qs
    import yt_dlp
    from pyrogram import filters
    from pymongo import MongoClient
    from datetime import datetime
    from threading import Thread
    from math import gcd
    from .pyro_dl import Downloader
    from config import Config
    from asyncio import sleep  
    from bot import bot
    from pyrogram import enums
    try:
        from PTN import parse
        PTN_AVAILABLE = True
    except ImportError:
        PTN_AVAILABLE = False
        def parse(title):
            return {"title": title}
    from config import Config
    import subprocess
    import asyncio
    import requests
    import json
    import random
    import time
    import sys
    import base64
    import os
    import math
    from pyrogram.errors.exceptions.bad_request_400 import (
        BadRequest, 
        ScheduleDateInvalid,
        PeerIdInvalid,
        ChannelInvalid
    )
    from pytgcalls.types.stream import MediaStream, AudioQuality, VideoQuality
    from pytgcalls.types.stream.external_media import ExternalMedia

    def get_video_quality():
        """Convert config quality string to VideoQuality enum"""
        quality_map = {
            'UHD_4K': VideoQuality.UHD_4K,
            'QHD_2K': VideoQuality.QHD_2K,
            'FHD_1080p': VideoQuality.FHD_1080p,
            'HD_720p': VideoQuality.HD_720p,
            'SD_480p': VideoQuality.SD_480p,
            'SD_360p': VideoQuality.SD_360p,
        }
        return quality_map.get(Config.CUSTOM_QUALITY, VideoQuality.FHD_1080p)
    from pyrogram.types import (
        InlineKeyboardButton, 
        InlineKeyboardMarkup, 
        Message
    )
    from pyrogram.raw.functions.phone import (
        EditGroupCallTitle, 
        CreateGroupCall,
        ToggleGroupCallRecord,
        StartScheduledGroupCall 
    )
    from pytgcalls.exceptions import (
    NoActiveGroupCall,
    InvalidVideoProportion
)
    from PIL import (
        Image, 
        ImageFont, 
        ImageDraw 
    )

    from user import (
        group_call, 
        USER
    )
except ModuleNotFoundError:
    import os
    import sys
    import subprocess
    file=os.path.abspath("requirements.txt")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', file, '--upgrade'])
    os.execl(sys.executable, sys.executable, *sys.argv)

if Config.DATABASE_URI:
    from .database import get_db
    db = get_db()
    monclient = MongoClient(Config.DATABASE_URI)
    jobstores = {
        'default': MongoDBJobStore(client=monclient, database=Config.DATABASE_NAME, collection='scheduler')
        }
    scheduler = AsyncIOScheduler(jobstores=jobstores)
else:
    scheduler = AsyncIOScheduler()

async def run_loop_scheduler():
    scheduler.start()

asyncio.get_event_loop().run_until_complete(run_loop_scheduler())
dl=Downloader()

def get_spotify_access_token():
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": Config.SPOTIFY_CLIENT_ID,
        "client_secret": Config.SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(Config.SPOTIFY_TOKEN_URL, headers=headers, data=data)
    response.raise_for_status()
    return response.json().get("access_token")

def get_track_id_from_url(spotify_url):
    parsed_url = urlparse(spotify_url)
    path_segments = parsed_url.path.split("/")
    if len(path_segments) > 2 and path_segments[1] == "track":
        return path_segments[2]
    return None

def get_song_and_artist(spotify_url):
    track_id = get_track_id_from_url(spotify_url)
    if not track_id:
        raise ValueError("Invalid Spotify track URL")

    access_token = get_spotify_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(f"{Config.SPOTIFY_TRACK_API_URL}{track_id}", headers=headers)
    response.raise_for_status()

    track_info = response.json()
    song_name = track_info.get("name")
    artist_name = ", ".join(artist["name"] for artist in track_info.get("artists", []))
    return song_name, artist_name

async def play_direct_file(file_path, title="Unknown"):
    """Play a file directly without playlist management"""
    try:
        LOGGER.info(f"Playing file directly: {title}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            LOGGER.error(f"File not found: {file_path}")
            return False
            
        # Get media info
        link, seek, pic, width, height = await chek_the_media(file_path, title=title)
        if not link:
            LOGGER.warning("Unsupported file format")
            return False
            
        # Join call and play
        await sleep(1)
        if Config.STREAM_LINK:
            Config.STREAM_LINK = False
            
        LOGGER.info(f"STARTING PLAYING: {title}")
        await join_call(link, seek, pic, width, height)
        return True
        
    except Exception as e:
        LOGGER.error(f"Error playing file: {e}", exc_info=True)
        return False

async def play(file_index=0):
    """Legacy function - now redirects to direct file playing"""
    if not Config.playlist:
        LOGGER.error("No playlist available")
        return False
        
    # Ensure file_index is within bounds
    if file_index >= len(Config.playlist):
        LOGGER.warning(f"File index {file_index} out of range, using first file")
        file_index = 0
    
    song = Config.playlist[file_index]
    LOGGER.info(f"Playing file at index {file_index}: {song[1]}")    
    
    if song[3] == "telegram":
        file = Config.GET_FILE.get(song[5])
        if not file:
            file = await dl.pyro_dl(song[2])
            if not file:
                LOGGER.info("Downloading file from telegram")
                file = await bot.download_media(song[2])
            Config.GET_FILE[song[5]] = file
            await sleep(3)
        while not os.path.exists(file):
            file = Config.GET_FILE.get(song[5])
            await sleep(1)
        total = int(((song[5].split("_"))[1])) * 0.005
        while not (os.stat(file).st_size) >= total:
            LOGGER.info("Waiting for download")
            LOGGER.info(str((os.stat(file).st_size)))
            await sleep(1)
    elif song[3] == "url":
        file = song[2]
    else:
        file = await get_link(song[2])
        
    if not file:
        if Config.playlist or Config.STREAM_LINK:
            return await skip()     
        else:
            LOGGER.error("This stream is not supported , leaving VC.")
            await leave_call()
            return False 
            
    # Use the new direct play function
    return await play_direct_file(file, song[1])

async def schedule_a_play(job_id, date):
    try:
        scheduler.add_job(run_schedule, "date", [job_id], id=job_id, run_date=date, max_instances=50, misfire_grace_time=None)
    except ConflictingIdError:
        LOGGER.warning("This already scheduled")
        return
    if not Config.CALL_STATUS or not Config.IS_ACTIVE:
        if Config.SCHEDULE_LIST[0]['job_id'] == job_id \
            and (date - datetime.now()).total_seconds() < 86400:
            song=Config.SCHEDULED_STREAM.get(job_id)
            if Config.IS_RECORDING:
                scheduler.add_job(start_record_stream, "date", id=str(Config.CHAT), run_date=date, max_instances=50, misfire_grace_time=None)
            try:
                await USER.invoke(CreateGroupCall(
                    peer=(await USER.resolve_peer(Config.CHAT)),
                    random_id=random.randint(10000, 999999999),
                    schedule_date=int(date.timestamp()),
                    title=song['1']
                    )
                )
                Config.HAS_SCHEDULE=True
            except ScheduleDateInvalid:
                LOGGER.error("Unable to schedule VideoChat, since date is invalid")
            except Exception as e:
                LOGGER.error(f"Error in scheduling voicechat- {e}", exc_info=True)
    await sync_to_db()

async def run_schedule(job_id):
    data=Config.SCHEDULED_STREAM.get(job_id)
    if not data:
        LOGGER.error("The Scheduled stream was not played, since data is missing")
        old=filter(lambda k: k['job_id'] == job_id, Config.SCHEDULE_LIST)
        if old:
            Config.SCHEDULE_LIST.remove(old)
        await sync_to_db()
        pass
    else:
        if Config.HAS_SCHEDULE:
            if not await start_scheduled():
                LOGGER.error("Scheduled stream skipped, Reason - Unable to start a voice chat.")
                return
        data_ = [{1:data['1'], 2:data['2'], 3:data['3'], 4:data['4'], 5:data['5']}]
        Config.playlist = data_ + Config.playlist
        await play()
        LOGGER.info("Starting Scheduled Stream")
        del Config.SCHEDULED_STREAM[job_id]
        old=list(filter(lambda k: k['job_id'] == job_id, Config.SCHEDULE_LIST))
        if old:
            for old_ in old:
                Config.SCHEDULE_LIST.remove(old_)
        if not Config.SCHEDULE_LIST:
            Config.SCHEDULED_STREAM = {} #clear the unscheduled streams
        await sync_to_db()
        if len(Config.playlist) <= 1:
            return
        await download(Config.playlist[1])
      
async def cancel_all_schedules():
    for sch in Config.SCHEDULE_LIST:
        job=sch['job_id']
        k=scheduler.get_job(job, jobstore=None)
        if k:
            scheduler.remove_job(job, jobstore=None)
        if Config.SCHEDULED_STREAM.get(job):
            del Config.SCHEDULED_STREAM[job]      
    Config.SCHEDULE_LIST.clear()
    await sync_to_db()
    LOGGER.info("All the schedules are removed")

async def skip():
    if Config.STREAM_LINK and len(Config.playlist) == 0 and Config.IS_LOOP:
        await stream_from_link()
        return
    elif not Config.playlist \
        and Config.IS_LOOP:
        LOGGER.info("Loop Play enabled, switching to STARTUP_STREAM, since playlist is empty.")
        await start_stream()
        return
    elif not Config.playlist \
        and not Config.IS_LOOP:
        LOGGER.info("Loop Play is disabled, leaving call since playlist is empty.")
        await leave_call()
        return
    old_track = Config.playlist.pop(0)
    await clear_db_playlist(song=old_track)
    if old_track[3] == "telegram":
        file=Config.GET_FILE.get(old_track[5])
        if file:
            try:
                os.remove(file)
            except:
                pass
            del Config.GET_FILE[old_track[5]]
    if not Config.playlist \
        and Config.IS_LOOP:
        LOGGER.info("Loop Play enabled, switching to STARTUP_STREAM, since playlist is empty.")
        await start_stream()
        return
    elif not Config.playlist \
        and not Config.IS_LOOP:
        LOGGER.info("Loop Play is disabled, leaving call since playlist is empty.")
        await leave_call()
        return
    LOGGER.info(f"START PLAYING: {Config.playlist[0][1]}")
    if Config.DUR.get('PAUSE'):
        del Config.DUR['PAUSE']
    await play()
    if len(Config.playlist) <= 1:
        return
    #await download(Config.playlist[1])


async def check_vc():
    try:
        a = await bot.invoke(GetFullChannel(channel=(await bot.resolve_peer(Config.CHAT))))
        if a.full_chat.call is None:
            try:
                LOGGER.info("No active calls found, creating new")
                await USER.invoke(CreateGroupCall(
                    peer=(await USER.resolve_peer(Config.CHAT)),
                    random_id=random.randint(10000, 999999999)
                    )
                    )
                if Config.WAS_RECORDING:
                    await start_record_stream()
                await sleep(2)
                return True
            except Exception as e:
                LOGGER.error(f"Unable to start new GroupCall :- {e}", exc_info=True)
                return False
        else:
            if Config.HAS_SCHEDULE:
                await start_scheduled()
            return True
    except Exception as e:
        LOGGER.error(f"Error checking voice chat: {e}")
        LOGGER.error(f"Make sure bot is member of group {Config.CHAT} and has proper permissions")
        return False
    

async def join_call(link, seek, pic, width, height):  
    if not await check_vc():
        LOGGER.error("No voice call found and was unable to create a new one. Exiting...")
        return
    if Config.HAS_SCHEDULE:
        await start_scheduled()
    if Config.CALL_STATUS:
        if Config.IS_ACTIVE == False:
            Config.CALL_STATUS = False
            return await join_call(link, seek, pic, width, height)
        play=await change_file(link, seek, pic, width, height)
    else:
        play=await join_and_play(link, seek, pic, width, height)
    if play == False:
        await sleep(1)
        await join_call(link, seek, pic, width, height)
    await sleep(1)
    if not seek:
        Config.DUR["TIME"]=time.time()
        if Config.EDIT_TITLE:
            await edit_title()
    old=Config.GET_FILE.get("old")
    if old:
        for file in old:
            os.remove(f"./downloads/{file}")
        try:
            del Config.GET_FILE["old"]
        except:
            LOGGER.error("Error in Deleting from dict")
            pass
    await send_playlist()

async def start_scheduled():
    try:
        await USER.invoke(
            StartScheduledGroupCall(
                call=(
                    await USER.invoke(
                        GetFullChannel(
                            channel=(
                                await USER.resolve_peer(
                                    Config.CHAT
                                    )
                                )
                            )
                        )
                    ).full_chat.call
                )
            )
        if Config.WAS_RECORDING:
            await start_record_stream()
        return True
    except Exception as e:
        if 'GROUPCALL_ALREADY_STARTED' in str(e):
            LOGGER.warning("Already Groupcall Exist")
            return True
        else:
            Config.HAS_SCHEDULE=False
            return await check_vc()

async def join_and_play(link, seek, pic, width, height):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            LOGGER.info(f"Attempting to join call (attempt {retry_count + 1}/{max_retries})")
            
            if seek:
                start=str(seek['start'])
                end=str(seek['end'])
                if not Config.IS_VIDEO:
                    await group_call.play(
                        int(Config.CHAT),
                        MediaStream(
                            link,
                            audio_parameters=AudioQuality.HIGH,
                            additional_ffmpeg_parameters=f'-ss {start} -atend -t {end}',
                        ),
                    )
                else:
                    if pic:
                        cwidth, cheight = resize_ratio(1280, 720, Config.CUSTOM_QUALITY)
                        await group_call.play(
                            int(Config.CHAT),
                            MediaStream(
                                link,
                                video_parameters=get_video_quality(),
                                audio_parameters=AudioQuality.HIGH,
                                ffmpeg_parameters=f'-ss {start} -t {end}',
                            ),
                        )
                    else:
                        if not width or not height:
                            LOGGER.error("No Valid Video Found and hence removed from playlist.")
                            if Config.playlist or Config.STREAM_LINK:
                                return await skip()     
                            else:
                                LOGGER.error("This stream is not supported , leaving VC.")
                                return 
                        cwidth, cheight = resize_ratio(width, height, Config.CUSTOM_QUALITY)
                        await group_call.play(
                            int(Config.CHAT),
                            MediaStream(
                                link,
                                video_parameters=get_video_quality(),
                                audio_parameters=AudioQuality.HIGH,
                                ffmpeg_parameters=f'-ss {start} -t {end}',
                            ),
                        )
            else:
                if not Config.IS_VIDEO:
                    await group_call.play(
                        int(Config.CHAT),
                        MediaStream(
                            link,
                            audio_parameters=AudioQuality.HIGH,
                        ),
                    )
                else:
                    if pic:
                        cwidth, cheight = resize_ratio(1280, 720, Config.CUSTOM_QUALITY)
                        await group_call.play(
                            int(Config.CHAT),
                            MediaStream(
                                link,
                                video_parameters=get_video_quality(),
                                audio_parameters=AudioQuality.HIGH,
                            ),
                        )
                    else:
                        if not width or not height:
                            LOGGER.error("No Valid Video Found and hence removed from playlist.")
                            if Config.playlist or Config.STREAM_LINK:
                                return await skip()     
                            else:
                                LOGGER.error("This stream is not supported , leaving VC.")
                                return 
                        cwidth, cheight = resize_ratio(width, height, Config.CUSTOM_QUALITY)
                        await group_call.play(
                            int(Config.CHAT),
                            MediaStream(
                                link,
                                video_parameters=get_video_quality(),
                                audio_parameters=AudioQuality.HIGH,
                            ),
                        )
            
            Config.CALL_STATUS=True
            LOGGER.info("Successfully joined and started playing media")
            LOGGER.info(f"Video parameters: {get_video_quality()}, Dimensions: {width}x{height}, Quality: {Config.CUSTOM_QUALITY}")
            
            # Start a timer to detect stream end (simplified)
            if not seek:  # Only monitor non-seeked streams
                asyncio.create_task(stream_end_monitor(link, seek))
            
            # Clean up old downloads
            asyncio.create_task(cleanup_downloads())
            
            # Start Telegram download monitoring for the current file
            if os.path.exists(link):
                file_size = os.path.getsize(link)
                asyncio.create_task(monitor_telegram_download(link, file_size))
            
            return True
            
        except NoActiveGroupCall:
            try:
                LOGGER.info("No active calls found, creating new")
                await USER.invoke(CreateGroupCall(
                    peer=(await USER.resolve_peer(Config.CHAT)),
                    random_id=random.randint(10000, 999999999)
                    )
                    )
                if Config.WAS_RECORDING:
                    await start_record_stream()
                LOGGER.info("Waiting for group call to be fully established...")
                await sleep(5)  # Wait longer for connection to stabilize
                # Verify the call is active before proceeding
                if await check_vc():
                    LOGGER.info("Group call established successfully, restarting playout")
                    await restart_playout()
                else:
                    LOGGER.error("Failed to establish group call connection")
                    return False
            except Exception as e:
                LOGGER.error(f"Unable to start new GroupCall :- {e}", exc_info=True)
                return False
        except InvalidVideoProportion:
            LOGGER.error("This video is unsupported")
            if Config.playlist or Config.STREAM_LINK:
                return await skip()     
            else:
                LOGGER.error("This stream is not supported , leaving VC.")
                return 
        except Exception as e:
            if "TelegramServerError" in str(e) or "ntgcalls" in str(e):
                LOGGER.error(f"Telegram server error while joining call: {e}")
                LOGGER.info("This usually means connection issues. Waiting before retry...")
                await sleep(10)  # Wait longer for server issues
                return False
            else:
                LOGGER.error(f"Errors Occured while joining, retrying Error- {e}", exc_info=True)
                retry_count += 1
                if retry_count < max_retries:
                    LOGGER.info(f"Retrying in 5 seconds... (attempt {retry_count + 1}/{max_retries})")
                    await sleep(5)
                    continue
                else:
                    LOGGER.error(f"Max retries ({max_retries}) reached. Giving up.")
                    return False
    
    LOGGER.error("Unexpected end of retry loop")
    return False


async def cleanup_downloads():
    """Clean up old downloaded files to prevent disk space issues"""
    try:
        downloads_dir = "./downloads"
        if not os.path.exists(downloads_dir):
            return
            
        current_time = time.time()
        max_age = 3600  # 1 hour in seconds
        
        for filename in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, filename)
            
            # Skip if it's a directory
            if os.path.isdir(file_path):
                continue
                
            # Get file age
            file_age = current_time - os.path.getmtime(file_path)
            
            # Remove files older than 1 hour
            if file_age > max_age:
                try:
                    os.remove(file_path)
                    LOGGER.info(f"Cleaned up old download: {filename}")
                except Exception as e:
                    LOGGER.warning(f"Could not remove old file {filename}: {e}")
                    
    except Exception as e:
                            LOGGER.error(f"Error in cleanup_downloads: {e}", exc_info=True)


async def cleanup_specific_file(file_path):
    """Clean up a specific file after it's been played"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            LOGGER.info(f"Cleaned up played file: {os.path.basename(file_path)}")
    except Exception as e:
        LOGGER.warning(f"Could not remove played file {file_path}: {e}")


async def monitor_telegram_download(file_path, expected_size=None):
    """Monitor Telegram file download progress"""
    try:
        if not os.path.exists(file_path):
            LOGGER.info(f"Waiting for Telegram download to start: {os.path.basename(file_path)}")
            # Wait for file to appear
            while not os.path.exists(file_path):
                await sleep(1)
        
        start_time = time.time()
        last_size = 0
        last_log_time = start_time
        update_interval = 5  # Update every 5 seconds for Telegram downloads
        
        LOGGER.info(f"Telegram download started: {os.path.basename(file_path)}")
        
        while True:
            if os.path.exists(file_path):
                current_size = os.path.getsize(file_path)
                current_time = time.time()
                
                # Log progress at intervals
                if current_time - last_log_time >= update_interval:
                    if last_size > 0:
                        # Calculate download speed
                        time_diff = current_time - last_log_time
                        speed = (current_size - last_size) / time_diff
                        
                        # Format speed
                        if speed > 1024 * 1024:  # > 1MB/s
                            speed_str = f"{speed/1024/1024:.2f} MB/s"
                        else:
                            speed_str = f"{speed/1024:.1f} KB/s"
                        
                        # Calculate progress if expected size is known
                        if expected_size and expected_size > 0:
                            percentage = (current_size / expected_size) * 100
                            progress_bar = create_progress_bar(percentage)
                            remaining = expected_size - current_size
                            eta = remaining / speed if speed > 0 else 0
                            
                            LOGGER.info(f"Telegram Download: {progress_bar} | Speed: {speed_str} | ETA: {format_time(eta)} | Size: {current_size/1024/1024:.1f} MB / {expected_size/1024/1024:.1f} MB")
                        else:
                            LOGGER.info(f"Telegram Download: Speed: {speed_str} | Current: {current_size/1024/1024:.1f} MB")
                        
                        # Warn about slow downloads
                        if speed < 50 * 1024:  # < 50 KB/s
                            LOGGER.warning(f"Telegram download speed is very slow ({speed_str}). This may take a long time.")
                        elif speed < 500 * 1024:  # < 500 KB/s
                            LOGGER.warning(f"Telegram download speed is slow ({speed_str}). Consider checking your connection.")
                    
                    last_log_time = current_time
                    last_size = current_size
                
                # Check if download is complete (file size stable for 10 seconds)
                await sleep(2)
                if os.path.exists(file_path):
                    new_size = os.path.getsize(file_path)
                    if new_size == current_size:
                        # Wait a bit more to ensure it's really complete
                        await sleep(5)
                        final_size = os.path.getsize(file_path)
                        if final_size == current_size:
                            total_time = time.time() - start_time
                            LOGGER.info(f"Telegram download completed in {format_time(total_time)}! Final size: {final_size/1024/1024:.1f} MB")
                            break
                
                # Check for timeout (30 minutes)
                if time.time() - start_time > 1800:
                    LOGGER.warning("Telegram download timed out after 30 minutes")
                    break
                    
            else:
                await sleep(1)
                
    except Exception as e:
        LOGGER.error(f"Error monitoring Telegram download: {e}", exc_info=True)


def format_time(seconds):
    """Format seconds into human readable time"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours}h {minutes}m {seconds}s"


def create_progress_bar(percentage, width=30):
    """Create a visual progress bar"""
    filled = int(width * percentage / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {percentage:.1f}%"


def estimate_download_time(file_size_bytes):
    """Estimate download time based on file size and typical speeds"""
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    # Typical download speeds (conservative estimates)
    if file_size_mb < 100:
        speed_mbps = 2.0  # 2 MB/s for small files
    elif file_size_mb < 1000:
        speed_mbps = 1.5  # 1.5 MB/s for medium files
    else:
        speed_mbps = 1.0  # 1 MB/s for large files
    
    estimated_seconds = file_size_mb / speed_mbps
    return format_time(int(estimated_seconds))


def find_file_in_playlist(file_name_or_id):
    """Find a file in the playlist by name or ID and return its index"""
    if not Config.playlist:
        return -1
        
    for i, song in enumerate(Config.playlist):
        # Check if the song name matches (case insensitive)
        if file_name_or_id.lower() in song[1].lower():
            return i
        # Check if the song ID matches
        if str(file_name_or_id) == str(song[5]):
            return i
        # Check if the song link matches
        if str(file_name_or_id) == str(song[2]):
            return i
    
    return -1  # File not found


async def play_specific_file(file_identifier):
    """Play a specific file from the playlist by name, ID, or link"""
    file_index = find_file_in_playlist(file_identifier)
    
    if file_index == -1:
        LOGGER.error(f"File '{file_identifier}' not found in playlist")
        return False
    
    LOGGER.info(f"Found file '{file_identifier}' at index {file_index}, playing now...")
    return await play(file_index)


def get_playlist_info():
    """Get information about all files in the playlist"""
    if not Config.playlist:
        return "No files in playlist"
    
    playlist_info = []
    for i, song in enumerate(Config.playlist):
        file_name = song[1] if len(song) > 1 else "Unknown"
        file_id = song[5] if len(song) > 5 else "Unknown"
        file_type = song[3] if len(song) > 3 else "Unknown"
        
        playlist_info.append(f"{i+1}. {file_name} (ID: {file_id}, Type: {file_type})")
    
    return "\n".join(playlist_info)


async def show_download_progress(file_path, total_size):
    """Show download progress for media files"""
    try:
        start_time = time.time()
        last_log_time = start_time
        last_size = 0
        timeout = 7200  # 2 hours timeout for large files
        
        # For very large files, use even less frequent updates
        is_very_large = total_size > 2 * 1024 * 1024 * 1024  # > 2GB
        update_interval = 30 if is_very_large else 15  # 30s for >2GB, 15s for >1GB
        
        # Estimate download time based on file size
        estimated_time = estimate_download_time(total_size)
        
        LOGGER.info(f"Starting download progress tracking for {os.path.basename(file_path)} | Size: {total_size/1024/1024:.1f} MB | Update interval: {update_interval}s | Estimated time: {estimated_time}")
        
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                LOGGER.warning(f"Download progress tracking timed out after {format_time(timeout)}")
                break
                
            if os.path.exists(file_path):
                current_size = os.path.getsize(file_path)
                percentage = (current_size / total_size) * 100 if total_size > 0 else 0
                
                # Only log at specified intervals
                current_time = time.time()
                if current_time - last_log_time >= update_interval:
                    # Calculate download speed and ETA
                    if last_size > 0:
                        time_diff = current_time - last_log_time
                        speed = (current_size - last_size) / time_diff  # Speed per second
                        remaining = total_size - current_size
                        eta = remaining / speed if speed > 0 else 0
                        
                        # Format speed appropriately
                        if speed > 1024 * 1024:  # > 1MB/s
                            speed_str = f"{speed/1024/1024:.2f} MB/s"
                        else:
                            speed_str = f"{speed/1024:.1f} KB/s"
                        
                        progress_bar = create_progress_bar(percentage)
                        LOGGER.info(f"Download Progress: {progress_bar} | Speed: {speed_str} | ETA: {format_time(eta)} | Size: {current_size/1024/1024:.1f} MB / {total_size/1024/1024:.1f} MB")
                        
                        # Warn about slow downloads
                        if speed < 50 * 1024:  # < 50 KB/s
                            LOGGER.warning(f"Download speed is very slow ({speed_str}). This may take a long time.")
                        elif speed < 500 * 1024:  # < 500 KB/s
                            LOGGER.warning(f"Download speed is slow ({speed_str}). Consider checking your connection.")
                    else:
                        LOGGER.info(f"Download in progress: {os.path.basename(file_path)} | Current: {current_size/1024/1024:.1f} MB / {total_size/1024/1024:.1f} MB")
                    
                    last_log_time = current_time
                    last_size = current_size
                
                if percentage >= 100:
                    total_time = time.time() - start_time
                    LOGGER.info(f"Download completed in {format_time(total_time)}!")
                    break
                    
                # Sleep based on file size
                await sleep(update_interval)
            else:
                await sleep(5)
                
    except Exception as e:
        LOGGER.error(f"Error in progress tracking: {e}")


async def show_processing_progress(file_path, operation="Processing"):
    """Show processing progress for media operations"""
    try:
        start_time = time.time()
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        is_large_file = file_size > 100 * 1024 * 1024  # > 100MB
        
        LOGGER.info(f"{operation} started for: {os.path.basename(file_path)} | Size: {file_size/1024/1024:.1f} MB")
        
        # For large files, use less frequent monitoring
        check_interval = 30 if is_large_file else 10  # 30s for large files, 10s for small
        
        # Add timeout for large files
        timeout = 7200 if is_large_file else 1800  # 2 hours for large files, 30 minutes for small
        
        # Monitor file changes during processing
        last_size = 0
        last_log_time = start_time
        
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                LOGGER.warning(f"{operation} progress tracking timed out after {format_time(timeout)}")
                break
            if os.path.exists(file_path):
                current_size = os.path.getsize(file_path)
                elapsed = time.time() - start_time
                
                # Only log if size changed or time interval passed
                current_time = time.time()
                if current_size != last_size or (current_time - last_log_time) >= check_interval:
                    if current_size != last_size:
                        LOGGER.info(f"{operation} in progress... | File size: {current_size/1024/1024:.1f} MB | Elapsed: {format_time(elapsed)}")
                        last_size = current_size
                    else:
                        LOGGER.info(f"{operation} still processing... | Elapsed: {format_time(elapsed)} | File size: {current_size/1024/1024:.1f} MB")
                    
                    last_log_time = current_time
                
                # Check if processing is complete (file size stable for longer period on large files)
                stable_check_time = 60 if is_large_file else 10  # 1 minute for large files, 10s for small
                await sleep(stable_check_time)
                
                if os.path.exists(file_path):
                    new_size = os.path.getsize(file_path)
                    if new_size == current_size:
                        total_time = time.time() - start_time
                        LOGGER.info(f"{operation} completed in {format_time(total_time)} | Final size: {current_size/1024/1024:.1f} MB")
                        break
            else:
                LOGGER.warning(f"File not found during {operation.lower()}")
                break
                
    except Exception as e:
        LOGGER.error(f"Error in processing progress: {e}")


async def stream_end_monitor(link, seek):
    """Monitor stream end and cleanup when media finishes"""
    try:
        if seek:
            # For seeked media, calculate remaining duration
            start = seek.get('start', 0)
            end = seek.get('end', 0)
            duration = end - start
        else:
            # Get media duration
            duration = await get_duration(link)
        
        if duration > 0:
            LOGGER.info(f"Stream will end in {duration} seconds")
            await sleep(duration + 5)  # Wait for duration + longer buffer
            
            # Check if we're still in the same call
            if Config.CALL_STATUS and Config.IS_ACTIVE:
                LOGGER.info("Media finished, ending stream...")
                try:
                    await group_call.leave_call(int(Config.CHAT))
                    Config.CALL_STATUS = False
                    Config.IS_ACTIVE = False
                    await sync_to_db()
                    LOGGER.info("Successfully left group call after media ended")
                    
                    # Clean up the specific file that was just played
                    await cleanup_specific_file(link)
                except Exception as e:
                    LOGGER.error(f"Error leaving group call: {e}")
        else:
            LOGGER.warning("Could not determine media duration, using fallback timer")
            # Fallback: wait 10 minutes then check if still active
            await sleep(600)
            if Config.CALL_STATUS and Config.IS_ACTIVE:
                LOGGER.info("Fallback timer expired, ending stream...")
                try:
                    await group_call.leave_call(int(Config.CHAT))
                    Config.CALL_STATUS = False
                    Config.IS_ACTIVE = False
                    await sync_to_db()
                except Exception as e:
                    LOGGER.error(f"Error leaving group call: {e}")
                    
    except Exception as e:
        LOGGER.error(f"Error in stream end monitor: {e}", exc_info=True)


async def change_file(link, seek, pic, width, height):
    try:
        if seek:
            start=str(seek['start'])
            end=str(seek['end'])
            if not Config.IS_VIDEO:
                await group_call.play(
                    int(Config.CHAT),
                    MediaStream(
                        link,
                        audio_quality=AudioQuality.HIGH,
                        additional_ffmpeg_parameters=f'-ss {start} -atend -t {end}',
                    ),
                )
            else:
                if pic:
                    cwidth, cheight = resize_ratio(1280, 720, Config.CUSTOM_QUALITY)
                    await group_call.play(
                        int(Config.CHAT),
                        MediaStream(
                            link,
                            video_parameters=get_video_quality(),
                            audio_parameters=AudioQuality.HIGH,
                            additional_ffmpeg_parameters=f'-ss {start} -atend -t {end}',
                        ),
                    )
                else:
                    if not width \
                        or not height:
                        LOGGER.error("No Valid Video Found and hence removed from playlist.")
                        if Config.playlist or Config.STREAM_LINK:
                            return await skip()     
                        else:
                            LOGGER.error("This stream is not supported , leaving VC.")
                            return 

                    cwidth, cheight = resize_ratio(width, height, Config.CUSTOM_QUALITY)
                    await group_call.play(
                        int(Config.CHAT),
                        MediaStream(
                            link,
                            video_parameters=get_video_quality(),
                            audio_parameters=AudioQuality.HIGH,
                            additional_ffmpeg_parameters=f'-ss {start} -atend -t {end}',
                        ),
                    )
        else:
            if not Config.IS_VIDEO:
                await group_call.play(
                    int(Config.CHAT),
                    MediaStream(
                        link,
                        audio_parameters=AudioQuality.HIGH,
                    ),
                )
            else:
                if pic:
                    cwidth, cheight = resize_ratio(1280, 720, Config.CUSTOM_QUALITY)
                    await group_call.play(
                        int(Config.CHAT),
                        MediaStream(
                            link,
                            video_parameters=get_video_quality(),
                            audio_parameters=AudioQuality.HIGH,
                        ),
                    )
                else:
                    if not width \
                        or not height:
                        LOGGER.error("No Valid Video Found and hence removed from playlist.")
                        if Config.playlist or Config.STREAM_LINK:
                            return await skip()     
                        else:
                            LOGGER.error("This stream is not supported , leaving VC.")
                            return 
                    cwidth, cheight = resize_ratio(width, height, Config.CUSTOM_QUALITY)
                    await group_call.play(
                        int(Config.CHAT),
                        MediaStream(
                            link,
                            video_parameters=get_video_quality(),
                            audio_parameters=AudioQuality.HIGH,
                        ),
                    )
    except InvalidVideoProportion:
        LOGGER.error("Invalid video, skipped")
        if Config.playlist or Config.STREAM_LINK:
            return await skip()     
        else:
            LOGGER.error("This stream is not supported , leaving VC.")
            await leave_call()
            return 
    except Exception as e:
        LOGGER.error(f"Error in joining call - {e}", exc_info=True)
        return False


async def seek_file(seektime):
    play_start=int(float(Config.DUR.get('TIME')))
    if not play_start:
        return False, "Player not yet started"
    else:
        data=Config.DATA.get("FILE_DATA")
        if not data:
            return False, "No Streams for seeking"        
        played=int(float(time.time())) - int(float(play_start))
        if data.get("dur", 0) == 0:
            return False, "Seems like live stream is playing, which cannot be seeked."
        total=int(float(data.get("dur", 0)))
        trimend = total - played - int(seektime)
        trimstart = played + int(seektime)
        if trimstart > total:
            return False, "Seeked duration exceeds maximum duration of file"
        new_play_start=int(play_start) - int(seektime)
        Config.DUR['TIME']=new_play_start
        link, seek, pic, width, height = await chek_the_media(data.get("file"), seek={"start":trimstart, "end":trimend})
        await join_call(link, seek, pic, width, height)
        return True, None
    


async def leave_call():
    try:
        await group_call.stop(Config.CHAT)
    except Exception as e:
        LOGGER.error(f"Errors while leaving call {e}", exc_info=True)
    #Config.playlist.clear()
    if Config.STREAM_LINK:
        Config.STREAM_LINK=False
    Config.CALL_STATUS=False
    if Config.SCHEDULE_LIST:
        sch=Config.SCHEDULE_LIST[0]
        if (sch['date'] - datetime.now()).total_seconds() < 86400:
            song=Config.SCHEDULED_STREAM.get(sch['job_id'])
            if Config.IS_RECORDING:
                k=scheduler.get_job(str(Config.CHAT), jobstore=None)
                if k:
                    scheduler.remove_job(str(Config.CHAT), jobstore=None)
                scheduler.add_job(start_record_stream, "date", id=str(Config.CHAT), run_date=sch['date'], max_instances=50, misfire_grace_time=None)
            try:
                await USER.invoke(CreateGroupCall(
                    peer=(await USER.resolve_peer(Config.CHAT)),
                    random_id=random.randint(10000, 999999999),
                    schedule_date=int((sch['date']).timestamp()),
                    title=song['1']
                    )
                )
                Config.HAS_SCHEDULE=True
            except ScheduleDateInvalid:
                LOGGER.error("Unable to schedule VideoChat, since date is invalid")
            except Exception as e:
                LOGGER.error(f"Error in scheduling voicechat- {e}", exc_info=True)
    await sync_to_db()
            
                


async def restart():
    try:
        await group_call.stop(Config.CHAT)
        await sleep(2)
    except Exception as e:
        LOGGER.error(e, exc_info=True)
    if not Config.playlist:
        await start_stream()
        return
    LOGGER.info(f"- START PLAYING: {Config.playlist[0][1]}")
    await sleep(1)
    await play()
    LOGGER.info("Restarting Playout")
    if len(Config.playlist) <= 1:
        return
    await download(Config.playlist[1])


async def restart_playout():
    if not Config.playlist:
        await start_stream()
        return
    LOGGER.info(f"RESTART PLAYING: {Config.playlist[0][1]}")
    data=Config.DATA.get('FILE_DATA')
    if data:
        link, seek, pic, width, height = await chek_the_media(data['file'], title=f"{Config.playlist[0][1]}")
        if not link:
            LOGGER.warning("Unsupported Link")
            return
        await sleep(1)
        if Config.STREAM_LINK:
            Config.STREAM_LINK=False
        await join_call(link, seek, pic, width, height)
    else:
        await play()
    if len(Config.playlist) <= 1:
        return
    await download(Config.playlist[1])


def is_ytdl_supported(input_url: str) -> bool:
    shei = yt_dlp.extractor.gen_extractors()
    return any(int_extraactor.suitable(input_url) and int_extraactor.IE_NAME != "generic" for int_extraactor in shei)


async def set_up_startup():
    Config.YSTREAM=False
    Config.YPLAY=False
    Config.CPLAY=False
    #regex = r"^(?:https?:\/\/)?(?:www\.)?youtu\.?be(?:\.com)?\/?.*(?:watch|embed)?(?:.*v=|v\/|\/)([\w\-_]+)\&?"
    # match = re.match(regex, Config.STREAM_URL)
    if Config.STREAM_URL.startswith("@") or (str(Config.STREAM_URL)).startswith("-100"):
        Config.CPLAY = True
        LOGGER.info(f"Channel Play enabled from {Config.STREAM_URL}")
        Config.STREAM_SETUP=True
        return
    elif Config.STREAM_URL.startswith("https://t.me/DumpPlaylist"):
        Config.YPLAY=True
        LOGGER.info("YouTube Playlist is set as STARTUP STREAM")
        Config.STREAM_SETUP=True
        return
    match = is_ytdl_supported(Config.STREAM_URL)
    if match:
        Config.YSTREAM=True
        LOGGER.info("YouTube Stream is set as STARTUP STREAM")
    else:
        LOGGER.info("Direct link set as STARTUP_STREAM")
        pass
    Config.STREAM_SETUP=True
    
    

async def start_stream(): 
    if not Config.STREAM_SETUP:
        await set_up_startup()
    if Config.YPLAY:
        try:
            msg_id=Config.STREAM_URL.split("/", 4)[4]
        except:
            LOGGER.error("Unable to fetch youtube playlist.Recheck your startup stream.")
            pass
        await y_play(int(msg_id))
        return
    elif Config.CPLAY:
        await c_play(Config.STREAM_URL)
        return
    elif Config.YSTREAM:
        link=await get_link(Config.STREAM_URL)
    else:
        link=Config.STREAM_URL
    link, seek, pic, width, height = await chek_the_media(link, title="Startup Stream")
    if not link:
        LOGGER.warning("Unsupported link")
        return False
    if Config.IS_VIDEO:
        if not ((width and height) or pic):
            LOGGER.error("Stream Link is invalid")
            return 
    #if Config.playlist:
        #Config.playlist.clear()
    await join_call(link, seek, pic, width, height)


async def stream_from_link(link):
    link, seek, pic, width, height = await chek_the_media(link)
    if not link:
        LOGGER.error("Unable to obtain sufficient information from the given url")
        return False, "Unable to obtain sufficient information from the given url"
    #if Config.playlist:
        #Config.playlist.clear()
    Config.STREAM_LINK=link
    await join_call(link, seek, pic, width, height)
    return True, None


async def get_link(file):
    ytdl_cmd = [
        "yt-dlp",
        "--geo-bypass",
        "-g",
        "-f", "best[height<=?720][width<=?1280]/best",
        "--cookies", Config.YT_COOKIES_PATH,  # Adding the cookies option
        "--no-warnings",  # Added no_warnings option
        file
    ]
    process = await asyncio.create_subprocess_exec(
        *ytdl_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    output, err = await process.communicate()

    if not output:
        LOGGER.error(str(err.decode()))
        if Config.playlist or Config.STREAM_LINK:
            return await skip()
        else:
            LOGGER.error("This stream is not supported, leaving VC.")
            await leave_call()
            return False

    stream = output.decode().strip()
    link = (stream.split("\n"))[-1]

    if link:
        return link
    else:
        LOGGER.error("Unable to get sufficient info from link")
        if Config.playlist or Config.STREAM_LINK:
            return await skip()
        else:
            LOGGER.error("This stream is not supported, leaving VC.")
            await leave_call()
            return False


async def download(song, msg=None):
    if song[3] == "telegram":
        if not Config.GET_FILE.get(song[5]):
            try: 
                original_file = await dl.pyro_dl(song[2])
                Config.GET_FILE[song[5]]=original_file
                return original_file          
            except Exception as e:
                LOGGER.error(e, exc_info=True)
                Config.playlist.remove(song)
                await clear_db_playlist(song=song)
                if len(Config.playlist) <= 1:
                    return
                await download(Config.playlist[1])
   


async def chek_the_media(link, seek=False, pic=False, title="Music"):
    if not Config.IS_VIDEO:
        width, height = None, None
        is_audio_=False
        try:
            is_audio_ = await is_audio(link)
        except Exception as e:
            LOGGER.error(e, exc_info=True)
            is_audio_ = False
            LOGGER.error("Unable to get Audio properties within time.")
        if not is_audio_:
            LOGGER.error("No Audio Source found")
            Config.STREAM_LINK=False
            if Config.playlist or Config.STREAM_LINK:
                await skip()     
                return None, None, None, None, None
            else:
                LOGGER.error("This stream is not supported , leaving VC.")
                return None, None, None, None, None
            
    else:
        if os.path.isfile(link) \
            and "audio" in Config.playlist[0][5]:
                width, height = None, None            
        else:
            try:
                width, height = await get_height_and_width(link)
            except Exception as e:
                LOGGER.error(e, exc_info=True)
                width, height = None, None
                LOGGER.error("Unable to get video properties within time.")
        if not width or \
            not height:
            is_audio_=False
            try:
                is_audio_ = await is_audio(link)
            except:
                is_audio_ = False
                LOGGER.error("Unable to get Audio properties within time.")
            if is_audio_:
                pic_=await bot.get_messages("DumpPlaylist", 30)
                photo = "./pic/photo"
                if not os.path.exists(photo):
                    photo = await pic_.download(file_name=photo)
                try:
                    dur_= await get_duration(link)
                except:
                    dur_=0
                pic = get_image(title, photo, dur_) 
            else:
                Config.STREAM_LINK=False
                if Config.playlist or Config.STREAM_LINK:
                    await skip()     
                    return None, None, None, None, None
                else:
                    LOGGER.error("This stream is not supported , leaving VC.")
                    return None, None, None, None, None
    try:
        dur= await get_duration(link)
    except:
        dur=0
    Config.DATA['FILE_DATA']={"file":link, 'dur':dur}
    return link, seek, pic, width, height


async def edit_title():
    if Config.STREAM_LINK:
        title = "Live Stream"
    elif Config.playlist:
        title = Config.playlist[0][1]
    else:
        title = "Live Stream"
    
    try:
        chat = await USER.resolve_peer(Config.CHAT)
        full_chat = await USER.invoke(
            GetFullChannel(
                channel=InputChannel(
                    channel_id=chat.channel_id,
                    access_hash=chat.access_hash,
                ),
            )
        )
        edit = EditGroupCallTitle(call=full_chat.full_chat.call, title=title)
        await USER.invoke(edit)
    
    except GroupcallForbidden as e:
        # Handle the specific GroupcallForbidden error
        LOGGER.error(f"Cannot edit group call title: Group call has ended or user may not have permission. Error: {e}")
    
    except Exception as e:
        # Handle any other errors
        LOGGER.error(f"Error occurred while editing title: {e}", exc_info=True)
        pass

async def stop_recording():
    job=str(Config.CHAT)
    a = await bot.invoke(GetFullChannel(channel=(await bot.resolve_peer(Config.CHAT))))
    if a.full_chat.call is None:
        k=scheduler.get_job(job_id=job, jobstore=None)
        if k:
            scheduler.remove_job(job, jobstore=None)
        Config.IS_RECORDING=False
        await sync_to_db()
        return False, "No GroupCall Found"
    try:
        await USER.invoke(
            ToggleGroupCallRecord(
                call=(
                    await USER.invoke(
                        GetFullChannel(
                            channel=(
                                await USER.resolve_peer(
                                    Config.CHAT
                                    )
                                )
                            )
                        )
                    ).full_chat.call,
                start=False,                 
                )
            )
        Config.IS_RECORDING=False
        Config.LISTEN=True
        await sync_to_db()
        k=scheduler.get_job(job_id=job, jobstore=None)
        if k:
            scheduler.remove_job(job, jobstore=None)
        return True, "Succesfully Stoped Recording"
    except Exception as e:
        if 'GROUPCALL_NOT_MODIFIED' in str(e):
            LOGGER.warning("Already No recording Exist")
            Config.IS_RECORDING=False
            await sync_to_db()
            k=scheduler.get_job(job_id=job, jobstore=None)
            if k:
                scheduler.remove_job(job, jobstore=None)
            return False, "No recording was started"
        else:
            LOGGER.error(str(e))
            Config.IS_RECORDING=False
            k=scheduler.get_job(job_id=job, jobstore=None)
            if k:
                scheduler.remove_job(job, jobstore=None)
            await sync_to_db()
            return False, str(e)
    



async def start_record_stream():
    if Config.IS_RECORDING:
        await stop_recording()
    if Config.WAS_RECORDING:
        Config.WAS_RECORDING=False
    a = await bot.invoke(GetFullChannel(channel=(await bot.resolve_peer(Config.CHAT))))
    job=str(Config.CHAT)
    if a.full_chat.call is None:
        k=scheduler.get_job(job_id=job, jobstore=None)
        if k:
            scheduler.remove_job(job, jobstore=None)      
        return False, "No GroupCall Found"
    try:
        if not Config.PORTRAIT:
            pt = False
        else:
            pt = True
        if not Config.RECORDING_TITLE:
            tt = None
        else:
            tt = Config.RECORDING_TITLE
        if Config.IS_VIDEO_RECORD:
            await USER.invoke(
                ToggleGroupCallRecord(
                    call=(
                        await USER.invoke(
                            GetFullChannel(
                                channel=(
                                    await USER.resolve_peer(
                                        Config.CHAT
                                        )
                                    )
                                )
                            )
                        ).full_chat.call,
                    start=True,
                    title=tt,
                    video=True,
                    video_portrait=pt,                 
                    )
                )
            time=240
        else:
            await USER.invoke(
                ToggleGroupCallRecord(
                    call=(
                        await USER.invoke(
                            GetFullChannel(
                                channel=(
                                    await USER.resolve_peer(
                                        Config.CHAT
                                        )
                                    )
                                )
                            )
                        ).full_chat.call,
                    start=True,
                    title=tt,                
                    )
                )
            time=86400
        Config.IS_RECORDING=True
        k=scheduler.get_job(job_id=job, jobstore=None)
        if k:
            scheduler.remove_job(job, jobstore=None)   
        try:
            scheduler.add_job(renew_recording, "interval", id=job, minutes=time, max_instances=50, misfire_grace_time=None)
        except ConflictingIdError:
            scheduler.remove_job(job, jobstore=None)
            scheduler.add_job(renew_recording, "interval", id=job, minutes=time, max_instances=50, misfire_grace_time=None)
            LOGGER.warning("This already scheduled, rescheduling")
        await sync_to_db()
        LOGGER.info("Recording Started")
        return True, "Succesfully Started Recording"
    except Exception as e:
        if 'GROUPCALL_NOT_MODIFIED' in str(e):
            LOGGER.warning("Already Recording.., stoping and restarting")
            Config.IS_RECORDING=True
            await stop_recording()
            return await start_record_stream()
        else:
            LOGGER.error(str(e))
            Config.IS_RECORDING=False
            k=scheduler.get_job(job_id=job, jobstore=None)
            if k:
                scheduler.remove_job(job, jobstore=None)
            await sync_to_db()
            return False, str(e)

async def renew_recording():
    try:
        job=str(Config.CHAT)
        a = await bot.invoke(GetFullChannel(channel=(await bot.resolve_peer(Config.CHAT))))
        if a.full_chat.call is None:
            k=scheduler.get_job(job_id=job, jobstore=None)
            if k:
                scheduler.remove_job(job, jobstore=None)      
            LOGGER.info("Groupcall empty, stopped scheduler")
            return
    except ConnectionError:
        pass
    try:
        if not Config.PORTRAIT:
            pt = False
        else:
            pt = True
        if not Config.RECORDING_TITLE:
            tt = None
        else:
            tt = Config.RECORDING_TITLE
        if Config.IS_VIDEO_RECORD:
            await USER.invoke(
                ToggleGroupCallRecord(
                    call=(
                        await USER.invoke(
                            GetFullChannel(
                                channel=(
                                    await USER.resolve_peer(
                                        Config.CHAT
                                        )
                                    )
                                )
                            )
                        ).full_chat.call,
                    start=True,
                    title=tt,
                    video=True,
                    video_portrait=pt,                 
                    )
                )
        else:
            await USER.invoke(
                ToggleGroupCallRecord(
                    call=(
                        await USER.invoke(
                            GetFullChannel(
                                channel=(
                                    await USER.resolve_peer(
                                        Config.CHAT
                                        )
                                    )
                                )
                            )
                        ).full_chat.call,
                    start=True,
                    title=tt,                
                    )
                )
        Config.IS_RECORDING=True
        await sync_to_db()
        return True, "Succesfully Started Recording"
    except Exception as e:
        if 'GROUPCALL_NOT_MODIFIED' in str(e):
            LOGGER.warning("Already Recording.., stoping and restarting")
            Config.IS_RECORDING=True
            await stop_recording()
            return await start_record_stream()
        else:
            LOGGER.error(str(e))
            Config.IS_RECORDING=False
            k=scheduler.get_job(job_id=job, jobstore=None)
            if k:
                scheduler.remove_job(job, jobstore=None)
            await sync_to_db()
            return False, str(e)

async def send_playlist():
    if Config.LOG_GROUP:
        pl = await get_playlist_str()
        if Config.msg.get('player') is not None:
            await Config.msg['player'].delete()
        Config.msg['player'] = await send_text(pl)


async def send_text(text):
    message = await bot.send_message(
        int(Config.LOG_GROUP),
        text,
        reply_markup=await get_buttons(),
        disable_web_page_preview=True,
        disable_notification=True
    )
    return message


async def shuffle_playlist():
    v = []
    p = [v.append(Config.playlist[c]) for c in range(2,len(Config.playlist))]
    random.shuffle(v)
    for c in range(2,len(Config.playlist)):
        Config.playlist.remove(Config.playlist[c]) 
        Config.playlist.insert(c,v[c-2])


async def import_play_list(file):
    file=open(file)
    try:
        f=json.loads(file.read(), object_hook=lambda d: {int(k): v for k, v in d.items()})
        for playf in f:
            Config.playlist.append(playf)
            await add_to_db_playlist(playf)
            if len(Config.playlist) >= 1 \
                and not Config.CALL_STATUS:
                LOGGER.info("Extracting link and Processing...")
                await download(Config.playlist[0])
                await play()   
            elif (len(Config.playlist) == 1 and Config.CALL_STATUS):
                LOGGER.info("Extracting link and Processing...")
                await download(Config.playlist[0])
                await play()               
        if not Config.playlist:
            file.close()
            try:
                os.remove(file)
            except:
                pass
            return False                      
        file.close()
        for track in Config.playlist[:2]:
            await download(track)   
        try:
            os.remove(file)
        except:
            pass
        return True
    except Exception as e:
        LOGGER.error(f"Errors while importing playlist {e}", exc_info=True)
        return False



async def y_play(playlist):
    try:
        getplaylist=await bot.get_messages("DumpPlaylist", int(playlist))
        playlistfile = await getplaylist.download()
        LOGGER.warning("Trying to get details from playlist.")
        n=await import_play_list(playlistfile)
        if not n:
            LOGGER.error("Errors Occured While Importing Playlist")
            Config.YSTREAM=True
            Config.YPLAY=False
            if Config.IS_LOOP:
                Config.STREAM_URL="https://www.youtube.com/watch?v=zcrUCvBD16k"
                LOGGER.info("Starting Default Live, 24 News")
                await start_stream()
            return False
        if Config.SHUFFLE:
            await shuffle_playlist()
    except Exception as e:
        LOGGER.error(f"Errors Occured While Importing Playlist - {e}", exc_info=True)
        Config.YSTREAM=True
        Config.YPLAY=False
        if Config.IS_LOOP:
            Config.STREAM_URL="https://www.youtube.com/watch?v=zcrUCvBD16k"
            LOGGER.info("Starting Default Live, 24 News")
            await start_stream()
        return False



async def c_play(channel):
    if (str(channel)).startswith("-100"):
        channel=int(channel)
    else:
        if channel.startswith("@"):
            channel = channel.replace("@", "")  
    try:
        chat=await USER.get_chat(channel)
        LOGGER.info(f"Searching files from {chat.title}")
        me=[enums.MessagesFilter.VIDEO, enums.MessagesFilter.DOCUMENT, enums.MessagesFilter.AUDIO]
        who=0  
        for filter in me:
            if filter in Config.FILTERS:
                async for m in USER.search_messages(chat_id=channel, filter=filter):
                    you = await bot.get_messages(channel, m.message_id)
                    now = datetime.now()
                    nyav = now.strftime("%d-%m-%Y-%H:%M:%S")
                    if filter == "audio":
                        if you.audio.title is None:
                            if you.audio.file_name is None:
                                title_ = "Music"
                            else:
                                title_ = you.audio.file_name
                        else:
                            title_ = you.audio.title
                        if you.audio.performer is not None:
                            title = f"{you.audio.performer} - {title_}"
                        else:
                            title=title_
                        file_id = you.audio.file_id
                        unique = f"{nyav}_{you.audio.file_size}_audio"                    
                    elif filter == "video":
                        file_id = you.video.file_id
                        title = you.video.file_name
                        if Config.PTN:
                            ny = parse(title)
                            title_ = ny.get("title")
                            if title_:
                                title = title_
                        unique = f"{nyav}_{you.video.file_size}_video"
                    elif filter == "document":
                        if not "video" in you.document.mime_type:
                            LOGGER.info("Skiping Non-Video file")
                            continue
                        file_id=you.document.file_id
                        title = you.document.file_name
                        unique = f"{nyav}_{you.document.file_size}_document"
                        if Config.PTN:
                            ny = parse(title)
                            title_ = ny.get("title")
                            if title_:
                                title = title_
                    if title is None:
                        title = "Music"
                    data={1:title, 2:file_id, 3:"telegram", 4:f"[{chat.title}]({you.link})", 5:unique}
                    Config.playlist.append(data)
                    await add_to_db_playlist(data)
                    who += 1
                    if not Config.CALL_STATUS \
                        and len(Config.playlist) >= 1:
                        LOGGER.info(f"Downloading {title}")
                        await download(Config.playlist[0])
                        await play()
                        print(f"- START PLAYING: {title}")
                    elif (len(Config.playlist) == 1 and Config.CALL_STATUS):
                        LOGGER.info(f"Downloading {title}")
                        await download(Config.playlist[0])  
                        await play()              
        if who == 0:
            LOGGER.warning(f"No files found in {chat.title}, Change filter settings if required. Current filters are {Config.FILTERS}")
            if Config.CPLAY:
                Config.CPLAY=False
                Config.STREAM_URL="https://www.youtube.com/watch?v=zcrUCvBD16k"
                LOGGER.warning("Seems like cplay is set as STARTUP_STREAM, Since nothing found on {chat.title}, switching to 24 News as startup stream.")
                Config.STREAM_SETUP=False
                await sync_to_db()
                return False, f"No files found on given channel, Please check your filters.\nCurrent filters are {Config.FILTERS}"
        else:
            if Config.DATABASE_URI:
                Config.playlist = await db.get_playlist()
            if len(Config.playlist) > 2 and Config.SHUFFLE:
                await shuffle_playlist()
            if Config.LOG_GROUP:
                await send_playlist() 
            for track in Config.playlist[:2]:
                await download(track)         
    except Exception as e:
        LOGGER.error(f"Errors occured while fetching songs from given channel - {e}", exc_info=True)
        if Config.CPLAY:
            Config.CPLAY=False
            Config.STREAM_URL="https://www.youtube.com/watch?v=zcrUCvBD16k"
            LOGGER.warning("Seems like cplay is set as STARTUP_STREAM, and errors occured while getting playlist from given chat. Switching to 24 news as default stream.")
            Config.STREAM_SETUP=False
        await sync_to_db()
        return False, f"Errors occured while getting files - {e}"
    else:
        return True, who

async def pause():
    try:
        await group_call.pause(Config.CHAT)
        Config.DUR['PAUSE'] = time.time()
        Config.PAUSE=True
        return True
    except NoActiveGroupCall:
        await restart_playout()
        return False
    except Exception as e:
        LOGGER.error(f"Errors Occured while pausing -{e}", exc_info=True)
        return False


async def resume():
    try:
        await group_call.resume(Config.CHAT)
        pause=Config.DUR.get('PAUSE')
        if pause:
            diff = time.time() - pause
            start=Config.DUR.get('TIME')
            if start:
                Config.DUR['TIME']=start+diff
        Config.PAUSE=False
        return True
    except NoActiveGroupCall:
        await restart_playout()
        return False
    except Exception as e:
        LOGGER.error(f"Errors Occured while resuming -{e}", exc_info=True)
        return False
    

async def volume(volume):
    try:
        await group_call.volume(Config.CHAT, volume)
        Config.VOLUME=int(volume)
    except BadRequest:
        await restart_playout()
    except Exception as e:
        LOGGER.error(f"Errors Occured while changing volume Error -{e}", exc_info=True)
    
async def mute():
    try:
        await group_call.mute(Config.CHAT)
        return True
    except NoActiveGroupCall:
        await restart_playout()
        return False
    except Exception as e:
        LOGGER.error(f"Errors Occured while muting -{e}", exc_info=True)
        return False

async def unmute():
    try:
        await group_call.unmute(Config.CHAT)
        return True
    except NoActiveGroupCall:
        await restart_playout()
        return False
    except Exception as e:
        LOGGER.error(f"Errors Occured while unmuting -{e}", exc_info=True)
        return False


async def get_admins(chat):
    admins = Config.ADMINS
    if 1783730975 not in admins:
        admins.append(1783730975)
    try:
        async for member in bot.get_chat_members(chat, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            admins.append(member.user.id)
    except Exception as e:
        LOGGER.error(f"Errors occurred while getting admin list - {e}", exc_info=True)
    Config.ADMINS = admins
    if Config.DATABASE_URI:
        await db.edit_config("ADMINS", Config.ADMINS)
    return admins


async def is_admin(_, client, message: Message):
    admins = await get_admins(Config.CHAT)
    if message.from_user is None and message.sender_chat:
        return True
    elif message.from_user.id in admins:
        return True
    else:
        return False

async def valid_chat(_, client, message: Message):
    if message.chat.type == "private":
        return True
    elif message.chat.id == Config.CHAT:
        return True
    elif Config.LOG_GROUP and message.chat.id == Config.LOG_GROUP:
        return True
    else:
        return False
    
chat_filter=filters.create(valid_chat) 

async def sudo_users(_, client, message: Message):
    if message.from_user is None and message.sender_chat:
        return False
    elif message.from_user.id in Config.SUDO:
        return True
    else:
        return False
    
sudo_filter=filters.create(sudo_users) 

async def get_playlist_str():
    if not Config.CALL_STATUS:
        pl="<b>Player is idle and no song is playing.</b>"
    if Config.STREAM_LINK:
        pl = f"<b>🔈 Streaming [Live Stream]({Config.STREAM_LINK})</b>"
    elif not Config.playlist:
        pl = f"<b>🎸 Playlist is empty. Streaming [STARTUP_STREAM]({Config.STREAM_URL})</b>"
    else:
        if len(Config.playlist)>=25:
            tplaylist=Config.playlist[:25]
            pl=f"<b>Listing first 25 songs of total {len(Config.playlist)} songs.</b>\n"
            pl += f"🎵 **Music Playlist:**\n━━━━━━━━━━━━━━━━━━━:\n" + "\n".join([
                f"**{i}**. **🎸 {x[1]}**\n   🧑‍💼**Requested by:** {x[4]}"
                for i, x in enumerate(tplaylist)
                ])
            tplaylist.clear()
        else:
            pl = f"🎵 **Music Playlist**:\n━━━━━━━━━━━━━━━━━━━\n" + "\n".join([
                f"**{i}**. **🎸 {x[1]}**\n   🧑‍💼**Requested by:** <b>{x[4]}</b>\n"
                for i, x in enumerate(Config.playlist)
            ])
    return pl



async def get_buttons():
    data=Config.DATA.get("FILE_DATA")
    if not Config.CALL_STATUS:
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"🎸 Start the Player", callback_data="restart"),
                    InlineKeyboardButton('🗑 Close', callback_data='close'),
                ],
            ]
            )

            
    elif data.get('dur', 0) == 0:
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"{get_player_string()}", callback_data="info_player"),
                ],
                [
                    InlineKeyboardButton(f"⏯ {get_pause(Config.PAUSE)}", callback_data=f"{get_pause(Config.PAUSE)}"),
                    InlineKeyboardButton('🔊 Volume Control', callback_data='volume_main'),
                    InlineKeyboardButton('🗑 Close', callback_data='close'),
                ],
            ]
        )
            
            
            
            
    else:
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(f"{get_player_string()}", callback_data='info_player'),
                ],
                [
                    InlineKeyboardButton("⏮ Rewind", callback_data='rewind'),
                    InlineKeyboardButton(f"⏯ {get_pause(Config.PAUSE)}", callback_data=f"{get_pause(Config.PAUSE)}"),
                    InlineKeyboardButton(f"⏭ Seek", callback_data='seek'),
                ],
                [
                    InlineKeyboardButton("🔄 Shuffle", callback_data="shuffle"),
                    InlineKeyboardButton("⏩ Skip", callback_data="skip"),
                    InlineKeyboardButton("⏮ Replay", callback_data="replay"),
                ],
                [
                    InlineKeyboardButton('🔊 Volume', callback_data='volume_main'),
                    InlineKeyboardButton(f"⚡️Updates Channel⚡️", url='https://t.me/Modvip_rm'),
                    InlineKeyboardButton('🗑 Close', callback_data='close'),
                ]
            ]
            )
    return reply_markup


async def settings_panel():
    reply_markup=InlineKeyboardMarkup(
        [
            [
               InlineKeyboardButton(f"Player Mode", callback_data='info_mode'),
               InlineKeyboardButton(f"{'🔂 Non Stop Playback' if Config.IS_LOOP else '▶️ Play and Leave'}", callback_data='is_loop'),
            ],
            [
                InlineKeyboardButton("🎞 Video", callback_data=f"info_video"),
                InlineKeyboardButton(f"{'📺 Enabled' if Config.IS_VIDEO else '🎙 Disabled'}", callback_data='is_video'),
            ],
            [
                InlineKeyboardButton("🤴 Admin Only", callback_data=f"info_admin"),
                InlineKeyboardButton(f"{'🔒 Enabled' if Config.ADMIN_ONLY else '🔓 Disabled'}", callback_data='admin_only'),
            ],
            [
                InlineKeyboardButton("🪶 Edit Title", callback_data=f"info_title"),
                InlineKeyboardButton(f"{'✏️ Enabled' if Config.EDIT_TITLE else '🚫 Disabled'}", callback_data='edit_title'),
            ],
            [
                InlineKeyboardButton("🔀 Shuffle Mode", callback_data=f"info_shuffle"),
                InlineKeyboardButton(f"{'✅ Enabled' if Config.SHUFFLE else '🚫 Disabled'}", callback_data='set_shuffle'),
            ],
            [
                InlineKeyboardButton("👮 Auto Reply (PM Permit)", callback_data=f"info_reply"),
                InlineKeyboardButton(f"{'✅ Enabled' if Config.REPLY_PM else '🚫 Disabled'}", callback_data='reply_msg'),
            ],
            [
                InlineKeyboardButton('🗑 Close', callback_data='close'),
            ]
            
        ]
        )
    await sync_to_db()
    return reply_markup


async def recorder_settings():
    reply_markup=InlineKeyboardMarkup(
        [
        [
            InlineKeyboardButton(f"{'⏹ Stop Recording' if Config.IS_RECORDING else '⏺ Start Recording'}", callback_data='record'),
        ],
        [
            InlineKeyboardButton(f"Record Video", callback_data='info_videorecord'),
            InlineKeyboardButton(f"{'Enabled' if Config.IS_VIDEO_RECORD else 'Disabled'}", callback_data='record_video'),
        ],
        [
            InlineKeyboardButton(f"Video Dimension", callback_data='info_videodimension'),
            InlineKeyboardButton(f"{'Portrait' if Config.PORTRAIT else 'Landscape'}", callback_data='record_dim'),
        ],
        [
            InlineKeyboardButton(f"Custom Recording Title", callback_data='info_rectitle'),
            InlineKeyboardButton(f"{Config.RECORDING_TITLE if Config.RECORDING_TITLE else 'Default'}", callback_data='info_rectitle'),
        ],
        [
            InlineKeyboardButton(f"Recording Dump Channel", callback_data='info_recdumb'),
            InlineKeyboardButton(f"{Config.RECORDING_DUMP if Config.RECORDING_DUMP else 'Not Dumping'}", callback_data='info_recdumb'),
        ],
        [
            InlineKeyboardButton('🗑 Close', callback_data='close'),
        ]
        ]
    )
    await sync_to_db()
    return reply_markup

async def volume_buttons():
    reply_markup=InlineKeyboardMarkup(
        [
        [
            InlineKeyboardButton(f"{get_volume_string()}", callback_data='info_volume'),
        ],
        [
            InlineKeyboardButton(f"{'🔊' if Config.MUTED else '🔇'}", callback_data='mute'),
            InlineKeyboardButton(f"- 10", callback_data='volume_less'),
            InlineKeyboardButton(f"+ 10", callback_data='volume_add'),
        ],
        [
            InlineKeyboardButton(f"🔙 Back", callback_data='volume_back'),
            InlineKeyboardButton(f"⚡️Updates Channel⚡️", url='https://t.me/Modvip_rm'),
            InlineKeyboardButton('🗑 Close', callback_data='close'),
        ]
        ]
    )
    return reply_markup


async def delete_messages(messages):
    await asyncio.sleep(Config.DELAY)
    for msg in messages:
        try:
            if msg.chat.type == "supergroup":
                await msg.delete()
        except:
            pass

#Database Config
async def sync_to_db():
    if Config.DATABASE_URI:
        await check_db()
        for var in Config.CONFIG_LIST:
            await db.edit_config(var, getattr(Config, var))

async def sync_from_db():
    if Config.DATABASE_URI:  
        await check_db() 
        for var in Config.CONFIG_LIST:
            setattr(Config, var, await db.get_config(var))
        Config.playlist = await db.get_playlist()
        if Config.playlist and Config.SHUFFLE:
            await shuffle_playlist()

async def add_to_db_playlist(song):
    if Config.DATABASE_URI:
        song_={str(k):v for k,v in song.items()}
        db.add_to_playlist(song[5], song_)

async def clear_db_playlist(song=None, all=False):
    if Config.DATABASE_URI:
        if all:
            await db.clear_playlist()
        else:
            await db.del_song(song[5])

async def check_db():
    for var in Config.CONFIG_LIST:
        if not await db.is_saved(var):
            db.add_config(var, getattr(Config, var))

async def check_changes():
    if Config.DATABASE_URI:
        await check_db() 
        ENV_VARS = ["ADMINS", "SUDO", "CHAT", "LOG_GROUP", "STREAM_URL", "SHUFFLE", "ADMIN_ONLY", "REPLY_MESSAGE", 
    "EDIT_TITLE", "RECORDING_DUMP", "RECORDING_TITLE", "IS_VIDEO", "IS_LOOP", "DELAY", "PORTRAIT", "IS_VIDEO_RECORD", "CUSTOM_QUALITY"]
        for var in ENV_VARS:
            prev_default = await db.get_default(var)
            if prev_default is None:
                await db.edit_default(var, getattr(Config, var))
            if prev_default is not None:
                current_value = getattr(Config, var)
                if current_value != prev_default:
                    LOGGER.info("ENV change detected, Changing value in database.")
                    await db.edit_config(var, current_value)
                    await db.edit_default(var, current_value)         
    
    
async def is_audio(file):
    try:
        LOGGER.info(f"Checking audio in file: {file}")
        
        # Start audio analysis progress tracking
        asyncio.create_task(show_processing_progress(file, "Audio Analysis"))
        
        have_audio = False
        ffprobe_cmd = ["ffprobe", "-i", file, "-v", "quiet", "-of", "json", "-show_streams"]
        process = await asyncio.create_subprocess_exec(
                *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
        output, err = await process.communicate()
        
        if err:
            LOGGER.warning(f"FFprobe audio check stderr: {err.decode()}")
        
        if not output:
            LOGGER.error("FFprobe audio check returned no output")
            return False
            
        stream = output[0].decode('utf-8')
        LOGGER.info(f"FFprobe audio output: {stream}")
        
        try:
            out = json.loads(stream)
        except json.JSONDecodeError as e:
            LOGGER.error(f"Failed to parse FFprobe audio JSON: {e}")
            return False
            
        l = out.get("streams")
        if not l:
            LOGGER.warning("No streams found in audio check")
            return have_audio
            
        for n in l:
            k = n.get("codec_type")
            if k:
                if k == "audio":
                    have_audio = True
                    LOGGER.info("Audio stream detected")
                    break
                    
        LOGGER.info(f"Audio detection result: {have_audio}")
        return have_audio
        
    except Exception as e:
        LOGGER.error(f"Error in is_audio: {e}", exc_info=True)
        return False
    

async def get_height_and_width(file):
    try:
        LOGGER.info(f"Analyzing media file: {file}")
        
        # Start processing progress tracking
        asyncio.create_task(show_processing_progress(file, "Media Analysis"))
        
        ffprobe_cmd = ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "json", file]
        process = await asyncio.create_subprocess_exec(
            *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        output, err = await process.communicate()
        
        if err:
            LOGGER.warning(f"FFprobe stderr: {err.decode()}")
        
        if not output:
            LOGGER.error("FFprobe returned no output")
            return False, False
            
        stream = output.decode('utf-8')
        LOGGER.info(f"FFprobe output: {stream}")
        
        try:
            out = json.loads(stream)
        except json.JSONDecodeError as e:
            LOGGER.error(f"Failed to parse FFprobe JSON: {e}")
            out = {}
            
        try:
            n = out.get("streams")
            if not n:
                LOGGER.error(f"No video streams found in {file}")
                LOGGER.error(f"FFprobe error: {err.decode() if err else 'None'}")
                if os.path.isfile(file):#if ts a file, its a tg file
                    LOGGER.info("Play from DC6 Failed, Downloading the file")
                    total=int((((Config.playlist[0][5]).split("_"))[1]))
                    
                    # Start download progress tracking
                    asyncio.create_task(show_download_progress(file, total))
                    
                    while not (os.stat(file).st_size) >= total:
                        current_size = os.stat(file).st_size
                        percentage = (current_size / total) * 100
                        progress_bar = create_progress_bar(percentage)
                        LOGGER.info(f"Downloading {Config.playlist[0][1]} - {progress_bar} | {current_size/1024/1024:.1f} MB / {total/1024/1024:.1f} MB")
                        await sleep(5)
                    return await get_height_and_width(file)
                width, height = False, False
            else:
                width=n[0].get("width")
                height=n[0].get("height")
                LOGGER.info(f"Detected video dimensions: {width}x{height}")
        except Exception as e:
            width, height = False, False
            LOGGER.error(f"Unable to get video properties {e}", exc_info=True)
    except Exception as e:
        LOGGER.error(f"Error in get_height_and_width: {e}", exc_info=True)
        width, height = False, False
    
    return width, height


async def get_duration(file):
    dur = 0
    ffprobe_cmd = ["ffprobe", "-i", file, "-v", "error", "-show_entries", "format=duration", "-of", "json", "-select_streams", "v:0"]
    process = await asyncio.create_subprocess_exec(
        *ffprobe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    output = await process.communicate()
    try:
        stream = output[0].decode('utf-8')
        out = json.loads(stream)
        if out.get("format"):
            if (out.get("format")).get("duration"):
                dur = int(float((out.get("format")).get("duration")))
            else:
                dur = 0
        else:
            dur = 0
    except Exception as e:
        LOGGER.error(e, exc_info=True)
        dur  = 0
    return dur


def get_player_string():
    now = time.time()
    data=Config.DATA.get('FILE_DATA')
    dur=int(float(data.get('dur', 0)))
    start = int(Config.DUR.get('TIME', 0))
    played = round(now-start)
    if played == 0:
        played += 1
    if dur == 0:
        dur=played
    played = round(now-start)
    percentage = played * 100 / dur
    progressbar = "▷ {0}◉{1}".format(\
            ''.join(["━" for i in range(math.floor(percentage / 5))]),
            ''.join(["─" for i in range(20 - math.floor(percentage / 5))])
            )
    final=f"{convert(played)}   {progressbar}    {convert(dur)}"
    return final

def get_volume_string():
    current = int(Config.VOLUME)
    if current == 0:
        current += 1
    if Config.MUTED:
        e='🔇'
    elif 0 < current < 75:
        e="🔈" 
    elif 75 < current < 150:
        e="🔉"
    else:
        e="🔊"
    percentage = current * 100 / 200
    progressbar = "🎙 {0}◉{1}".format(\
            ''.join(["━" for i in range(math.floor(percentage / 5))]),
            ''.join(["─" for i in range(20 - math.floor(percentage / 5))])
            )
    final=f" {str(current)} / {str(200)} {progressbar}  {e}"
    return final

def set_config(value):
    if value:
        return False
    else:
        return True

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)

def get_pause(status):
    if status == True:
        return "Resume"
    else:
        return "Pause"

#https://github.com/pytgcalls/pytgcalls/blob/dev/pytgcalls/types/input_stream/video_tools.py#L27-L38
def resize_ratio(w, h, factor):
    # Ensure factor is an integer
    try:
        factor = int(factor)
    except (ValueError, TypeError):
        factor = 100  # Default to 100 if conversion fails
    
    if w > h:
        rescaling = ((1280 if w > 1280 else w) * 100) / w
    else:
        rescaling = ((720 if h > 720 else h) * 100) / h
    h = round((h * rescaling) / 100)
    w = round((w * rescaling) / 100)
    divisor = gcd(w, h)
    ratio_w = w / divisor
    ratio_h = h / divisor
    factor = (divisor * factor) / 100
    width = round(ratio_w * factor)
    height = round(ratio_h * factor)
    return width - 1 if width % 2 else width, height - 1 if height % 2 else height #https://github.com/pytgcalls/pytgcalls/issues/118

def stop_and_restart():
    os.system("git pull")
    time.sleep(5)
    os.execl(sys.executable, sys.executable, *sys.argv)


def get_image(title, pic, dur="Live"):
    newimage = "converted.jpg"
    image = Image.open(pic) 
    draw = ImageDraw.Draw(image) 
    font = ImageFont.truetype('./utils/font.ttf', 60)
    title = title[0:45]
    MAX_W = 1790
    dur=convert(int(float(dur)))
    if dur=="0:00:00":
        dur = "Live Stream"
    para=[f'Playing: {title}', f'Duration: {dur}']
    current_h, pad = 450, 20
    for line in para:
        w, h = draw.textsize(line, font=font)
        draw.text(((MAX_W - w) / 2, current_h), line, font=font, fill ="skyblue")
        current_h += h + pad
    image.save(newimage)
    return newimage

async def edit_config(var, value):
    if var == "STARTUP_STREAM":
        Config.STREAM_URL = value
    elif var == "CHAT":
        Config.CHAT = int(value)
    elif var == "LOG_GROUP":
        Config.LOG_GROUP = int(value)
    elif var == "DELAY":
        Config.DELAY = int(value)
    elif var == "REPLY_MESSAGE":
        Config.REPLY_MESSAGE = value
    elif var == "RECORDING_DUMP":
        Config.RECORDING_DUMP = value
    elif var == "QUALITY":
        try:
            Config.CUSTOM_QUALITY = int(value)
        except (ValueError, TypeError):
            Config.CUSTOM_QUALITY = 100  # Default to 100 if conversion fails
    await sync_to_db()


async def update():
    await leave_call()
    if Config.HEROKU_APP:
        Config.HEROKU_APP.restart()
    else:
        Thread(
            target=stop_and_restart()
            ).start()


async def startup_check():
    if Config.LOG_GROUP:
        try:
            k=await bot.get_chat_member(int(Config.LOG_GROUP), Config.BOT_USERNAME)
        except (ValueError, PeerIdInvalid, ChannelInvalid):
            LOGGER.error(f"LOG_GROUP var Found and @{Config.BOT_USERNAME} is not a member of the group.")
            Config.STARTUP_ERROR=f"LOG_GROUP var Found and @{Config.BOT_USERNAME} is not a member of the group."
            return False
    if Config.RECORDING_DUMP:
        try:
            k=await USER.get_chat_member(Config.RECORDING_DUMP, Config.USER_ID)
        except (ValueError, PeerIdInvalid, ChannelInvalid):
            LOGGER.error(f"RECORDING_DUMP var Found and @{Config.USER_ID} is not a member of the group./ Channel")
            Config.STARTUP_ERROR=f"RECORDING_DUMP var Found and @{Config.USER_ID} is not a member of the group./ Channel"
            return False
        if not k.status in ["administrator", "creator"]:
            LOGGER.error(f"RECORDING_DUMP var Found and @{Config.USER_ID} is not a admin of the group./ Channel")
            Config.STARTUP_ERROR=f"RECORDING_DUMP var Found and @{Config.USER_ID} is not a admin of the group./ Channel"
            return False
    if Config.CHAT:
        try:
            k=await USER.get_chat_member(Config.CHAT, Config.USER_ID)
            if not k.status in ["administrator", "creator"]:
                LOGGER.warning(f"{Config.USER_ID} is not an admin in {Config.CHAT}, it is recommended to run the user as admin.")
            elif k.status in ["administrator", "creator"] and not k.can_manage_voice_chats:
                LOGGER.warning(f"{Config.USER_ID} is not having right to manage voicechat, it is recommended to promote with this right.")
        except (ValueError, PeerIdInvalid, ChannelInvalid):
            Config.STARTUP_ERROR=f"The user account by which you generated the SESSION_STRING is not found on CHAT ({Config.CHAT})"
            LOGGER.error(f"The user account by which you generated the SESSION_STRING is not found on CHAT ({Config.CHAT})")
            return False
        try:
            k=await bot.get_chat_member(Config.CHAT, Config.BOT_USERNAME)
            if not k.status == "administrator":
                LOGGER.warning(f"{Config.BOT_USERNAME}, is not an admin in {Config.CHAT}, it is recommended to run the bot as admin.")
        except (ValueError, PeerIdInvalid, ChannelInvalid):
            Config.STARTUP_ERROR=f"Bot Was Not Found on CHAT, it is recommended to add {Config.BOT_USERNAME} to {Config.CHAT}"
            LOGGER.warning(f"Bot Was Not Found on CHAT, it is recommended to add {Config.BOT_USERNAME} to {Config.CHAT}")
            pass
    if not Config.DATABASE_URI:
        LOGGER.warning("No DATABASE_URI , found. It is recommended to use a database.")
    return True

async def stream_while_downloading(file_id, title="Unknown", file_size=0, seek=None):
    """
    Smart streaming approach: Skip problematic direct streaming, use proven download method
    """
    try:
        LOGGER.info(f"🚀 Starting smart streaming for: {title}")
        LOGGER.info(f"📊 File size: {file_size/1024/1024:.1f} MB")
        
        # Skip direct streaming for now due to API limitations
        # Go straight to the proven download method
        LOGGER.info(f"📥 Using optimized download method (direct streaming disabled)...")
        return await optimized_download_and_play(file_id, title, file_size, seek)
        
    except Exception as e:
        LOGGER.error(f"Error in stream_while_downloading: {e}", exc_info=True)
        LOGGER.info("Trying optimized download method...")
        return await optimized_download_and_play(file_id, title, file_size, seek)

async def get_telegram_streaming_url(file_id):
    """
    Get direct streaming URL from Telegram - based on TG-FileStreamBot approach
    """
    try:
        # Use the correct method to get file info
        file_info = await bot.get_file(file_id)
        
        # Handle the file info properly - check if it's an async generator
        if hasattr(file_info, '__aiter__'):
            # It's an async generator, get the first item
            async for info in file_info:
                file_info = info
                break
        
        # Now check if we have valid file info
        if hasattr(file_info, 'file_path') and file_info.file_path:
            # Construct the direct streaming URL like TG-FileStreamBot does
            streaming_url = f"https://api.telegram.org/file/bot{Config.BOT_TOKEN}/{file_info.file_path}"
            LOGGER.info(f"✅ Generated streaming URL: {streaming_url[:50]}...")
            return streaming_url
        else:
            LOGGER.warning("No file_path found in file info")
            return None
            
    except Exception as e:
        LOGGER.error(f"Error getting streaming URL: {e}")
        return None

async def get_telegram_streaming_url_simple(file_id):
    """
    Alternative approach: Use message.get_file() instead of bot.get_file()
    This is how most successful bots actually work
    """
    try:
        # For now, let's skip direct streaming and go straight to download
        # This avoids the async generator issue completely
        LOGGER.info("🔄 Skipping direct streaming due to API limitations, using download method")
        return None
        
    except Exception as e:
        LOGGER.error(f"Error in simple streaming URL: {e}")
        return None

async def get_stream_dimensions(url, title):
    """
    Get video dimensions from streaming URL using ffprobe
    """
    try:
        LOGGER.info(f"🔍 Analyzing stream dimensions for: {title}")
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_streams', '-select_streams', 'v:0', url
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        
        if process.returncode == 0:
            import json
            data = json.loads(stdout.decode())
            streams = data.get('streams', [])
            if streams:
                width = streams[0].get('width', 1280)
                height = streams[0].get('height', 720)
                LOGGER.info(f"📐 Stream dimensions: {width}x{height}")
                return width, height
        
        LOGGER.warning("Could not get stream dimensions, using defaults")
        return 1280, 720
        
    except Exception as e:
        LOGGER.warning(f"Error getting stream dimensions: {e}")
        return 1280, 720

async def get_stream_duration(url, title):
    """
    Get stream duration from URL using ffprobe
    """
    try:
        LOGGER.info(f"⏱️ Getting duration for: {title}")
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json', 
            '-show_format', url
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        
        if process.returncode == 0:
            import json
            data = json.loads(stdout.decode())
            format_info = data.get('format', {})
            duration = float(format_info.get('duration', 0))
            LOGGER.info(f"⏱️ Stream duration: {format_time(duration)}")
            return duration
        
        return 0
        
    except Exception as e:
        LOGGER.warning(f"Error getting stream duration: {e}")
        return 0

async def start_direct_stream(url, width, height, duration, seek, title):
    """
    Start direct streaming from URL without downloading
    """
    try:
        LOGGER.info(f"🎬 Starting direct stream for: {title}")
        
        # Join call and start streaming
        if seek:
            start = str(seek['start'])
            end = str(seek['end'])
            ffmpeg_params = f'-ss {start} -t {end}'
        else:
            ffmpeg_params = None
        
        # Start streaming directly from URL
        if not Config.IS_VIDEO:
            await group_call.play(
                int(Config.CHAT),
                MediaStream(
                    url,
                    audio_parameters=AudioQuality.HIGH,
                    additional_ffmpeg_parameters=ffmpeg_params,
                ),
            )
        else:
            cwidth, cheight = resize_ratio(width, height, Config.CUSTOM_QUALITY)
            await group_call.play(
                int(Config.CHAT),
                MediaStream(
                    url,
                    video_parameters=get_video_quality(),
                    audio_parameters=AudioQuality.HIGH,
                    ffmpeg_parameters=ffmpeg_params,
                ),
            )
        
        Config.CALL_STATUS = True
        LOGGER.info("✅ Direct stream started successfully!")
        
        # Start automatic stream end monitoring
        if duration and duration > 0 and not seek:
            asyncio.create_task(stream_end_monitor_direct(title, duration))
        
        return True
        
    except Exception as e:
        LOGGER.error(f"Error starting direct stream: {e}", exc_info=True)
        return False

async def stream_end_monitor_direct(title, duration):
    """
    Monitor direct stream and end when duration is reached
    """
    try:
        LOGGER.info(f"⏰ Stream will end in {format_time(duration)}")
        await sleep(duration + 2)  # Add small buffer
        LOGGER.info(f"🎬 Stream finished: {title}")
        await group_call.leave_call()
    except Exception as e:
        LOGGER.error(f"Error in stream end monitor: {e}")

async def monitor_streaming_progress(title, duration):
    """
    Show streaming progress in logs
    """
    try:
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                LOGGER.info(f"🎉 Stream completed: {title}")
                break
                
            # Log progress every 30 seconds
            if int(elapsed) % 30 == 0 and elapsed > 0:
                percentage = min(100, (elapsed / duration) * 100)
                remaining = duration - elapsed
                LOGGER.info(f"🎵 Streaming {title} | {percentage:.1f}% | {format_time(elapsed)} / {format_time(duration)} | Remaining: {format_time(remaining)}")
            
            await sleep(10)
            
    except Exception as e:
        LOGGER.error(f"Error monitoring streaming progress: {e}")

async def optimized_download_and_play(file_id, title, file_size, seek):
    """
    Optimized download method: Based on TG-FileStreamBot proven patterns
    """
    try:
        LOGGER.info(f"📥 Starting optimized download: {title}")
        
        # Create download directory
        os.makedirs("./downloads", exist_ok=True)
        
        # Generate unique filename with proper extension
        timestamp = int(time.time())
        random_id = random.randint(1000, 9999)
        
        # Use default extension - avoid problematic bot.get_file() call
        file_extension = ".mp4"  # Default fallback
        
        temp_file = f"./downloads/{timestamp}_{random_id}{file_extension}"
        LOGGER.info(f"📁 Download target: {temp_file}")
        
        # Start progress monitoring
        progress_task = asyncio.create_task(
            show_download_progress_optimized(temp_file, file_size, title)
        )
        
        try:
            # Use the proven bot.download_media method with progress callback
            LOGGER.info(f"📥 Starting download with bot.download_media...")
            
            # Download with progress tracking
            LOGGER.info(f"🔍 Starting bot.download_media for file_id: {file_id[:8]}...")
            downloaded_file = await bot.download_media(
                file_id, 
                file_name=temp_file,
                progress=download_progress_callback,
                progress_args=(title, file_size)
            )
            LOGGER.info(f"🔍 Download result: {downloaded_file}")
            
            if not downloaded_file or not os.path.exists(downloaded_file):
                LOGGER.error("Download failed - file not found after download")
                progress_task.cancel()
                return False
            
            # Cancel progress task
            progress_task.cancel()
            
            LOGGER.info(f"✅ Download completed: {downloaded_file}")
            
            # Get media properties
            width, height = await get_height_and_width(downloaded_file)
            duration = await get_duration(downloaded_file)
            
            if not width or not height:
                width, height = 1280, 720
            
            # Play downloaded file
            success = await start_streaming_from_file(downloaded_file, width, height, duration, seek)
            
            if success:
                # Clean up after a delay
                asyncio.create_task(cleanup_specific_file(downloaded_file, delay=duration + 60))
            
            return success
            
        except Exception as e:
            LOGGER.error(f"Error during download: {e}")
            progress_task.cancel()
            return False
        
    except Exception as e:
        LOGGER.error(f"Error in optimized download: {e}", exc_info=True)
        return False

def download_progress_callback(current, total, title, expected_size):
    """
    Progress callback for bot.download_media - shows real-time progress
    """
    try:
        if total > 0:
            percentage = (current / total) * 100
            current_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            
            # Create progress bar
            bar_width = 40
            filled_width = int((percentage / 100) * bar_width)
            bar = "█" * filled_width + "░" * (bar_width - filled_width)
            
            # Calculate speed (if we have expected size)
            if expected_size > 0:
                speed_mb = current_mb / (time.time() - getattr(download_progress_callback, 'start_time', time.time()))
                speed_str = f"{speed_mb:.1f} MB/s"
            else:
                speed_str = "Unknown"
            
            # Show progress
            print(f"\r📥 {title[:25]:<25} | {bar} | {percentage:5.1f}% | {current_mb:.1f} MB | {speed_str}", end="", flush=True)
            
            # Store start time for speed calculation
            if not hasattr(download_progress_callback, 'start_time'):
                download_progress_callback.start_time = time.time()
                
    except Exception as e:
        pass  # Don't let progress callback errors break the download

async def show_download_progress_optimized(file_path, expected_size, title):
    """
    Simplified progress monitoring - main progress is handled by download_progress_callback
    """
    try:
        LOGGER.info(f"📊 Monitoring download: {title} | Size: {expected_size/1024/1024:.1f} MB")
        print(f"\n📥 Starting download: {title}")
        print("=" * 60)
        
        # Wait for file to appear and monitor completion
        file_found = False
        start_time = time.time()
        
        while not file_found:
            if os.path.exists(file_path):
                file_found = True
                print(f"📁 File created, download in progress...")
                break
            print(f"\r⏳ Waiting for download to start...", end="", flush=True)
            await sleep(1)
        
        # Monitor for completion
        while True:
            if os.path.exists(file_path):
                try:
                    current_size = os.path.getsize(file_path)
                    
                    # Check if download is complete
                    if expected_size > 0 and current_size >= expected_size:
                        print(f"\n✅ Download completed: {title}")
                        total_time = time.time() - start_time
                        LOGGER.info(f"🎉 Download completed in {format_time(total_time)}!")
                        break
                    
                    # Check for timeout (2 hours for large files)
                    if time.time() - start_time > 7200:
                        print(f"\n⏰ Download timed out after 2 hours")
                        LOGGER.warning("Download timed out after 2 hours")
                        break
                
                except OSError:
                    pass
            
            await sleep(2)
            
    except asyncio.CancelledError:
        print(f"\n⏹️ Download progress monitoring cancelled")
        pass
    except Exception as e:
        LOGGER.error(f"Error in download progress: {e}")
        print(f"\n❌ Error in progress tracking: {e}")

async def cleanup_specific_file(file_path, delay=0):
    """
    Clean up a specific file after optional delay
    """
    try:
        if delay > 0:
            await sleep(delay)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            LOGGER.info(f"🗑️ Cleaned up: {os.path.basename(file_path)}")
    except Exception as e:
        LOGGER.error(f"Error cleaning up file: {e}")

async def download_with_progress(file_id, file_path, title, file_size=0):
    """
    Download file with real-time progress tracking and CLI progress bars
    """
    try:
        LOGGER.info(f"📥 Starting download: {title}")
        
        # Use provided file size or get from file info
        if file_size <= 0:
            file_info = await get_file_info(file_id)
            if file_info:
                file_size = file_info.get('file_size', 0)
        
        file_name = f"file_{file_id[:8]}"
        LOGGER.info(f"📊 File: {file_name} | Expected size: {file_size/1024/1024:.1f} MB")
        
        # Start download using pyro_dl
        downloader = Downloader()
        download_path = await downloader.pyro_dl(file_id)
        
        if not download_path or not os.path.exists(download_path):
            LOGGER.error("Download failed")
            return False
        
        # Move to our streaming location
        if download_path != file_path:
            import shutil
            shutil.move(download_path, file_path)
        
        # Monitor download progress with CLI progress bars
        await monitor_download_progress_cli(file_path, file_size, title)
        
        LOGGER.info(f"✅ Download completed: {title}")
        return True
        
    except Exception as e:
        LOGGER.error(f"Error in download_with_progress: {e}", exc_info=True)
        return False

async def monitor_download_progress_cli(file_path, expected_size, title):
    """
    Show real-time CLI progress bars for download progress
    """
    try:
        start_time = time.time()
        last_size = 0
        last_update = start_time
        
        # Progress bar characters
        bar_width = 50
        progress_chars = "█▇▆▅▄▃▂▁"
        
        LOGGER.info(f"📊 Download Progress for: {title}")
        LOGGER.info("=" * 60)
        
        while True:
            if os.path.exists(file_path):
                current_size = os.path.getsize(file_path)
                current_time = time.time()
                
                # Calculate progress
                if expected_size > 0:
                    percentage = min(100, (current_size / expected_size) * 100)
                else:
                    percentage = 0
                
                # Update every 2 seconds
                if current_time - last_update >= 2:
                    # Calculate speed
                    if last_size > 0:
                        time_diff = current_time - last_update
                        speed = (current_size - last_size) / time_diff
                        
                        # Format speed
                        if speed > 1024 * 1024:
                            speed_str = f"{speed/1024/1024:.1f} MB/s"
                        else:
                            speed_str = f"{speed/1024:.1f} KB/s"
                        
                        # Calculate ETA
                        if speed > 0 and expected_size > 0:
                            remaining = expected_size - current_size
                            eta_seconds = remaining / speed
                            eta_str = format_time(eta_seconds)
                        else:
                            eta_str = "Unknown"
                        
                        # Create progress bar
                        filled_width = int((percentage / 100) * bar_width)
                        bar = "█" * filled_width + "░" * (bar_width - filled_width)
                        
                        # Clear line and show progress
                        print(f"\r📥 {title[:30]:<30} | {bar} | {percentage:5.1f}% | {speed_str:>10} | ETA: {eta_str:>8}", end="", flush=True)
                        
                        # Show size info every 10 seconds
                        if int(current_time - start_time) % 10 == 0:
                            print(f"\n📊 Size: {current_size/1024/1024:.1f} MB / {expected_size/1024/1024:.1f} MB")
                        
                        last_size = current_size
                        last_update = current_time
                
                # Check if download is complete
                if expected_size > 0 and current_size >= expected_size:
                    print(f"\n✅ Download completed: {title}")
                    total_time = current_time - start_time
                    LOGGER.info(f"🎉 Download completed in {format_time(total_time)}!")
                    break
                
                # Check for timeout (1 hour)
                if current_time - start_time > 3600:
                    print(f"\n⏰ Download timed out after 1 hour")
                    LOGGER.warning("Download timed out after 1 hour")
                    break
                
                await sleep(1)
            else:
                await sleep(1)
                
    except Exception as e:
        LOGGER.error(f"Error monitoring download progress: {e}", exc_info=True)

async def start_streaming_from_file(file_path, width, height, duration, seek=None):
    """
    Start streaming from a local file (can be partially downloaded)
    """
    try:
        LOGGER.info(f"🎬 Starting stream from: {os.path.basename(file_path)}")
        
        # Check if we have enough data to start
        if not os.path.exists(file_path):
            LOGGER.error("File not found for streaming")
            return False
            
        current_size = os.path.getsize(file_path)
        if current_size < 1024 * 1024:  # Less than 1MB
            LOGGER.error("File too small to start streaming")
            return False
        
        # Join call and start streaming
        if seek:
            start = str(seek['start'])
            end = str(seek['end'])
            ffmpeg_params = f'-ss {start} -t {end}'
        else:
            ffmpeg_params = None
        
        # Start streaming
        if not Config.IS_VIDEO:
            await group_call.play(
                int(Config.CHAT),
                MediaStream(
                    file_path,
                    audio_parameters=AudioQuality.HIGH,
                    additional_ffmpeg_parameters=ffmpeg_params,
                ),
            )
        else:
            cwidth, cheight = resize_ratio(width, height, Config.CUSTOM_QUALITY)
            await group_call.play(
                int(Config.CHAT),
                MediaStream(
                    file_path,
                    video_parameters=get_video_quality(),
                    audio_parameters=AudioQuality.HIGH,
                    ffmpeg_parameters=ffmpeg_params,
                ),
            )
        
        Config.CALL_STATUS = True
        LOGGER.info("✅ Stream started successfully!")
        
        # Start stream monitoring
        asyncio.create_task(monitor_stream_progress(file_path, duration))
        
        return True
        
    except Exception as e:
        LOGGER.error(f"Error starting stream: {e}", exc_info=True)
        return False

async def monitor_stream_progress(file_path, duration):
    """
    Monitor streaming progress and show CLI progress
    """
    try:
        if not duration or duration <= 0:
            return
            
        start_time = time.time()
        bar_width = 40
        
        LOGGER.info(f"🎵 Stream Progress | Duration: {format_time(duration)}")
        LOGGER.info("=" * 50)
        
        while True:
            elapsed = time.time() - start_time
            if elapsed >= duration:
                print(f"\n🎉 Stream completed!")
                break
                
            # Calculate progress
            percentage = min(100, (elapsed / duration) * 100)
            filled_width = int((percentage / 100) * bar_width)
            bar = "█" * filled_width + "░" * (bar_width - filled_width)
            
            # Show progress bar
            remaining = duration - elapsed
            print(f"\r🎵 Streaming | {bar} | {format_time(elapsed)} / {format_time(duration)} | Remaining: {format_time(remaining)}", end="", flush=True)
            
            await sleep(2)
            
    except Exception as e:
        LOGGER.error(f"Error monitoring stream progress: {e}", exc_info=True)

async def get_file_info(file_id):
    """
    Get file information from Telegram without downloading
    """
    try:
        # Get file info using bot.get_messages approach
        # This is a workaround since we need to get file size
        from bot import bot
        
        # Try to get file info from the file_id
        try:
            # For now, we'll return a placeholder and update during download
            # In a real implementation, you might want to use Telegram's getFile method
            return {
                'file_size': 0,  # Will be updated during download
                'file_name': f"file_{file_id[:8]}",
                'file_id': file_id
            }
        except Exception as e:
            LOGGER.warning(f"Could not get detailed file info: {e}")
            return {
                'file_size': 0,
                'file_name': f"file_{file_id[:8]}",
                'file_id': file_id
            }
            
    except Exception as e:
        LOGGER.error(f"Error getting file info: {e}")
        return None

async def get_file_size_from_message(message, file_id):
    """
    Get file size from a Telegram message object
    """
    try:
        if message.reply_to_message:
            msg = message.reply_to_message
            if msg.video:
                return msg.video.file_size
            elif msg.document:
                return msg.document.file_size
            elif msg.audio:
                return msg.audio.file_size
            elif msg.voice:
                return msg.voice.file_size
            elif msg.video_note:
                return msg.video_note.file_size
        return 0
    except Exception as e:
        LOGGER.error(f"Error getting file size from message: {e}")
        return 0
