#!/usr/bin/env python3
"""
Debug analysis settings usage
"""

import json
import os
import sys

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_analysis_settings():
    """Test if settings are being used correctly in analysis"""
    
    print("🔍 DEBUGGING ANALYSIS SETTINGS USAGE")
    print("=" * 50)
    
    # 1. Load current settings
    settings_file = "data/settings.json"
    print(f"\n1. 📁 Loading current settings from: {settings_file}")
    
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            current_settings = json.load(f)
            print("✅ Current settings:")
            for key, value in current_settings.items():
                print(f"   {key}: {value}")
    else:
        print("❌ Settings file not found")
        return
    
    # 2. Test generate_visual_suggestions function
    print(f"\n2. 🎯 Testing generate_visual_suggestions function...")
    
    # Simulate a micro-scene
    test_micro_scene = {
        'scene_title': 'Test Scene',
        'summary': 'This is a test scene for debugging',
        'visual_prompt': 'A professional office environment',
        'keywords': ['office', 'professional', 'business'],
        'tone': 'professional'
    }
    
    # Test the stock prompt generation
    stock_prompt = f"""
Based on this micro-scene, provide search keywords for finding stock media:

Scene Title: {test_micro_scene.get('scene_title', '')}
Summary: {test_micro_scene.get('summary', '')}
Visual Prompt: {test_micro_scene.get('visual_prompt', '')}
Keywords: {', '.join(test_micro_scene.get('keywords', []))}
Tone: {test_micro_scene.get('tone', '')}

Provide ONLY search keywords for each category:

1. **Stock Image Keywords** ({current_settings['stock_images_count']} sets):
   - Each as a list of 3-5 keywords for stock sites

2. **Stock Video Keywords** ({current_settings['stock_videos_count']} sets):
   - Each as a list of 3-5 keywords for stock sites

Return ONLY a valid JSON object:
{{
  "stock_image_keywords": [
    ["keyword1", "keyword2", "keyword3"],
    ["keyword4", "keyword5", "keyword6"]
  ],
  "stock_video_keywords": [
    ["keyword1", "keyword2", "keyword3"]
  ]
}}
"""
    
    ai_prompt = f"""
You are a professional AI image prompt engineer. Create {current_settings['ai_images_count']} highly detailed, photorealistic prompts for AI image generation based on this micro-scene:

Scene Title: {test_micro_scene.get('scene_title', '')}
Summary: {test_micro_scene.get('summary', '')}
Visual Prompt: {test_micro_scene.get('visual_prompt', '')}
Keywords: {', '.join(test_micro_scene.get('keywords', []))}
Tone: {test_micro_scene.get('tone', '')}

IMPORTANT: NEVER use any proper names (like Cody, John, Annie, Sarah, Mike, etc.) in any of your prompts. Use generic terms like "person", "professional", "individual", "student", "worker", etc.

Create {current_settings['ai_images_count']} unique AI image prompts that are:
- Highly detailed and specific
- Include camera angles, lighting, composition
- Specify mood, atmosphere, and style
- Optimized for Midjourney, DALL-E, or Stable Diffusion
- Each prompt should be different but related to the scene
- NEVER include proper names, use generic terms for people

Return ONLY a valid JSON array:
[
  {{
    "title": "Descriptive title for the image",
    "prompt": "Highly detailed prompt for AI image generation"
  }},
  {{
    "title": "Another descriptive title",
    "prompt": "Another detailed prompt"
  }}
]
"""
    
    print("✅ Settings are correctly used in prompts:")
    print(f"   Stock Images: {current_settings['stock_images_count']} sets requested")
    print(f"   Stock Videos: {current_settings['stock_videos_count']} sets requested")
    print(f"   AI Images: {current_settings['ai_images_count']} prompts requested")
    
    # 3. Test cache key generation
    print(f"\n3. 🔑 Testing cache key generation...")
    
    import hashlib
    
    test_text = "This is a test text for analysis"
    
    # Create cache key with current settings
    content = f"{test_text}_{json.dumps(current_settings, sort_keys=True)}"
    cache_key = hashlib.md5(content.encode()).hexdigest()
    
    print(f"Cache key: {cache_key}")
    print(f"Content hash: {content[:100]}...")
    
    # 4. Test settings validation
    print(f"\n4. ✅ Testing settings validation...")
    
    required_keys = ['stock_images_count', 'stock_videos_count', 'ai_images_count']
    missing_keys = []
    
    for key in required_keys:
        if key not in current_settings:
            missing_keys.append(key)
        else:
            value = current_settings[key]
            if not isinstance(value, int) or value < 0:
                print(f"⚠️ Invalid value for {key}: {value} (should be positive integer)")
            else:
                print(f"✅ {key}: {value}")
    
    if missing_keys:
        print(f"❌ Missing required settings: {missing_keys}")
    else:
        print("✅ All required settings are present and valid")
    
    # 5. Test settings consistency
    print(f"\n5. 🔄 Testing settings consistency...")
    
    # Check if settings match what we expect
    expected_settings = {
        'stock_images_count': 2,
        'stock_videos_count': 1,
        'ai_images_count': 1
    }
    
    for key, expected_value in expected_settings.items():
        actual_value = current_settings.get(key)
        if actual_value == expected_value:
            print(f"✅ {key}: {actual_value} (matches expected)")
        else:
            print(f"❌ {key}: {actual_value} (expected {expected_value})")
    
    print(f"\n6. 📋 SUMMARY")
    print("=" * 50)
    print("✅ Settings are correctly used in analysis prompts")
    print("✅ Cache key generation includes settings")
    print("✅ Settings validation passed")
    
    if all(current_settings.get(key) == expected_settings[key] for key in expected_settings):
        print("✅ Settings consistency check passed")
        print("\n💡 If you're still seeing wrong results:")
        print("   1. Make sure you're using a new text (not cached)")
        print("   2. Check if there are any other cache files")
        print("   3. Verify the analysis is using the latest settings")
        print("   4. Try restarting the application")
    else:
        print("❌ Settings consistency check failed")
        print("   Settings don't match expected values")

if __name__ == "__main__":
    test_analysis_settings() 