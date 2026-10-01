from PyQt6.QtCore import QThread, pyqtSignal
from typing import Dict, Any, List
from logic.smart_scene_analysis import analyze_scene_in_background, get_scenes_to_analyze_in_background

class SmartAnalysisThread(QThread):
    """Background thread for smart scene analysis"""
    progress_updated = pyqtSignal(float, str)
    analysis_complete = pyqtSignal(list)
    analysis_error = pyqtSignal(str)
    scene_analyzed = pyqtSignal(int, dict)  # scene_index, scene_data
    
    def __init__(self, text: str, settings: Dict[str, Any], user_id: str = None, cost_tracking_service = None, scene_cost_tracking_service = None):
        super().__init__()
        self.text = text
        # Create a deep copy of settings to ensure it's not modified
        self.settings = settings.copy() if settings else {}
        self.user_id = user_id
        self.cost_tracking_service = cost_tracking_service
        self.scene_cost_tracking_service = scene_cost_tracking_service
        
    def run(self):
        try:
            from logic.smart_scene_analysis import process_text_smart
            

            
            def progress_callback(current, total, scene_text):
                progress = current / total
                self.progress_updated.emit(progress, f"Analyzing scene {current}/{total}...")
                
            scenes_data = process_text_smart(
                self.text, 
                progress_callback, 
                self.settings,
                user_id=self.user_id,
                cost_tracking_service=self.cost_tracking_service,
                scene_cost_tracking_service=self.scene_cost_tracking_service
            )
            
            # Save results
            from logic.utils import write_json_output
            write_json_output(scenes_data)
            
            self.analysis_complete.emit(scenes_data)
            
        except Exception as e:
            self.analysis_error.emit(str(e))

class BackgroundSceneAnalysisThread(QThread):
    """Background thread for analyzing individual micro-scenes"""
    scene_analysis_complete = pyqtSignal(int, dict)  # scene_index, scene_data
    scene_analysis_error = pyqtSignal(int, str)      # scene_index, error_message
    
    def __init__(self, scene_index: int, scene_data: Dict[str, Any], settings: Dict[str, Any], user_id=None, cost_tracking_service=None, scene_cost_tracking_service=None):
        super().__init__()
        self.scene_index = scene_index
        self.scene_data = scene_data
        self.settings = settings
        self.user_id = user_id
        self.cost_tracking_service = cost_tracking_service
        self.scene_cost_tracking_service = scene_cost_tracking_service
        
    def run(self):
        try:
            from logic.smart_scene_analysis import analyze_scene_in_background
            
            # Analyze the micro-scene
            result = analyze_scene_in_background(self.scene_index, self.scene_data, self.settings, None, self.user_id, self.cost_tracking_service, self.scene_cost_tracking_service)
            
            if result:
                self.scene_analysis_complete.emit(self.scene_index, result)
            else:
                self.scene_analysis_error.emit(self.scene_index, "Failed to analyze micro-scene")
                
        except Exception as e:
            self.scene_analysis_error.emit(self.scene_index, str(e))

class SmartLazyLoadingThread(QThread):
    """Background thread for smart lazy loading of scene media"""
    scene_media_ready = pyqtSignal(int, dict)  # scene_index, media_data
    scene_media_error = pyqtSignal(int, str)   # scene_index, error_message
    
    def __init__(self, scene_data: Dict[str, Any], scene_index: int, settings: Dict[str, Any], user_id=None, cost_tracking_service=None, scene_cost_tracking_service=None):
        super().__init__()
        self.scene_data = scene_data
        self.scene_index = scene_index
        self.settings = settings
        self.user_id = user_id
        self.cost_tracking_service = cost_tracking_service
        self.scene_cost_tracking_service = scene_cost_tracking_service
        
    def run(self):
        try:
            from logic.scene_analysis import generate_visual_suggestions
            
            # Generate media suggestions for this scene
            suggestions = generate_visual_suggestions(self.scene_data, self.settings, self.user_id, self.cost_tracking_service, self.scene_cost_tracking_service)
            
            # Emit success signal with media data
            self.scene_media_ready.emit(self.scene_index, suggestions)
            
        except Exception as e:
            # Emit error signal
            self.scene_media_error.emit(self.scene_index, str(e)) 