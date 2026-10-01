#!/usr/bin/env python3
"""
Script to migrate user data from Program Files to AppData
Run this once to fix existing installations
"""
import os
import shutil
import sys

def migrate_user_data():
    """Migrate data from Program Files to AppData"""
    program_files_data = r"C:\Program Files\StuckAI\data"
    program_files_history = r"C:\Program Files\StuckAI\history"
    
    user_data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "StuckAI")
    user_data_data = os.path.join(user_data_dir, "data")
    user_data_history = os.path.join(user_data_dir, "history")
    
    print("=" * 60)
    print("USER DATA MIGRATION SCRIPT")
    print("=" * 60)
    
    # Create user data directories
    os.makedirs(user_data_data, exist_ok=True)
    os.makedirs(user_data_history, exist_ok=True)
    
    migrated_files = 0
    migrated_folders = 0
    
    # Migrate data directory
    if os.path.exists(program_files_data):
        print(f"Migrating data from: {program_files_data}")
        print(f"Migrating data to: {user_data_data}")
        
        try:
            for item in os.listdir(program_files_data):
                src = os.path.join(program_files_data, item)
                dst = os.path.join(user_data_data, item)
                
                if os.path.isfile(src):
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        print(f"  ✅ Migrated file: {item}")
                        migrated_files += 1
                    else:
                        print(f"  ⚠️ File already exists: {item}")
                elif os.path.isdir(src):
                    if not os.path.exists(dst):
                        shutil.copytree(src, dst)
                        print(f"  ✅ Migrated folder: {item}")
                        migrated_folders += 1
                    else:
                        print(f"  ⚠️ Folder already exists: {item}")
        except Exception as e:
            print(f"  ❌ Error migrating data: {e}")
    else:
        print("No data directory found in Program Files")
    
    # Migrate history directory
    if os.path.exists(program_files_history):
        print(f"\nMigrating history from: {program_files_history}")
        print(f"Migrating history to: {user_data_history}")
        
        try:
            for item in os.listdir(program_files_history):
                src = os.path.join(program_files_history, item)
                dst = os.path.join(user_data_history, item)
                
                if os.path.isdir(src):
                    if not os.path.exists(dst):
                        shutil.copytree(src, dst)
                        print(f"  ✅ Migrated history folder: {item}")
                        migrated_folders += 1
                    else:
                        print(f"  ⚠️ History folder already exists: {item}")
        except Exception as e:
            print(f"  ❌ Error migrating history: {e}")
    else:
        print("No history directory found in Program Files")
    
    print("\n" + "=" * 60)
    print(f"MIGRATION COMPLETED")
    print(f"Files migrated: {migrated_files}")
    print(f"Folders migrated: {migrated_folders}")
    print("=" * 60)
    
    # Verify migration
    print(f"\nVerifying migration...")
    print(f"User data directory: {user_data_dir}")
    print(f"Data exists: {os.path.exists(user_data_data)}")
    print(f"History exists: {os.path.exists(user_data_history)}")
    
    if os.path.exists(user_data_data):
        data_files = len([f for f in os.listdir(user_data_data) if os.path.isfile(os.path.join(user_data_data, f))])
        print(f"Data files: {data_files}")
    
    if os.path.exists(user_data_history):
        history_folders = len([f for f in os.listdir(user_data_history) if os.path.isdir(os.path.join(user_data_history, f))])
        print(f"History folders: {history_folders}")
    
    # Show next steps
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("1. Recompile the program with: pyinstaller StuckAI.spec")
    print("2. Create new installer")
    print("3. Uninstall old version and install new version")
    print("4. The program will now use AppData for all data")
    print("=" * 60)

if __name__ == "__main__":
    migrate_user_data()
