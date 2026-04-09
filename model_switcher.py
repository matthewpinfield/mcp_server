#!/usr/bin/env python3
"""
Model Switcher Script
====================
Safely switches the DEFAULT_MODEL in config.py and restarts the server for testing.
"""

import os
import re
import subprocess
import time
import signal
import requests
from typing import Optional

CONFIG_FILE = "/mnt/caseSSD/mcp_server_project/config.py"
MAIN_SCRIPT = "/mnt/caseSSD/mcp_server_project/main.py"

AVAILABLE_MODELS = [
    "gemma4:26b",
    "qwen3:30b-a3b-thinking-2507-q4_K_M",
    "qwen3:30b-a3b-instruct-2507-q4_K_M", 
    "qwen3:14b",
    "qwen3:30b-a3b"  # Original model for reference
]

def get_current_model() -> str:
    """Get current model from config.py"""
    with open(CONFIG_FILE, 'r') as f:
        content = f.read()
    
    match = re.search(r'DEFAULT_MODEL = ["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    return "Unknown"

def set_model(model_name: str) -> bool:
    """Set model in config.py"""
    if model_name not in AVAILABLE_MODELS:
        print(f"❌ Model {model_name} not in available models: {AVAILABLE_MODELS}")
        return False
    
    # Read current config
    with open(CONFIG_FILE, 'r') as f:
        content = f.read()
    
    # Replace DEFAULT_MODEL line
    new_content = re.sub(
        r'DEFAULT_MODEL = ["\'][^"\']+["\']',
        f'DEFAULT_MODEL = "{model_name}"',
        content
    )
    
    # Write back to file
    with open(CONFIG_FILE, 'w') as f:
        f.write(new_content)
    
    print(f"✅ Updated config.py with model: {model_name}")
    return True

def find_server_pid() -> Optional[int]:
    """Find the PID of the running main.py server"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python3 main.py"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return int(pids[0])  # Return first PID if multiple
        return None
    except:
        return None

def stop_server() -> bool:
    """Stop the running server"""
    pid = find_server_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"🛑 Stopped server (PID: {pid})")
            time.sleep(3)  # Wait for graceful shutdown
            return True
        except:
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"🛑 Force stopped server (PID: {pid})")
                time.sleep(2)
                return True
            except:
                print(f"❌ Failed to stop server (PID: {pid})")
                return False
    else:
        print("ℹ️  No server running")
        return True

def start_server() -> bool:
    """Start the server"""
    try:
        # Change to project directory
        os.chdir("/mnt/caseSSD/mcp_server_project")
        
        # Start server in background
        process = subprocess.Popen(
            ["python3", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        
        print(f"🚀 Starting server (PID: {process.pid})")
        
        # Wait for server to be ready
        for i in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            try:
                response = requests.get("http://localhost:8013/health", timeout=2)
                if response.status_code == 200:
                    print("✅ Server is ready!")
                    return True
            except:
                continue
        
        print("❌ Server failed to start within 30 seconds")
        return False
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False

def wait_for_server_ready(max_wait: int = 30) -> bool:
    """Wait for server to be ready"""
    print("⏳ Waiting for server to be ready...")
    for i in range(max_wait):
        try:
            response = requests.get("http://localhost:8013/health", timeout=2)
            if response.status_code == 200:
                print("✅ Server is ready!")
                return True
        except:
            pass
        time.sleep(1)
        if i % 5 == 0:
            print(f"   Still waiting... ({i+1}s)")
    
    print("❌ Server not ready after {max_wait}s")
    return False

def switch_model(model_name: str) -> bool:
    """Switch to a different model and restart server"""
    current_model = get_current_model()
    print(f"🔄 Switching from {current_model} to {model_name}")
    
    # Update config
    if not set_model(model_name):
        return False
    
    # Stop current server
    if not stop_server():
        print("⚠️  Warning: Failed to stop server cleanly")
    
    # Start server with new model
    if not start_server():
        print("❌ Failed to start server with new model")
        # Try to restore previous model
        print("🔄 Attempting to restore previous model...")
        set_model(current_model)
        start_server()
        return False
    
    return True

def show_status():
    """Show current status"""
    current_model = get_current_model()
    server_pid = find_server_pid()
    
    print("\n📊 CURRENT STATUS")
    print("-" * 40)
    print(f"Current Model: {current_model}")
    print(f"Server Status: {'Running (PID: {})'.format(server_pid) if server_pid else 'Not Running'}")
    
    if server_pid:
        try:
            response = requests.get("http://localhost:8013/health", timeout=2)
            health = "Healthy" if response.status_code == 200 else f"Unhealthy ({response.status_code})"
        except:
            health = "Unreachable"
        print(f"Health Check: {health}")
    
    print(f"Available Models: {', '.join(AVAILABLE_MODELS)}")
    print("-" * 40)

def main():
    """Main interactive menu"""
    while True:
        show_status()
        print("\n🎛️  MODEL SWITCHER MENU")
        print("1. Switch to gemma4:26b")
        print("2. Switch to qwen3:30b-a3b-thinking-2507-q4_K_M")
        print("3. Switch to qwen3:30b-a3b-instruct-2507-q4_K_M")  
        print("4. Switch to qwen3:14b")
        print("5. Switch to qwen3:30b-a3b (original)")
        print("6. Restart server (same model)")
        print("7. Stop server")
        print("8. Start server")
        print("9. Run model comparison test")
        print("0. Exit")
        
        choice = input("\nSelect option (0-9): ").strip()
        
        if choice == "0":
            print("👋 Goodbye!")
            break
        elif choice == "1":
            switch_model("gemma4:26b")
        elif choice == "2":
            switch_model("qwen3:30b-a3b-thinking-2507-q4_K_M")
        elif choice == "3":
            switch_model("qwen3:30b-a3b-instruct-2507-q4_K_M")
        elif choice == "4":
            switch_model("qwen3:14b")
        elif choice == "5":
            switch_model("qwen3:30b-a3b")
        elif choice == "6":
            current_model = get_current_model()
            print(f"🔄 Restarting server with {current_model}")
            stop_server()
            start_server()
        elif choice == "7":
            stop_server()
        elif choice == "8":
            start_server()
        elif choice == "9":
            print("🧪 Running model comparison test...")
            os.system("python3 model_comparison_test.py")
        else:
            print("❌ Invalid choice")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    print("🔧 Model Switcher for MCP Server")
    print("================================")
    main()