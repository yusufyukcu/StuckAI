#!/usr/bin/env python3
"""
Test script to verify installer mode path resolution
"""
import sys
import os

def get_project_root():
    """Get the project root directory, always uses user data directory for compiled mode"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable - always use user data directory
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        user_data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "StuckAI")
        os.makedirs(user_data_dir, exist_ok=True)
        project_root = user_data_dir
        print(f"🔍 DEBUG: get_project_root (installer mode): {project_root}")
        
        # Migrate data from exe directory if it exists
        migrate_data_from_exe_dir(exe_dir, project_root)
        
        print(f"🔍 DEBUG: sys.executable: {sys.executable}")
        return project_root
    else:
        # Running as script - get the directory containing this file
        project_root = os.path.dirname(os.path.abspath(__file__))
        print(f"🔍 DEBUG: get_project_root (script): {project_root}")
        print(f"🔍 DEBUG: __file__: {__file__}")
        return project_root

def migrate_data_from_exe_dir(exe_dir: str, user_data_dir: str):
    """Migrate data from exe directory to user data directory if needed"""
    try:
        exe_data_dir = os.path.join(exe_dir, 'data')
        exe_history_dir = os.path.join(exe_dir, 'history')
        
        if not os.path.exists(exe_data_dir) and not os.path.exists(exe_history_dir):
            return  # No data to migrate
        
        print(f"🔍 DEBUG: Migrating data from {exe_dir} to {user_data_dir}")
        
        # Create user data directories
        user_data_data_dir = os.path.join(user_data_dir, 'data')
        user_data_history_dir = os.path.join(user_data_dir, 'history')
        os.makedirs(user_data_data_dir, exist_ok=True)
        os.makedirs(user_data_history_dir, exist_ok=True)
        
        # Migrate data directory
        if os.path.exists(exe_data_dir):
            import shutil
            for item in os.listdir(exe_data_dir):
                src = os.path.join(exe_data_dir, item)
                dst = os.path.join(user_data_data_dir, item)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    print(f"🔍 DEBUG: Migrated file: {item}")
        
        # Migrate history directory
        if os.path.exists(exe_history_dir):
            import shutil
            for item in os.listdir(exe_history_dir):
                src = os.path.join(exe_history_dir, item)
                dst = os.path.join(user_data_history_dir, item)
                if os.path.isdir(src) and not os.path.exists(dst):
                    shutil.copytree(src, dst)
                    print(f"🔍 DEBUG: Migrated history folder: {item}")
        
        print(f"✅ Data migration completed")
        
    except Exception as e:
        print(f"⚠️ Error during data migration: {e}")

def test_paths():
    """Test path resolution"""
    print("=" * 60)
    print("INSTALLER MODE PATH TEST")
    print("=" * 60)
    
    project_root = get_project_root()
    
    # Test data paths
    data_dir = os.path.join(project_root, 'data')
    history_dir = os.path.join(project_root, 'history')
    
    print(f"\nProject Root: {project_root}")
    print(f"Data Directory: {data_dir}")
    print(f"History Directory: {history_dir}")
    
    print(f"\nData dir exists: {os.path.exists(data_dir)}")
    print(f"History dir exists: {os.path.exists(history_dir)}")
    
    # Test specific files
    history_file = os.path.join(data_dir, 'analysis_history.json')
    downloads_file = os.path.join(data_dir, 'downloads_history.json')
    
    print(f"\nHistory file: {history_file}")
    print(f"Downloads file: {downloads_file}")
    
    print(f"History file exists: {os.path.exists(history_file)}")
    print(f"Downloads file exists: {os.path.exists(downloads_file)}")
    
    # List history items if they exist
    if os.path.exists(history_dir):
        print(f"\nHistory items in {history_dir}:")
        try:
            items = os.listdir(history_dir)
            for item in items:
                item_path = os.path.join(history_dir, item)
                if os.path.isdir(item_path):
                    scenes_file = os.path.join(item_path, 'scenes.json')
                    print(f"  - {item}: scenes.json exists = {os.path.exists(scenes_file)}")
        except Exception as e:
            print(f"  Error listing history: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_paths()


