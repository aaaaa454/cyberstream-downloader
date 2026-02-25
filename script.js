document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    const pasteIndicator = document.getElementById('paste-indicator');
    const loader = document.getElementById('loader');
    const previewCard = document.getElementById('preview-card');
    const downloadBtn = document.getElementById('download-btn');
    const browseBtn = document.getElementById('browse-btn');
    const savePathInput = document.getElementById('savePath');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    
    let fileHandle = null;
    let currentVideoData = null; // Store fetched data

    // Mock Data for Preview
    const mockVideoData = {
        title: "Cyberpunk 2077 - Official Cinematic Trailer",
        author: "Cyberpunk 2077",
        duration: "04:15",
        thumbnail: "https://i.ytimg.com/vi/qIcTM8WX0_U/maxresdefault.jpg"
    };

    // Auto-paste detection simulation
    urlInput.addEventListener('input', (e) => {
        const value = e.target.value;
        if (isValidUrl(value)) {
            showPasteIndicator();
            analyzeLink(value);
            // On mobile, blur to hide keyboard and prevent layout shift
            if (window.innerWidth < 768) {
                urlInput.blur();
            }
        } else if (value.length > 0) {
            // Reset if invalid
            previewCard.classList.add('hidden');
        }
    });

    // Handle paste event specifically
    urlInput.addEventListener('paste', (e) => {
        setTimeout(() => {
            const value = urlInput.value;
            if (isValidUrl(value)) {
                showPasteIndicator();
                analyzeLink(value);
                // On mobile, blur to hide keyboard
                if (window.innerWidth < 768) {
                    urlInput.blur();
                }
            }
        }, 100);
    });
    
    function isValidUrl(url) {
        return url.includes('youtube.com') || 
               url.includes('youtu.be') || 
               url.includes('facebook.com') || 
               url.includes('fb.watch') ||
               url.includes('tiktok.com');
    }
    
    // Handle Save Location Browse
    browseBtn.addEventListener('click', async () => {
        try {
            if ('showSaveFilePicker' in window) {
                // Determine suggested name based on video title if available
                const videoTitle = document.getElementById('video-title').textContent;
                const safeName = videoTitle && videoTitle !== 'Video Title Placeholder' 
                    ? videoTitle.replace(/[^a-z0-9]/gi, '_').toLowerCase() + '.mp4' 
                    : 'cyberpunk_video.mp4';

                const options = {
                    suggestedName: safeName,
                    types: [
                        {
                            description: 'Video File',
                            accept: { 'video/mp4': ['.mp4'] },
                        },
                    ],
                };
                fileHandle = await window.showSaveFilePicker(options);
                savePathInput.value = fileHandle.name; // Browser security prevents showing full path
            } else {
                // Fallback for browsers that don't support the API
                alert('File System Access API not supported in this browser. Simulation mode active.');
                savePathInput.value = 'C:\\Downloads\\cyberpunk_video.mp4';
            }
        } catch (err) {
            console.error(err);
            // User cancelled or error
        }
    });

    function showPasteIndicator() {
        pasteIndicator.classList.remove('hidden');
        setTimeout(() => {
            pasteIndicator.classList.add('hidden');
        }, 3000);
    }

    async function analyzeLink(url) {
        // Reset UI
        previewCard.classList.add('hidden');
        progressContainer.classList.add('hidden');
        loader.classList.remove('hidden');
        savePathInput.value = ''; // Reset save path
        fileHandle = null;
        
        try {
            const response = await fetch('/api/info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();
            
            if (response.ok) {
                currentVideoData = data; // Store for later use
                // Populate Preview Card
                document.getElementById('video-title').textContent = data.title;
                document.getElementById('video-author').innerHTML = `<i class="fa-solid fa-user"></i> ${data.author}`;
                document.getElementById('video-duration').innerHTML = `<i class="fa-solid fa-clock"></i> ${data.duration}`;
                
                // Handle different thumbnail formats
                const thumbnailImg = document.getElementById('video-thumbnail');
                // Use a proxy or default image for FB since direct links often expire or have CORS issues
                if (data.thumbnail && !data.thumbnail.includes('fbcdn.net') && !data.thumbnail.includes('tiktokcdn.com')) {
                     thumbnailImg.src = data.thumbnail;
                } else if (data.thumbnail) {
                    // It's a FB or TikTok link, try it, but have backup
                    thumbnailImg.src = data.thumbnail;
                    thumbnailImg.onerror = function() {
                        if (data.thumbnail.includes('tiktokcdn.com')) {
                             this.src = 'https://via.placeholder.com/640x360?text=TikTok+Video';
                        } else {
                             this.src = 'https://via.placeholder.com/640x360?text=Facebook+Video';
                        }
                    };
                } else {
                    thumbnailImg.src = 'https://via.placeholder.com/640x360?text=No+Thumbnail';
                }
                
                // Show Preview Card
                loader.classList.add('hidden');
                previewCard.classList.remove('hidden');
            } else {
                alert(`Error: ${data.error}`);
                loader.classList.add('hidden');
            }
        } catch (error) {
            console.error('Error fetching video info:', error);
            alert('Failed to connect to server. Ensure backend is running.');
            loader.classList.add('hidden');
        }
    }

    function showPreview(data) {
        const videoTitle = document.getElementById('video-title');
        const videoAuthor = document.getElementById('video-author');
        const videoDuration = document.getElementById('video-duration');
        const videoThumbnail = document.getElementById('video-thumbnail');
        
        videoThumbnail.src = data.thumbnail || mockVideoData.thumbnail;
        videoTitle.textContent = data.title || "Unknown Title";
        videoAuthor.innerHTML = `<i class="fa-solid fa-user"></i> ${data.author || "Unknown Channel"}`;
        videoDuration.innerHTML = `<i class="fa-solid fa-clock"></i> ${data.duration || "00:00"}`;

        previewCard.classList.remove('hidden');
    }

    downloadBtn.addEventListener('click', () => {
        if (!savePathInput.value) {
            // Flash red to indicate required field
            savePathInput.style.borderColor = "red";
            setTimeout(() => savePathInput.style.borderColor = "#333", 500);
            
            // If no path selected, we can prompt or just start default download
            // For this user request "ask user where to save", we should probably enforce it or auto-prompt
            if ('showSaveFilePicker' in window && !fileHandle) {
                browseBtn.click(); // Trigger the browse dialog
                return;
            } else if (!fileHandle) {
                // Simulation fallback
                savePathInput.value = 'C:\\Downloads\\cyberpunk_video.mp4';
            }
        }
        
        const quality = document.getElementById('quality-select').value;
        const url = urlInput.value;
        startDownload(url, quality);
    });

    async function startDownload(url, quality) {
        downloadBtn.disabled = true;
        downloadBtn.querySelector('span').textContent = "INITIALIZING...";
        
        progressContainer.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressText.textContent = '0%';
        
        try {
            const response = await fetch(`/api/download?url=${encodeURIComponent(url)}&quality=${quality}`);
            
            if (!response.ok) {
                // Try to read error message
                const errorText = await response.text();
                throw new Error(errorText || 'Download failed');
            }
            
            // Check content length to verify it's not empty
            const contentLength = +response.headers.get('Content-Length');
            if (contentLength === 0) {
                 throw new Error('Empty file received from server');
            }

            const reader = response.body.getReader();
            
            // If we have a file handle, create a writable stream
            let writable = null;
            let chunks = [];
            if (fileHandle) {
                writable = await fileHandle.createWritable();
            }

            // Progress tracking
            let receivedLength = 0;
            // Content-Length might not be available for chunked encoding, but we can try
            let contentLength = +response.headers.get('Content-Length');
            
            // Fallback to metadata filesize if header is missing
            if (!contentLength && currentVideoData && currentVideoData.filesize) {
                contentLength = currentVideoData.filesize;
            }
            
            downloadBtn.querySelector('span').textContent = "DOWNLOADING...";
            
            // Speed calculation variables
            let startTime = Date.now();
            let lastUpdate = startTime;
            let lastReceived = 0;

            while(true) {
                const {done, value} = await reader.read();
                
                if (done) {
                    break;
                }
                
                if (writable) {
                    await writable.write(value);
                } else {
                    chunks.push(value);
                }
                
                receivedLength += value.length;
                
                // Throttle UI updates to every 200ms
                const now = Date.now();
                if (now - lastUpdate > 200) {
                    // Calculate Speed
                    const timeDiff = (now - lastUpdate) / 1000; // in seconds
                    const bytesDiff = receivedLength - lastReceived;
                    const speed = bytesDiff / timeDiff; // bytes per second
                    
                    // Format Speed
                    let speedText = '';
                    if (speed > 1024 * 1024) {
                        speedText = `${(speed / (1024 * 1024)).toFixed(2)} MB/s`;
                    } else {
                        speedText = `${(speed / 1024).toFixed(2)} KB/s`;
                    }
                    
                    // Update progress bar
                    if (contentLength) {
                        const percent = Math.min((receivedLength / contentLength) * 100, 99);
                        progressBar.style.width = `${percent}%`;
                        
                        // Format Size: 15.2 MB / 34.5 MB
                        const currentSize = (receivedLength / (1024 * 1024)).toFixed(1);
                        const totalSize = (contentLength / (1024 * 1024)).toFixed(1);
                        
                        progressText.textContent = `${Math.floor(percent)}% | ${currentSize} MB / ${totalSize} MB | ${speedText}`;
                    } else {
                        // Indeterminate
                        const mb = (receivedLength / (1024 * 1024)).toFixed(1);
                        progressText.textContent = `${mb} MB | ${speedText}`;
                        progressBar.style.width = '100%';
                        progressBar.classList.add('indeterminate'); 
                    }
                    
                    lastUpdate = now;
                    lastReceived = receivedLength;
                }
            }
            
            if (writable) {
                await writable.close();
            } else {
                // Fallback download if no file handle (e.g. user canceled or unsupported)
                const blob = new Blob(chunks, { type: 'video/mp4' });
                const blobUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                
                // Try to get filename from Content-Disposition header
                let filename = 'downloaded_video.mp4';
                const disposition = response.headers.get('Content-Disposition');
                if (disposition && disposition.includes('filename=')) {
                    const matches = disposition.match(/filename="?([^"]+)"?/);
                    if (matches && matches[1]) {
                        filename = matches[1];
                    }
                }
                
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(blobUrl);
                chunks = []; // Free memory
            }
            
            progressBar.style.width = '100%';
            progressText.textContent = '100%';
            finishDownload();
            
        } catch (error) {
            console.error('Download error:', error);
            downloadBtn.disabled = false;
            downloadBtn.querySelector('span').textContent = "ERROR - TRY AGAIN";
            setTimeout(() => {
                 downloadBtn.querySelector('span').textContent = "INITIALIZE DOWNLOAD";
            }, 3000);
        }
    }

    function finishDownload() {
        downloadBtn.querySelector('span').textContent = "DOWNLOAD COMPLETE";
        downloadBtn.style.borderColor = "#00ff00";
        downloadBtn.style.color = "#00ff00";
        downloadBtn.style.boxShadow = "0 0 20px #00ff00";
        
        setTimeout(() => {
            // Reset after 3 seconds
            downloadBtn.disabled = false;
            downloadBtn.querySelector('span').textContent = "INITIALIZE DOWNLOAD";
            downloadBtn.style = ""; // Reset styles
            progressContainer.classList.add('hidden');
            savePathInput.value = ""; // Clear path for next time
            fileHandle = null;
            progressBar.classList.remove('indeterminate');
        }, 3000);
    }
});
