from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
from PyQt6.QtCore import pyqtSignal
from typing import Optional, Tuple


class HighlightableTextWidget(QTextEdit):
    """Custom text widget that can highlight specific character ranges"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlight_format = None
        self.current_highlight_cursor = None
        self.original_text = ""
        
    def set_highlight_color(self, color: QColor, alpha: int = 100):
        """Set the highlight color and transparency"""
        self.highlight_format = QTextCharFormat()
        self.highlight_format.setBackground(QColor(color.red(), color.green(), color.blue(), alpha))
        
    def highlight_range(self, start_index: int, end_index: int):
        """Highlight a specific character range in the text"""
        if not self.highlight_format:
            # Default highlight color (yellow with transparency)
            self.set_highlight_color(QColor(255, 193, 7), 80)  # Yellow with 80 alpha
        
        # Clear any existing highlight first
        self.clear_highlight()
        
        # Get the text content
        text = self.toPlainText()
        text_length = len(text)
        
        # Ensure indices are within bounds
        start_index = max(0, min(start_index, text_length))
        end_index = max(start_index, min(end_index, text_length))
        
        # Adjust start_index to word boundary (start of word)
        start_index = self.find_word_start(text, start_index)
        
        # Adjust end_index to word boundary (end of word)
        end_index = self.find_word_end(text, end_index)
        
        # Create a cursor for the range
        cursor = self.textCursor()
        cursor.setPosition(start_index)
        cursor.setPosition(end_index, QTextCursor.MoveMode.KeepAnchor)
        
        # Apply the highlight format
        cursor.mergeCharFormat(self.highlight_format)
        
        # Store the cursor for later clearing
        self.current_highlight_cursor = cursor
        
        # Clear the selection to avoid blue selection highlight
        cursor.clearSelection()
        self.setTextCursor(cursor)
        
        # Scroll to the highlighted text with smooth animation
        self.scroll_to_position(start_index)
        
    def clear_highlight(self):
        """Clear any existing highlight"""
        try:
            # Method 1: Clear all formatting from the entire document
            cursor = self.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            
            # Reset to default format
            default_format = QTextCharFormat()
            cursor.mergeCharFormat(default_format)
            
            # Clear selection
            cursor.clearSelection()
            self.setTextCursor(cursor)
            
            # Method 2: Force document reload to clear all formatting
            current_text = self.toPlainText()
            self.clear()
            self.setPlainText(current_text)
            
            # Reset the highlight cursor
            self.current_highlight_cursor = None
            
        except Exception as e:
            print(f"Error clearing highlight: {e}")
            # Fallback: try to clear just the stored cursor
            self.current_highlight_cursor = None
    
    def scroll_to_position(self, position: int):
        """Scroll to a specific character position with smooth animation"""
        try:
            # Create a cursor at the target position
            cursor = self.textCursor()
            cursor.setPosition(position)
            self.setTextCursor(cursor)
            
            # Ensure the cursor is visible
            self.ensureCursorVisible()
            
            # Add a small delay to make the scroll more visible
            import time
            time.sleep(0.05)
            
        except Exception as e:
            print(f"Error scrolling to position: {e}")
    
    def find_word_start(self, text: str, position: int) -> int:
        """Find the start of the word at the given position"""
        if position >= len(text):
            return len(text)
        
        # If we're already at the start of a word, return the position
        if position == 0 or not text[position - 1].isalnum():
            return position
        
        # Move backwards to find the start of the word
        start = position
        while start > 0 and text[start - 1].isalnum():
            start -= 1
        
        return start
    
    def find_word_end(self, text: str, position: int) -> int:
        """Find the end of the word at the given position"""
        if position >= len(text):
            return len(text)
        
        # If we're already at the end of a word, return the position
        if position == len(text) or not text[position].isalnum():
            return position
        
        # Move forwards to find the end of the word
        end = position
        while end < len(text) and text[end].isalnum():
            end += 1
        
        return end
            
    def set_text_with_highlight(self, text: str, start_index: Optional[int] = None, end_index: Optional[int] = None):
        """Set text and optionally highlight a range"""
        self.original_text = text
        self.setPlainText(text)
        
        if start_index is not None and end_index is not None:
            self.highlight_range(start_index, end_index)
            
    def get_highlighted_range(self) -> Optional[Tuple[int, int]]:
        """Get the currently highlighted range"""
        if self.current_highlight_cursor:
            return (self.current_highlight_cursor.selectionStart(), self.current_highlight_cursor.selectionEnd())
        return None 