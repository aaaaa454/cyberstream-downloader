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

# Helper function to get ydl options
def get_ydl_opts(client='android'):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.youtube.com/',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    
    if client == 'android':
        opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'configs', 'js'],
            }
        }
    elif client == 'ios':
        opts['extractor_args'] = {
            'youtube': {
                'player_client': ['ios', 'web'],
                'player_skip': ['webpage', 'configs', 'js'],
            }
        }
        opts['http_headers']['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
    elif client == 'web':
        opts['extractor_args'] = {
            'youtube': {
                'player_client': ['web'],
                'player_skip': ['webpage', 'configs', 'js'],
            }
        }
    
    return opts

@app.route('/')
def index():
    return send_file(os.path.join(app.root_path, 'index.html'))

@app.route('/<path:path>')
def static_files(path):
    file_path = os.path.join(app.root_path, path)
    if os.path.exists(file_path):
        return send_file(file_path)
    return "File not found", 404

@app.route('/api/info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
            
        url = data['url']
        logger.info(f"Fetching info for URL: {url}")
        
        # Try multiple clients in order
        clients = ['android', 'web', 'ios']
        info = None
        last_error = None
        
        for client in clients:
            try:
                logger.info(f"Trying with client: {client}")
                ydl_opts = get_ydl_opts(client)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        break
            except Exception as e:
                logger.warning(f"Client {client} failed: {str(e)}")
                last_error = e
        
        if not info:
             # If all failed, fallback to generic info but indicate restriction
             logger.error(f"All clients failed. Last error: {str(last_error)}")
             
             # Fallback Logic
             video_data = {
                'title': 'Video Access Restricted (Try a different link)',
                'author': 'Unknown Channel',
                'duration': '--:--',
                'thumbnail': 'https://via.placeholder.com/640x360?text=Restricted',
                'id': 'unknown',
                'formats': [],
                'error': str(last_error)
            }
             
             if 'youtube.com' in url or 'youtu.be' in url:
                if 'v=' in url:
                    vid = url.split('v=')[1].split('&')[0]
                    video_data['thumbnail'] = f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
                    video_data['id'] = vid
             
             return jsonify(video_data)

        # Success path
        video_data = {
            'title': info.get('title'),
            'author': info.get('uploader'),
            'duration': info.get('duration_string'),
            'thumbnail': info.get('thumbnail'),
            'id': info.get('id'),
            'formats': info.get('formats', []),
            'filesize': info.get('filesize') or info.get('filesize_approx')
        }
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
    
    # Detect domain
    is_facebook = 'facebook.com' in url or 'fb.watch' in url
    is_tiktok = 'tiktok.com' in url
    
    # Map quality
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
            
        if is_facebook:
            if quality == 'mp3':
                format_str = 'bestaudio/best'
            else:
                if quality == '1080p' or quality == '720p':
                    format_str = 'hd/bestvideo[height>=720]+bestaudio/best'
                else:
                    format_str = 'sd/bestvideo[height<=480]+bestaudio/best'
        if is_tiktok:
             format_str = 'best' if quality != 'mp3' else 'bestaudio/best'
                 
    else:
        if quality == 'mp3':
            format_str = 'bestaudio/best' 
        else:
            target_height = quality.replace("p","") if "p" in quality else "1080"
            format_str = f'best[ext=mp4][height<={target_height}]/best[ext=mp4]/best'
            
            if is_facebook:
                format_str = 'hd/best' if quality in ['1080p', '720p'] else 'sd/best'
            if is_tiktok:
                 format_str = 'best'
    
    # Try clients sequentially for download too
    # Note: subprocess makes it hard to switch clients mid-stream
    # So we will try to use the 'android' client first as it's most robust usually
    # If users report issues, we might need to expose client selection in UI or retry logic
    
    cmd = [
        sys.executable, '-m', 'yt_dlp',
        url,
        '-f', format_str,
        '-o', '-',
        '--quiet',
        '--no-warnings',
        '--no-check-certificate',
        '--geo-bypass',
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        '--referer', 'https://www.youtube.com/',
        '--extractor-args', 'youtube:player_client=android,web;player_skip=webpage,configs,js'
    ]
    
    logger.info(f"Executing command: {' '.join(cmd)}")
    
    def generate():
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1024 * 1024
        )
        
        # Check if process failed immediately
        # We can't easily peek stdout without blocking, so we iterate
        first_chunk = True
        
        try:
            while True:
                chunk = process.stdout.read(1024 * 1024)
                if not chunk:
                    break
                first_chunk = False
                yield chunk
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code != 0:
                error_bytes = process.stderr.read()
                error = error_bytes.decode('utf-8', errors='replace')
                logger.error(f"Download failed with code {return_code}: {error}")
                # If first chunk, we can yield error (but it might corrupt video file if client expects binary)
                # But better than 0MB silent failure
                if first_chunk:
                     # Raise to trigger 500 in flask if possible? 
                     # Response is already started, so we can't change status code easily
                     pass 
                
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            process.kill()

    # We need to sanitize filename
    filename = "CyberStream_Video.mp4"
    if quality == 'mp3':
        filename = "CyberStream_Audio.mp3"
        
    headers = {
        'Content-Type': 'application/octet-stream',
        'Content-Disposition': f'attachment; filename="{filename}"',
    }
    
    return Response(generate(), headers=headers)

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == '__main__':
    print("CyberStream Backend Server Running on http://localhost:8000")
    app.run(host='0.0.0.0', port=8000, debug=True)
