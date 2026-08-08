from quart import Blueprint, Response, request, render_template, redirect
from math import ceil
from re import match as re_match
import asyncio
import time
from logging import getLogger
from hydrogram.errors import FileReferenceExpired
from .error import abort
from bot import TelegramBot
from bot.config import Telegram, Server
from bot.modules.telegram import get_message, get_file_properties
from bot.modules.client_pool import ClientPool

logger = getLogger('bot')

bp = Blueprint('main', __name__)

@bp.route('/')
async def home():
    return redirect(f'https://t.me/{Telegram.BOT_USERNAME}')

@bp.route('/dl/<int:file_id>')
async def transmit_file(file_id):
    file = await get_message(file_id) or abort(404)
    code = request.args.get('code') or abort(401)
    range_header = request.headers.get('Range')

    if code != file.caption.split('/')[0]:
        abort(403)

    file_name, file_size, mime_type = get_file_properties(file)

    start = 0
    end = file_size - 1

    if range_header:
        range_match = re_match(r'bytes=(\d+)-(\d*)', range_header)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
            if start > end or start >= file_size:
                abort(416, 'Requested range not satisfiable')
        else:
            abort(400, 'Invalid Range header')

    content_length = end - start + 1
    tg_chunk_size = 1 * 1024 * 1024  # Hydrogram stream_media chunk size is 1MB
    offset = start // tg_chunk_size
    trim_start = start % tg_chunk_size
    limit = ceil((trim_start + content_length) / tg_chunk_size)

    headers = {
        'Content-Type': mime_type,
        'Content-Disposition': f'inline; filename="{file_name}"',
        'Content-Range': f'bytes {start}-{end}/{file_size}',
        'Accept-Ranges': 'bytes',
        'Content-Length': str(content_length),
        'Cache-Control': 'no-store',
        'X-Accel-Buffering': 'no',  # Disable proxy buffering
    }
    status_code = 206 if range_header else 200

    async def smooth_stream():
        """Smart adaptive streaming with predictive buffering, exact chunk trimming, and auto FileReferenceExpired recovery."""
        nonlocal file
        bytes_sent = 0
        last_speed = None
        smoothing_factor = 0.85
        target_buffer_time = 0.25

        client = ClientPool.get_client()

        # Fetch fresh message context for this worker client to ensure valid file reference
        try:
            target_file = await client.get_messages(Telegram.CHANNEL_ID, message_ids=file_id)
            if not target_file or target_file.empty:
                target_file = file
        except Exception:
            target_file = file

        async def fetch_and_yield(c, f, off, lim, t_start):
            nonlocal bytes_sent, last_speed
            async for chunk in c.stream_media(f, offset=off, limit=lim):
                t1 = time.perf_counter()

                # Trim first chunk if starting offset is within a 1MB block
                if bytes_sent == 0 and t_start > 0:
                    chunk = chunk[t_start:]

                # Trim last chunk if it exceeds remaining content_length
                remaining = content_length - bytes_sent
                if remaining <= 0:
                    break
                if len(chunk) > remaining:
                    chunk = chunk[:remaining]

                # Send chunk
                yield chunk
                bytes_sent += len(chunk)

                # Measure speed
                t2 = time.perf_counter()
                duration = max(t2 - t1, 0.001)
                speed = len(chunk) / duration  # bytes/sec

                # Smooth average speed
                if last_speed:
                    speed = last_speed * smoothing_factor + speed * (1 - smoothing_factor)
                last_speed = speed

                # Adaptive delay to pace stream smoothly
                target_speed = 800_000
                ratio = min(max(speed / target_speed, 0.5), 2.0)

                await asyncio.sleep(max(target_buffer_time / ratio, 0.01))

                if bytes_sent >= content_length:
                    break

        try:
            async for chunk in fetch_and_yield(client, target_file, offset, limit, trim_start):
                yield chunk
        except FileReferenceExpired:
            logger.warning(f"FileReferenceExpired on file_id {file_id}. Refreshing message context...")
            try:
                refreshed_file = await client.get_messages(Telegram.CHANNEL_ID, message_ids=file_id)
                curr_start = start + bytes_sent
                curr_offset = curr_start // tg_chunk_size
                curr_trim = curr_start % tg_chunk_size
                curr_limit = ceil((curr_trim + (content_length - bytes_sent)) / tg_chunk_size)
                async for chunk in fetch_and_yield(client, refreshed_file, curr_offset, curr_limit, curr_trim):
                    yield chunk
            except Exception as e:
                logger.error(f"Failed to recover from FileReferenceExpired: {e}")

    return Response(smooth_stream(), headers=headers, status=status_code)

@bp.route('/stream/<int:file_id>')
async def stream_file(file_id):
    code = request.args.get('code') or abort(401)
    return await render_template('player.html', mediaLink=f'{Server.BASE_URL}/dl/{file_id}?code={code}')
