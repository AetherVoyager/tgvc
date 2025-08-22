from utils import LOGGER
from pyrogram.errors import BotInlineDisabled
from pyrogram import Client, filters
from config import Config
from user import group_call
import time
from asyncio import sleep
from pyrogram.raw.functions.channels import GetFullChannel
from pytgcalls import PyTgCalls
from pytgcalls.types import Update
from pyrogram.raw.types import (
    UpdateGroupCall, 
    GroupCallDiscarded, 
    UpdateGroupCallParticipants
)
# In py-tgcalls 2.2.6, these events are handled differently
# We'll need to update the event handlers accordingly
from utils import (
    start_record_stream,
    stop_recording, 
    edit_title, 
    stream_from_link, 
    leave_call, 
    start_stream, 
    skip, 
    sync_to_db,
    scheduler
)

async def is_reply(_, client, message):
    if Config.REPLY_PM:
        return True
    else:
        return False
reply_filter=filters.create(is_reply)

DUMBED=[]
async def dumb_it(_, client, message):
    if Config.RECORDING_DUMP and Config.LISTEN:
        return True
    else:
        return False
rec_filter=filters.create(dumb_it)

@Client.on_message(reply_filter & filters.private & ~filters.bot & filters.incoming & ~filters.service & ~filters.me & ~filters.chat([777000, 454000]))
async def reply(client, message): 
    try:
        inline = await client.get_inline_bot_results(Config.BOT_USERNAME, "ETHO_ORUTHAN_PM_VANNU")
        m=await client.send_inline_bot_result(
            message.chat.id,
            query_id=inline.query_id,
            result_id=inline.results[0].id,
            hide_via=True
            )
        old=Config.msg.get(message.chat.id)
        if old:
            await client.delete_messages(message.chat.id, [old["msg"], old["s"]])
        Config.msg[message.chat.id]={"msg":m.updates[1].message.id, "s":message.message_id}
    except BotInlineDisabled:
        LOGGER.error(f"Error: Inline Mode for @{Config.BOT_USERNAME} is not enabled. Enable from @Botfather to enable PM Permit.")
        await message.answer(f"{Config.REPLY_MESSAGE}\n\n<b>You can't use this bot in your group, for that you have to make your own bot from the [SOURCE CODE](https://github.com/subinps/VCPlayerBot) below.</b>", disable_web_page_preview=True)
    except Exception as e:
        LOGGER.error(e, exc_info=True)
        pass


@Client.on_message(filters.private & filters.media & filters.me & rec_filter)
async def dumb_to_log(client, message):
    if message.video and message.video.file_name == "record.mp4":
        await message.copy(int(Config.RECORDING_DUMP))
        DUMBED.append("video")
    if message.audio and message.audio.file_name == "record.ogg":
        await message.copy(int(Config.RECORDING_DUMP))
        DUMBED.append("audio")
    if Config.IS_VIDEO_RECORD:
        if len(DUMBED) == 2:
            DUMBED.clear()
            Config.LISTEN=False
    else:
        if len(DUMBED) == 1:
            DUMBED.clear()
            Config.LISTEN=False

    
@Client.on_message(filters.service & filters.chat(Config.CHAT))
async def service_msg(client, message):
    if message.service == 'voice_chat_started':
        Config.IS_ACTIVE=True
        k=scheduler.get_job(str(Config.CHAT), jobstore=None) #scheduled records
        if k:
            await start_record_stream()
            LOGGER.info("Resuming recording..")
        elif Config.WAS_RECORDING:
            LOGGER.info("Previous recording was ended unexpectedly, Now resuming recordings.")
            await start_record_stream()#for unscheduled
        a = await client.send(
                GetFullChannel(
                    channel=(
                        await client.resolve_peer(
                            Config.CHAT
                            )
                        )
                    )
                )
        if a.full_chat.call is not None:
            Config.CURRENT_CALL=a.full_chat.call.id
        LOGGER.info("Voice chat started.")
        await sync_to_db()
    elif message.service == 'voice_chat_scheduled':
        LOGGER.info("VoiceChat Scheduled")
        Config.IS_ACTIVE=False
        Config.HAS_SCHEDULE=True
        await sync_to_db()
    elif message.service == 'voice_chat_ended':
        Config.IS_ACTIVE=False
        LOGGER.info("Voicechat ended")
        Config.CURRENT_CALL=None
        if Config.IS_RECORDING:
            Config.WAS_RECORDING=True
            await stop_recording()
        await sync_to_db()
    else:
        pass

@Client.on_raw_update()
async def handle_raw_updates(client: Client, update: Update, user: dict, chat: dict):
    if isinstance(update, UpdateGroupCallParticipants):
        if not Config.CURRENT_CALL:
            a = await client.send(
                GetFullChannel(
                    channel=(
                        await client.resolve_peer(
                            Config.CHAT
                            )
                        )
                    )
                )
            if a.full_chat.call is not None:
                Config.CURRENT_CALL=a.full_chat.call.id
        if Config.CURRENT_CALL and update.call.id == Config.CURRENT_CALL:
            all=update.participants
            old=list(filter(lambda k:k.peer.user_id if hasattr(k.peer,'user_id') else k.peer.channel_id == Config.USER_ID, all))
            if old:
                for me in old:
                    if me.volume:
                        Config.VOLUME=round(int(me.volume)/100)


    if isinstance(update, UpdateGroupCall) and (update.chat_id == int(-1000000000000-Config.CHAT)):
        if update.call is None:
            Config.IS_ACTIVE = False
            Config.CURRENT_CALL=None
            LOGGER.warning("No Active Group Calls Found.")
            if Config.IS_RECORDING:
                Config.WAS_RECORDING=True
                await stop_recording()
                LOGGER.warning("Group call was ended and hence stoping recording.")
            Config.HAS_SCHEDULE = False
            await sync_to_db()
            return

        else:
            call=update.call
            if isinstance(call, GroupCallDiscarded):
                Config.CURRENT_CALL=None
                Config.IS_ACTIVE=False
                if Config.IS_RECORDING:
                    Config.WAS_RECORDING=True
                    await stop_recording()
                LOGGER.warning("Group Call Was ended")
                Config.CALL_STATUS = False
                await sync_to_db()
                return
            Config.IS_ACTIVE=True
            Config.CURRENT_CALL=call.id
            if Config.IS_RECORDING and not call.record_video_active:
                Config.LISTEN=True
                await stop_recording()
                LOGGER.warning("Recording was ended by user, hence stopping the schedules.")
                return
            if call.schedule_date:
                Config.HAS_SCHEDULE=True
            else:
                Config.HAS_SCHEDULE=False
        await sync_to_db()
 
@group_call.on_update()
async def handler(client: PyTgCalls, update: Update):
    # In py-tgcalls 2.2.6, the event system has changed
    # We'll handle basic updates for now
    chat_id = getattr(update, 'chat_id', None)
    if chat_id and chat_id == Config.CHAT:
        # Basic status tracking - can be enhanced later
        pass



# Stream end handling - simplified for py-tgcalls 2.2.6
# We'll handle this through the main update handler

       

