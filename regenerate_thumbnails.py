#!/usr/bin/env python3
"""
Regenerate all video thumbnails with higher quality
"""
import os
import subprocess
import sys
from pathlib import Path

def get_project_root():
    """Get project root directory"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent

def regenerate_thumbnails():
    """Regenerate all video thumbnails with higher quality"""
    project_root = get_project_root()
    thumbnails_dir = project_root / "thumbnails"
    
    if not thumbnails_dir.exists():
        print("No thumbnails directory found")
        return
    
    # Find all video files in downloads directory
    downloads_dir = project_root / "downloads"
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    
    video_files = []
    if downloads_dir.exists():
        for file_path in downloads_dir.rglob('*'):
            if file_path.suffix.lower() in video_extensions:
                video_files.append(file_path)
    
    print(f"Found {len(video_files)} video files")
    
    # Regenerate thumbnails
    for video_path in video_files:
        try:
            # Generate unique thumbnail filename
            import hashlib
            video_hash = hashlib.md5(str(video_path).encode()).hexdigest()[:8]
            video_name = video_path.stem
            thumbnail_path = thumbnails_dir / f"{video_name}_{video_hash}_thumb.jpg"
            
            # Delete old thumbnail if exists
            if thumbnail_path.exists():
                thumbnail_path.unlink()
                print(f"Deleted old thumbnail: {thumbnail_path.name}")
            
            # Create new high-quality thumbnail
            cmd = [
                'ffmpeg', '-i', str(video_path), 
                '-ss', '00:00:01',  # Extract frame at 1 second
                '-vframes', '1',    # Extract only 1 frame
                '-vf', 'scale=640:360',  # Scale to 640x360 (HD quality)
                '-q:v', '2',  # High quality JPEG
                '-y',  # Overwrite output file
                str(thumbnail_path)
            ]
            
            print(f"Regenerating thumbnail for: {video_path.name}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and thumbnail_path.exists():
                print(f"✅ Created high-quality thumbnail: {thumbnail_path.name}")
            else:
                print(f"❌ Failed to create thumbnail for {video_path.name}: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error processing {video_path.name}: {e}")
    
    print("Thumbnail regeneration complete!")

if __name__ == "__main__":
    regenerate_thumbnails()
