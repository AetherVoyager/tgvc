from utils import (
    play, 
    start_stream,
    startup_check, 
    sync_from_db,
    check_changes
)
from user import group_call, USER
from utils import LOGGER
from config import Config
from pyrogram import idle
from bot import bot
import asyncio
import os
import signal
import sys

# Global variables for graceful shutdown
shutdown_event = asyncio.Event()
shutdown_task = None
shutdown_in_progress = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_in_progress
    if shutdown_in_progress:
        print(f"\n🛑 Force exit requested...")
        sys.exit(1)
    
    print(f"\n🛑 Received signal {signum}. Starting graceful shutdown...")
    shutdown_in_progress = True
    if shutdown_task:
        shutdown_task.set()
    else:
        sys.exit(0)

async def graceful_shutdown():
    """Perform graceful shutdown of all services"""
    try:
        print("🔄 Stopping group call...")
        from user import group_call
        try:
            await asyncio.wait_for(group_call.leave_call(), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            print("⚠️ Group call stop timed out or failed")
        
        print("🔄 Stopping bot...")
        try:
            await asyncio.wait_for(bot.stop(), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            print("⚠️ Bot stop timed out or failed")
        
        print("🔄 Stopping user client...")
        try:
            from user import USER
            await asyncio.wait_for(USER.stop(), timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            print("⚠️ User client stop timed out or failed")
        
        print("✅ Graceful shutdown completed!")
        
    except Exception as e:
        print(f"❌ Error during shutdown: {e}")
    finally:
        print("🚪 Exiting...")
        os._exit(0)  # Force exit

if Config.DATABASE_URI:
    from utils.database import get_db
    db = get_db()


async def main():
    global shutdown_task
    shutdown_task = asyncio.Event()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await bot.start()
    Config.BOT_USERNAME = (await bot.get_me()).username
    LOGGER.info(f"{Config.BOT_USERNAME} Started.")
    if Config.DATABASE_URI:
        try:
            if await db.is_saved("RESTART"):
                msg=await db.get_config("RESTART")
                if msg:
                    try:
                        k=await bot.edit_message_text(msg['chat_id'], msg['msg_id'], text="Succesfully restarted.")
                        await db.del_config("RESTART")
                    except:
                        pass
            await check_changes()
            await sync_from_db()
        except Exception as e:
            LOGGER.error(f"Errors occured while setting up database for VCPlayerBot, check the value of DATABASE_URI. Full error - {str(e)}", exc_info=True)
            Config.STARTUP_ERROR="Errors occured while setting up database for VCPlayerBot, check the value of DATABASE_URI. Full error - {str(e)}"
            LOGGER.info("Activating debug mode, you can reconfigure your bot with /env command.")
            await bot.stop()
            from utils import debug
            await debug.start()
            await idle()
            return

    if Config.DEBUG:
        LOGGER.info("Debugging enabled by user, Now in debug mode.")
        Config.STARTUP_ERROR="Debugging enabled by user, Now in debug mode."
        from utils import debug
        await bot.stop()
        await debug.start()
        await idle()
        return

    try:
        await group_call.start()
        Config.USER_ID = (await USER.get_me()).id
        k=await startup_check()
        if k == False:
            LOGGER.error("Startup checks not passed , bot is quiting")
            await bot.stop()
            LOGGER.info("Activating debug mode, you can reconfigure your bot with /env command.")
            from utils import debug
            await debug.start()
            await idle()
            return

        if Config.IS_LOOP:
            if Config.playlist:
                await play()
                LOGGER.info("Loop play enabled and playlist is not empty, resuming playlist.")
            else:
                LOGGER.info("Loop play enabled , starting playing startup stream.")
                await start_stream()
    except Exception as e:
        if "unpack requires" in str(e):
            LOGGER.error("You Have to generate a new session string from the link given in README of the repo and replace the existing one with the new.")
            LOGGER.info("Activating debug mode, you can reconfigure your bot with /env command.")
            Config.STARTUP_ERROR=f"You Have to generate a new session string from the link given in README of the repo and replace the existing one with the new. \nGenerate string session from https://repl.it/@subinps/getStringName"
        else:
            LOGGER.error(f"Startup was unsuccesfull, Errors - {e}", exc_info=True)
            LOGGER.info("Activating debug mode, you can reconfigure your bot with /env command.")
            Config.STARTUP_ERROR=f"Startup was unsuccesfull, Errors - {e}"
        from utils import debug
        await bot.stop()
        await debug.start()
        await idle()
        return

    # Wait for shutdown signal or idle
    try:
        await asyncio.wait_for(shutdown_task.wait(), timeout=None)
    except asyncio.TimeoutError:
        pass
    
    # Perform graceful shutdown with timeout
    try:
        await asyncio.wait_for(graceful_shutdown(), timeout=15.0)
    except asyncio.TimeoutError:
        print("⏰ Shutdown timed out, forcing exit...")
        os._exit(1)

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())



