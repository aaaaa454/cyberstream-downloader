from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
import yt_dlp
import logging
import os
import subprocess
import sys

import shutil

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check for ffmpeg
FFMPEG_AVAILABLE = shutil.which('ffmpeg') is not None
if not FFMPEG_AVAILABLE:
    logger.warning("ffmpeg not found! High quality merged downloads (1080p+) may fail. Falling back to single file formats.")

# Serve the frontend
@app.route('/')
def index():
    return send_file('index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_file(path)

@app.route('/api/info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
            
        url = data['url']
        logger.info(f"Fetching info for URL: {url}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # Use 'android' client which often bypasses strict checks
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs', 'js'],
                    # 'include_live_dash': True, # This can cause 'bool' is not iterable error in some versions
                }
            },
            # Add user-agent and referer to avoid "Sign in to confirm you're not a bot"
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
                'Referer': 'https://m.youtube.com/',
            },
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Extract relevant info
                video_data = {
                    'title': info.get('title'),
                    'author': info.get('uploader'),
                    'duration': info.get('duration_string'),
                    'thumbnail': info.get('thumbnail'),
                    'id': info.get('id'),
                    'formats': info.get('formats', []),
                    'filesize': info.get('filesize') or info.get('filesize_approx')
                }
                
                # Check if we have a direct thumbnail URL (often problematic for FB)
                # We can try to proxy it if needed, or just let the frontend handle fallback
                
                return jsonify(video_data)
        except Exception as inner_e:
            logger.warning(f"Failed to extract full info: {str(inner_e)}")
            # Fallback to generic info if extraction fails due to bot detection
            # This allows the user to still try to download
            video_data = {
                'title': 'YouTube Video (Info Restricted)',
                'author': 'Unknown Channel',
                'duration': '--:--',
                'thumbnail': 'https://i.ytimg.com/vi/mq_tK63TTEI/maxresdefault.jpg', # Generic thumbnail
                'id': 'unknown',
                'formats': []
            }
            # Try to parse ID from URL for better thumbnail
            if 'youtube.com' in url or 'youtu.be' in url:
                if 'v=' in url:
                    vid = url.split('v=')[1].split('&')[0]
                    video_data['thumbnail'] = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
                    video_data['id'] = vid
            
            return jsonify(video_data)
            
    except Exception as e:
        logger.error(f"Error fetching video info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download_video():
    url = request.args.get('url')
    quality = request.args.get('quality', 'best')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
        
    logger.info(f"Starting download for URL: {url} with quality: {quality}")
    
    # Detect domain for specific optimizations
    is_youtube = 'youtube.com' in url or 'youtu.be' in url
    is_facebook = 'facebook.com' in url or 'fb.watch' in url
    is_tiktok = 'tiktok.com' in url
    
    # Map quality selection to yt-dlp format
    if FFMPEG_AVAILABLE:
        if quality == '1080p':
            format_str = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
        elif quality == '720p':
            format_str = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
        elif quality == '480p':
            format_str = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
        elif quality == 'mp3':
            format_str = 'bestaudio/best'
        else:
            format_str = 'best'
            
        # Facebook specific format handling
        if is_facebook:
            if quality == 'mp3':
                format_str = 'bestaudio/best'
            else:
                # Facebook often has 'sd' and 'hd' formats, or DASH formats
                # We want to prioritize HD if requested, but fallback gracefully
                if quality == '1080p' or quality == '720p':
                    format_str = 'hd/bestvideo[height>=720]+bestaudio/best'
                else:
                    format_str = 'sd/bestvideo[height<=480]+bestaudio/best'
                    
        # TikTok specific format handling
        if is_tiktok:
             if quality == 'mp3':
                 format_str = 'bestaudio/best'
             else:
                 # TikTok usually has a single video stream, 'best' is usually fine
                 # but sometimes there are watermarked vs non-watermarked
                 format_str = 'best'
                 
    else:
        # Fallback for when ffmpeg is missing - use pre-merged formats
        if quality == 'mp3':
            format_str = 'bestaudio/best' 
        else:
            # Prefer mp4 for compatibility
            target_height = quality.replace("p","") if "p" in quality else "1080"
            format_str = f'best[ext=mp4][height<={target_height}]/best[ext=mp4]/best'
            
            if is_facebook:
                if quality == '1080p' or quality == '720p':
                    format_str = 'hd/best'
                else:
                    format_str = 'sd/best'
            
            if is_tiktok:
                 format_str = 'best'
    
    # Using subprocess to stream data to client
    # This avoids loading the whole file into memory
    # We use yt-dlp to output to stdout (-o -)
    
    cmd = [
        sys.executable, '-m', 'yt_dlp',
        url,
        '-f', format_str,
        '-o', '-',  # Output to stdout
    ]

    # Add YouTube-specific args
    if is_youtube:
        cmd.extend([
            '--extractor-args', 'youtube:player_client=android,web;player_skip=webpage,configs,js',
            '--user-agent', 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
            '--referer', 'https://m.youtube.com/',
        ])
    elif is_facebook:
        cmd.extend([
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            '--referer', 'https://www.facebook.com/',
        ])
    
    # If audio only, we might want to convert, but that requires ffmpeg
    # For now, we'll just download what's available
    
    def generate():
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1024 * 1024  # 1MB buffer
        )
        
        try:
            while True:
                chunk = process.stdout.read(1024 * 1024) # Read 1MB chunks
                if not chunk:
                    break
                yield chunk
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                # Read stderr safely as bytes, then decode with replacement for errors
                error_bytes = process.stderr.read()
                error = error_bytes.decode('utf-8', errors='replace')
                logger.error(f"Download failed: {error}")
                
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            process.kill()

    # Set appropriate headers
    headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="video.mp4"',
    }
    
    return Response(generate(), headers=headers)

if __name__ == '__main__':
    print("CyberStream Backend Server Running on http://localhost:8000")
    app.run(host='0.0.0.0', port=8000, debug=True)
