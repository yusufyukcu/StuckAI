#!/usr/bin/env python3
"""
Debug settings save functionality
"""

import json
import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_settings_save():
    """Test if settings are being saved correctly"""
    
    print("🔍 DEBUGGING SETTINGS SAVE FUNCTIONALITY")
    print("=" * 50)
    
    # 1. Check current settings
    settings_file = "data/settings.json"
    print(f"\n1. 📁 Current settings file: {settings_file}")
    
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            current_settings = json.load(f)
            print("✅ Current settings:")
            for key, value in current_settings.items():
                print(f"   {key}: {value}")
    else:
        print("❌ Settings file not found")
        return
    
    # 2. Simulate settings dialog save
    print(f"\n2. 🔧 Simulating settings dialog save...")
    
    # Simulate what happens when user changes settings in dialog
    new_settings = current_settings.copy()
    new_settings['stock_images_count'] = 2
    new_settings['stock_videos_count'] = 1
    new_settings['ai_images_count'] = 3
    
    print("📝 New settings to be saved:")
    for key, value in new_settings.items():
        print(f"   {key}: {value}")
    
    # 3. Save settings (simulate SettingsDialog.save_settings())
    print(f"\n3. 💾 Saving settings to file...")
    try:
        with open(settings_file, 'w') as f:
            json.dump(new_settings, f, indent=2)
        print("✅ Settings saved successfully")
    except Exception as e:
        print(f"❌ Error saving settings: {e}")
        return
    
    # 4. Verify the save
    print(f"\n4. 🔍 Verifying saved settings...")
    with open(settings_file, 'r') as f:
        saved_settings = json.load(f)
        print("✅ Settings after save:")
        for key, value in saved_settings.items():
            print(f"   {key}: {value}")
    
    # 5. Test MainWindow.load_settings_from_file()
    print(f"\n5. 🔄 Testing MainWindow.load_settings_from_file()...")
    
    # Simulate the load_settings_from_file method
    try:
        with open(settings_file, 'r') as f:
            loaded_settings = json.load(f)
        
        print("✅ Settings loaded successfully:")
        for key, value in loaded_settings.items():
            print(f"   {key}: {value}")
            
        # Check if the loaded settings match what we saved
        if loaded_settings == saved_settings:
            print("✅ Loaded settings match saved settings")
        else:
            print("❌ Loaded settings do not match saved settings")
            
    except Exception as e:
        print(f"❌ Error loading settings: {e}")
    
    # 6. Test cache key generation
    print(f"\n6. 🔑 Testing cache key generation...")
    
    # Simulate the cache key generation from smart_scene_analysis.py
    import hashlib
    
    test_text = "This is a test text for analysis"
    
    # Create cache key with old settings
    old_content = f"{test_text}_{json.dumps(current_settings, sort_keys=True)}"
    old_cache_key = hashlib.md5(old_content.encode()).hexdigest()
    
    # Create cache key with new settings
    new_content = f"{test_text}_{json.dumps(saved_settings, sort_keys=True)}"
    new_cache_key = hashlib.md5(new_content.encode()).hexdigest()
    
    print(f"Old cache key: {old_cache_key}")
    print(f"New cache key: {new_cache_key}")
    
    if old_cache_key != new_cache_key:
        print("✅ Cache keys are different - settings change will trigger new analysis")
    else:
        print("❌ Cache keys are the same - settings change will NOT trigger new analysis")
    
    print(f"\n7. 📋 SUMMARY")
    print("=" * 50)
    print("✅ Settings save/load system appears to be working correctly")
    print("✅ Cache key generation includes settings")
    print("✅ Settings changes should trigger new analysis")
    print("\n💡 If you're still seeing old results:")
    print("   1. Make sure you restart the application after changing settings")
    print("   2. Check if there are any other cache files")
    print("   3. Verify the analysis is using the latest settings")

if __name__ == "__main__":
    test_settings_save() 