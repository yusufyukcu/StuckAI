#!/usr/bin/env python3
"""
Video Scene AI - Login System Setup Script
Bu script Supabase kimlik doğrulama sistemini kurmanıza yardımcı olur.
"""

import os
import sys
from pathlib import Path

def create_env_file():
    """Create .env file with user input"""
    print("🎬 Video Scene AI - Login System Setup")
    print("=" * 50)
    
    # Check if .env already exists
    env_path = Path(".env")
    if env_path.exists():
        print("⚠️  .env file already exists!")
        response = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if response != 'y':
            print("Setup cancelled.")
            return False
    
    print("\n📋 Enter your Supabase information:")
    print("You can find this information in Supabase Dashboard > Settings > API section.\n")
    
    # Get Supabase URL
    while True:
        supabase_url = input("Supabase Project URL: ").strip()
        if supabase_url.startswith("https://") and "supabase.co" in supabase_url:
            break
        print("❌ Invalid URL. Example: https://your-project-id.supabase.co")
    
    # Get Supabase Anon Key
    while True:
        supabase_key = input("Supabase Anon Key: ").strip()
        if len(supabase_key) > 20:  # Basic validation
            break
        print("❌ Invalid key. Please enter the correct anon key.")
    
    # Get OpenAI API Key (optional)
    openai_key = input("OpenAI API Key (optional): ").strip()
    
    # Create .env file
    env_content = f"""# Supabase Configuration
SUPABASE_URL={supabase_url}
SUPABASE_ANON_KEY={supabase_key}

# OpenAI API Key (Eğer OpenAI kullanıyorsanız)
"""
    
    if openai_key:
        env_content += f"OPENAI_API_KEY={openai_key}\n"
    else:
        env_content += "# OPENAI_API_KEY=your-openai-api-key-here\n"
    
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(env_content)
        
        print(f"\n✅ .env file created successfully: {env_path.absolute()}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    
    try:
        import subprocess
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Dependencies installed successfully!")
            return True
        else:
            print(f"❌ Dependency installation error:\n{result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Dependency installation error: {e}")
        return False

def check_supabase_connection():
    """Test Supabase connection"""
    print("\n🔗 Testing Supabase connection...")
    
    try:
        from logic.supabase_auth import SupabaseAuthService
        auth_service = SupabaseAuthService()
        
        # Try to get current user (should work even if no user is logged in)
        current_user = auth_service.get_current_user()
        print("✅ Supabase connection successful!")
        return True
        
    except Exception as e:
        print(f"❌ Supabase connection error: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure the information in .env file is correct")
        print("2. Check that your Supabase project is active")
        print("3. Make sure you've run the supabase_setup.sql script")
        return False

def main():
    """Main setup function"""
    print("🎬 Video Scene AI - Login System Setup")
    print("=" * 50)
    
    # Step 1: Create .env file
    if not create_env_file():
        return
    
    # Step 2: Install dependencies
    if not install_dependencies():
        print("\n⚠️  Dependency installation failed. Try installing manually:")
        print("pip install -r requirements.txt")
        return
    
    # Step 3: Test connection
    if not check_supabase_connection():
        print("\n⚠️  Connection test failed. Please check your settings.")
        return
    
    print("\n🎉 Setup completed!")
    print("\n📋 Next steps:")
    print("1. Open SQL Editor in Supabase Dashboard")
    print("2. Copy the content of supabase_setup.sql file")
    print("3. Run it in SQL Editor")
    print("4. Start the application: python app.py")
    
    print("\n🚀 To start the application:")
    print("python app.py")

if __name__ == "__main__":
    main() 