import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import yt_dlp

# Your Telegram API Token has been successfully injected here
API_TOKEN = "8686466337:AAEOeA9w1naJKGrrUIZEHKODlNl_FdpciRY"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Temp storage for search results
search_cache = {}

# 1. Start Command Handler
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("Hello! Send me any song name or artist, and I will find it for you! 🎵")

# 2. Search Music Logic via Text Message
@dp.message()
async def search_music(message: types.Message):
    query = message.text.strip()
    if not query:
        return

    waiting_msg = await message.answer("🔍 Searching for '" + query + "'... Please wait.")
    
    # Configure yt-dlp to search for top 4 tracks without downloading them yet
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search YouTube Music backend for top results
            search_results = ydl.extract_info(f"ytsearch4:{query}", download=False)
            
            if 'entries' not in search_results or len(search_results['entries']) == 0:
                await waiting_msg.edit_text("❌ No songs found. Try another title!")
                return
            
            # Create interactive inline keyboard grid
            builder = InlineKeyboardBuilder()
            user_id = str(message.from_user.id)
            search_cache[user_id] = {}
            
            for index, entry in enumerate(search_results['entries']):
                title = entry.get('title', 'Unknown Track')
                video_url = entry.get('url') or f"https://youtube.com{entry.get('id')}"
                
                # Trim title if it's too long for telegram buttons
                short_title = title[:45] + "..." if len(title) > 45 else title
                callback_id = f"track_{index}"
                
                # Cache url under short indexes to bypass 64-byte telegram limits
                search_cache[user_id][callback_id] = {
                    "url": video_url,
                    "title": title
                }
                
                builder.button(text=f"🎵 {short_title}", callback_data=f"{user_id}:{callback_id}")
            
            builder.adjust(1) # Stack buttons vertically
            
            await waiting_msg.delete()
            await message.answer("🎶 Here is what I found. Make your choice:", reply_markup=builder.as_markup())
            
    except Exception as e:
        await waiting_msg.edit_text("⚠️ An error occurred during search. Try again later.")

# 3. Callback Handler (When user clicks on a song from the stack)
@dp.callback_query()
async def download_and_send_song(callback_query: types.CallbackQuery):
    data = callback_query.data.split(":")
    if len(data) < 2:
        return
        
    target_user_id = data[0]
    callback_id = data[1]
    
    # Validate cache security context
    if target_user_id != str(callback_query.from_user.id) or target_user_id not in search_cache:
        await callback_query.answer("⚠️ This search stack expired. Please search again!", show_alert=True)
        return
        
    track_info = search_cache[target_user_id].get(callback_id)
    if not track_info:
        await callback_query.answer("❌ Error: Track not found in cache.", show_alert=True)
        return
    
    await callback_query.message.edit_text("📥 Downloading '" + track_info['title'] + "'... This takes a few seconds.")
    
    # Configure production downloader options
    output_filename = f"song_{callback_query.from_user.id}.mp3"
    ydl_download_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_filename,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True
    }
    
    try:
        # Run synchronous downloader block in parallel process pool
        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_download_opts).download([track_info['url']]))
        
        # Verify physical file conversion completion
        if os.path.exists(output_filename):
            await callback_query.message.delete()
            
            # Send the real audio (.mp3) directly to user
            await callback_query.message.answer_audio(
                audio=types.FSInputFile(output_filename),
                caption=f"✅ Enjoy your music, Darling! Shared via Bot."
            )
            
            # Safe disk optimization delete
            os.remove(output_filename)
        else:
            await callback_query.message.edit_text("❌ Failed to process audio conversion.")
            
    except Exception as e:
        await callback_query.message.edit_text("⚠️ Download error. Try another song.")
        if os.path.exists(output_filename):
            os.remove(output_filename)

# Start Application Polling
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
