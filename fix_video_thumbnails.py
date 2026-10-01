#!/usr/bin/env python3
"""
Fix for video thumbnail loading issues
Improves the reliability of video thumbnail display
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_video_thumbnail_loading():
    """Apply fixes to improve video thumbnail loading"""
    
    print("🔧 Fixing Video Thumbnail Loading Issues")
    print("=" * 50)
    
    # Read the main window file
    main_window_path = "ui/main_window.py"
    
    if not os.path.exists(main_window_path):
        print(f"❌ File not found: {main_window_path}")
        return False
    
    try:
        with open(main_window_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("✅ Main window file loaded")
        
        # Apply fixes
        fixes_applied = 0
        
        # Fix 1: Improve thumbnail URL validation
        old_validation = """# First try preview_url if it's available and looks like a valid image URL
        if 'preview_url' in self.suggestion and self.suggestion['preview_url']:
            preview_url = self.suggestion['preview_url']
            if any(ext in preview_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) or 'images.' in preview_url:
                thumbnail_urls.append(preview_url)"""
        
        new_validation = """# First try preview_url if it's available and looks like a valid image URL
        if 'preview_url' in self.suggestion and self.suggestion['preview_url']:
            preview_url = self.suggestion['preview_url']
            # More comprehensive validation for video thumbnails
            if (any(ext in preview_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']) or 
                'images.' in preview_url or 'thumbnails.' in preview_url or 'cdn.' in preview_url):
                thumbnail_urls.append(preview_url)"""
        
        if old_validation in content:
            content = content.replace(old_validation, new_validation)
            fixes_applied += 1
            print("✅ Applied Fix 1: Improved thumbnail URL validation")
        
        # Fix 2: Add better fallback for video thumbnails
        old_fallback = """# Add fallback URLs for videos if no valid URLs found
        if not thumbnail_urls and self.media_type == "stock_videos":
            # Create a fallback thumbnail URL for videos
            title = self.suggestion.get('title', 'Video')
            fallback_url = f"data:image/svg+xml,%3csvg width='400' height='300' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='100%25' height='100%25' fill='%2310B981'/%3e%3ctext x='50%25' y='50%25' font-size='16' fill='white' text-anchor='middle' dy='.3em'%3e{title[:20]}%3c/text%3e%3c/svg%3e"
            thumbnail_urls.append(fallback_url)"""
        
        new_fallback = """# Add fallback URLs for videos if no valid URLs found
        if not thumbnail_urls and self.media_type == "stock_videos":
            # Create a fallback thumbnail URL for videos
            title = self.suggestion.get('title', 'Video')
            # Try to create a more reliable fallback
            if 'download_url' in self.suggestion and self.suggestion['download_url']:
                # Use download URL as fallback for video thumbnails
                thumbnail_urls.append(self.suggestion['download_url'])
            else:
                # Create SVG fallback
                fallback_url = f"data:image/svg+xml,%3csvg width='400' height='300' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='100%25' height='100%25' fill='%2310B981'/%3e%3ctext x='50%25' y='50%25' font-size='16' fill='white' text-anchor='middle' dy='.3em'%3e{title[:20]}%3c/text%3e%3c/svg%3e"
                thumbnail_urls.append(fallback_url)"""
        
        if old_fallback in content:
            content = content.replace(old_fallback, new_fallback)
            fixes_applied += 1
            print("✅ Applied Fix 2: Better fallback for video thumbnails")
        
        # Fix 3: Improve network request timeout and retry logic
        old_timeout = """request.setTransferTimeout(8000)  # 8 seconds"""
        new_timeout = """request.setTransferTimeout(12000)  # 12 seconds - increased for video thumbnails"""
        
        if old_timeout in content:
            content = content.replace(old_timeout, new_timeout)
            fixes_applied += 1
            print("✅ Applied Fix 3: Increased network timeout for video thumbnails")
        
        # Fix 4: Add better error handling for video thumbnails
        old_error_handling = """# Only log errors for non-placeholder URLs to reduce spam
                if not any(placeholder in current_url for placeholder in ["data:image/svg+xml", "via.placeholder.com", "vimeocdn"]):
                    print(f"Network error loading thumbnail ({self.media_type}): {error_msg}")
                    print(f"URL: {current_url}")"""
        
        new_error_handling = """# Only log errors for non-placeholder URLs to reduce spam
                if not any(placeholder in current_url for placeholder in ["data:image/svg+xml", "via.placeholder.com", "vimeocdn"]):
                    print(f"Network error loading thumbnail ({self.media_type}): {error_msg}")
                    print(f"URL: {current_url}")
                    # For video thumbnails, try alternative loading method
                    if self.media_type == "stock_videos" and self.current_url_index == 0:
                        print(f"🔄 Trying alternative loading for video thumbnail...")
                        QTimer.singleShot(1000, self.try_alternative_video_thumbnail_loading)"""
        
        if old_error_handling in content:
            content = content.replace(old_error_handling, new_error_handling)
            fixes_applied += 1
            print("✅ Applied Fix 4: Better error handling for video thumbnails")
        
        # Fix 5: Add alternative video thumbnail loading method
        alternative_method = """
    def try_alternative_video_thumbnail_loading(self):
        \"\"\"Try alternative method for loading video thumbnails\"\"\"
        try:
            if not hasattr(self, 'thumbnail_label') or self.thumbnail_label is None:
                return
                
            # Try to create a simple colored placeholder with video icon
            title = self.suggestion.get('title', 'Video')
            
            # Create a more attractive fallback thumbnail
            fallback_url = f"data:image/svg+xml,%3csvg width='400' height='300' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='100%25' height='100%25' fill='%2310B981'/%3e%3crect x='10%25' y='10%25' width='80%25' height='80%25' fill='rgba(255,255,255,0.1)' rx='10'/%3e%3cpolygon points='35%25,25%25 35%25,75%25 75%25,50%25' fill='white'/%3e%3ctext x='50%25' y='85%25' font-size='12' fill='white' text-anchor='middle'%3e{title[:15]}%3c/text%3e%3c/svg%3e"
            
            # Create pixmap from SVG data
            pixmap = QPixmap()
            if pixmap.loadFromData(fallback_url.encode()):
                # Scale to fit thumbnail frame
                target_width = 248
                target_height = 140
                scaled_pixmap = pixmap.scaled(
                    target_width, 
                    target_height, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Create final pixmap with background
                final_pixmap = QPixmap(target_width, target_height)
                final_pixmap.fill(QColor("#F9FAFB"))
                
                painter = QPainter(final_pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                x = (target_width - scaled_pixmap.width()) // 2
                y = (target_height - scaled_pixmap.height()) // 2
                painter.drawPixmap(x, y, scaled_pixmap)
                painter.end()
                
                # Set the pixmap
                QTimer.singleShot(0, lambda: self.safe_set_pixmap(final_pixmap, False))
                print(f"✅ Alternative video thumbnail loaded for: {title}")
            else:
                # Fallback to simple placeholder
                self.create_placeholder_image()
                
        except Exception as e:
            print(f"❌ Error in alternative video thumbnail loading: {e}")
            self.create_placeholder_image()
"""
        
        # Find the right place to insert the alternative method (after try_next_url method)
        if "def try_next_url(self):" in content and "def try_alternative_video_thumbnail_loading(self):" not in content:
            # Insert after try_next_url method
            content = content.replace("def try_next_url(self):", "def try_next_url(self):")
            content = content.replace("    def create_placeholder_image(self):", alternative_method + "\n    def create_placeholder_image(self):")
            fixes_applied += 1
            print("✅ Applied Fix 5: Added alternative video thumbnail loading method")
        
        # Write the fixed content back
        with open(main_window_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✅ Successfully applied {fixes_applied} fixes to video thumbnail loading")
        print("🔄 The application will now have more reliable video thumbnail display")
        
        return True
        
    except Exception as e:
        print(f"❌ Error applying fixes: {e}")
        return False

if __name__ == "__main__":
    success = fix_video_thumbnail_loading()
    if success:
        print("\n🎉 Video thumbnail fixes applied successfully!")
        print("💡 Restart the application to see the improvements")
    else:
        print("\n💥 Failed to apply video thumbnail fixes") 