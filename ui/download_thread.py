#!/usr/bin/env python3
"""
Download thread for handling media downloads
"""

import os
import asyncio
import concurrent.futures
from PyQt6.QtCore import QThread, pyqtSignal
from logic.stock_api_service import StockAPIService

class DownloadThread(QThread):
    """Thread for downloading media files"""
    
    # Signals
    download_progress = pyqtSignal(int, int)  # current, total
    download_complete = pyqtSignal(int, int)  # downloaded, failed
    download_error = pyqtSignal(str)
    
    def __init__(self, media_list, directory):
        super().__init__()
        self.media_list = media_list
        self.directory = directory
        self.stock_service = StockAPIService()
        self._is_cancelled = False
        self.downloaded_files = []  # Track downloaded files for history
        
    def cancel(self):
        """Cancel the download operation"""
        self._is_cancelled = True
        
    def run(self):
        """Run the download operation"""
        try:
            total_files = len(self.media_list)
            downloaded = 0
            failed = 0
            
            for i, media in enumerate(self.media_list):
                if self._is_cancelled:
                    break
                    
                try:
                    # Emit progress immediately
                    self.download_progress.emit(i + 1, total_files)
                    
                    # Get download URL
                    download_url = media.get('download_url')
                    if not download_url:
                        print(f"⚠️ No download URL for media: {media.get('title', 'Unknown')}")
                        failed += 1
                        continue
                    
                    # Generate filename
                    filepath = self._generate_filepath(media, download_url)
                    
                    # Download file with timeout
                    success = self._download_file_with_timeout(download_url, filepath)
                    
                    if success:
                        downloaded += 1
                        print(f"✅ Downloaded: {os.path.basename(filepath)}")
                        
                        # Add to downloaded files list for history
                        self.downloaded_files.append({
                            'file_path': filepath,
                            'original_url': download_url,
                            'chapter': media.get('chapter', ''),
                            'scene': media.get('scene', ''),
                            'title': media.get('title', ''),
                            'media_type': media.get('media_type', '')
                        })
                    else:
                        failed += 1
                        print(f"❌ Failed to download: {os.path.basename(filepath)}")
                        
                except Exception as e:
                    failed += 1
                    print(f"❌ Error downloading media: {e}")
                    
            # Emit completion signal
            self.download_complete.emit(downloaded, failed)
            
        except Exception as e:
            self.download_error.emit(str(e))
    
    def _download_file_with_timeout(self, download_url, filepath):
        """Download a single file with timeout"""
        try:
            import asyncio
            import concurrent.futures
            
            # Use ThreadPoolExecutor for timeout
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._download_file, download_url, filepath)
                return future.result(timeout=30)  # 30 second timeout
        except concurrent.futures.TimeoutError:
            print(f"❌ Download timeout for: {os.path.basename(filepath)}")
            return False
        except Exception as e:
            print(f"❌ Download error: {e}")
            return False
    
    def _generate_filepath(self, media, download_url):
        """Generate filepath for media"""
        # Get chapter and scene information
        chapter_info = media.get('chapter', 'Chapter 1')
        scene_info = media.get('scene', 'Scene 1')
        media_type = 'Video' if media.get('media_type') == 'video' else 'Image'
        
        # Clean chapter and scene names
        chapter_clean = "".join(c for c in chapter_info if c.isalnum() or c in (' ', '-', '_')).rstrip()
        chapter_clean = chapter_clean.replace(' ', '_')[:20]
        
        scene_clean = "".join(c for c in scene_info if c.isalnum() or c in (' ', '-', '_')).rstrip()
        scene_clean = scene_clean.replace(' ', '_')[:20]
        
        # Get title
        title_clean = media.get('title', 'Untitled')[:15]
        title_clean = "".join(c for c in title_clean if c.isalnum() or c in (' ', '-', '_')).rstrip()
        title_clean = title_clean.replace(' ', '_')
        
        # Determine file extension
        if media_type == 'Video':
            if '.mp4' in download_url.lower():
                ext = '.mp4'
            elif '.mov' in download_url.lower():
                ext = '.mov'
            elif '.avi' in download_url.lower():
                ext = '.avi'
            else:
                ext = '.mp4'
        else:
            if any(ext in download_url.lower() for ext in ['.jpg', '.jpeg']):
                ext = '.jpg'
            elif '.png' in download_url.lower():
                ext = '.png'
            elif '.webp' in download_url.lower():
                ext = '.webp'
            else:
                ext = '.jpg'
        
        # Create base filename
        base_filename = f"{chapter_clean}_{scene_clean}_{media_type}_{title_clean}{ext}"
        filepath = os.path.join(self.directory, base_filename)
        
        # Check if file already exists and add counter if needed
        counter = 1
        original_filepath = filepath
        while os.path.exists(filepath):
            name_without_ext = original_filepath.rsplit('.', 1)[0]
            ext = original_filepath.rsplit('.', 1)[1] if '.' in original_filepath else ''
            filepath = f"{name_without_ext}_{counter}.{ext}" if ext else f"{name_without_ext}_{counter}"
            counter += 1
            if counter > 100:  # Prevent infinite loop
                break
                
        return filepath
    
    def _download_file(self, download_url, filepath):
        """Download a single file"""
        try:
            # Use asyncio.run for simple async operations
            return asyncio.run(self.stock_service.download_media(download_url, filepath))
        except Exception as e:
            print(f"❌ Download error: {e}")
            return False 