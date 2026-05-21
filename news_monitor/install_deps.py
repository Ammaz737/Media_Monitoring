#!/usr/bin/env python3
"""
Installation script for News Monitor dependencies
Handles Python 3.12 compatibility issues
"""

import subprocess
import sys
import logging

def run_command(cmd):
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Success: {cmd}")
            return True
        else:
            print(f"✗ Failed: {cmd}")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Exception running {cmd}: {e}")
        return False

def main():
    print("🚀 Installing News Monitor Dependencies...")
    print("=" * 50)
    
    # Core dependencies that should work
    core_deps = [
        "torch==1.13.1",
        "torchvision==0.14.1", 
        "torchaudio==0.13.1",
        "numpy==1.24.0",
        "opencv-python==4.8.0.74",
        "pillow==10.0.0",
        "requests==2.31.0",
        "python-dateutil==2.8.2",
        "scikit-image==0.21.0",
        "matplotlib==3.7.0"
    ]
    
    # Web framework with Python 3.12 compatibility
    web_deps = [
        "flask==2.3.0",
        "werkzeug==2.3.0"
    ]
    
    # Optional dependencies
    optional_deps = [
        "openai-whisper",
        "transformers==4.30.0",
        "arabic-reshaper==3.0.0",
        "python-bidi==0.4.2"
    ]
    
    print("📦 Installing core dependencies...")
    for dep in core_deps:
        run_command(f"pip install {dep}")
    
    print("\n🌐 Installing web framework...")
    for dep in web_deps:
        run_command(f"pip install {dep}")
    
    print("\n🔍 Trying to install SocketIO (may fail on Python 3.12)...")
    socketio_success = False
    
    # Try different SocketIO versions
    socketio_versions = [
        "flask-socketio==5.3.6 python-socketio==5.10.0",
        "flask-socketio==5.1.0 python-socketio==5.3.0",
        "flask-socketio"
    ]
    
    for version in socketio_versions:
        print(f"Trying: {version}")
        if run_command(f"pip install {version}"):
            socketio_success = True
            break
    
    if not socketio_success:
        print("⚠️ SocketIO installation failed. Real-time updates will be disabled.")
        print("The system will still work without real-time web updates.")
    
    print("\n🎵 Installing optional audio dependencies...")
    for dep in optional_deps:
        run_command(f"pip install {dep}")
    
    print("\n✅ Installation complete!")
    print("\nTo test the installation, run:")
    print("python main.py --mode test")

if __name__ == "__main__":
    main()