from .logger import LOGGER
# from .debug import debug  # Temporarily commented out to fix circular import
from .database import get_db
db = get_db()  # Initialize database instance
from .utils import (
    play, start_stream, startup_check, sync_from_db, check_changes,
    cancel_all_schedules, clear_db_playlist, edit_title, leave_call,
    skip, stream_from_link, start_record_stream, stop_recording,
    delete_messages, get_admins, get_buttons, get_playlist_str,
    mute, unmute, pause, resume, volume, recorder_settings, restart,
    restart_playout, schedule_a_play, seek_file, set_config, settings_panel,
    shuffle_playlist, sync_to_db, volume_buttons, edit_config, is_admin, update,
    chat_filter, sudo_filter, add_to_db_playlist, download, get_duration,
    get_link, import_play_list, is_audio, send_playlist, c_play,
    is_ytdl_supported, get_song_and_artist, scheduler, play_direct_file,
    chek_the_media, join_call, sleep, bot, stream_while_downloading,
    start_streaming_from_file, get_file_info, get_file_size_from_message,
    optimized_download_and_play, cleanup_specific_file, play_file_simple
)
# from .pyro_dl import Downloader  # Temporarily commented out to fix circular import