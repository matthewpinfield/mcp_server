#!/usr/bin/env python3
"""
Emergency Configuration Rollback Script
========================================

This script provides immediate rollback to safe baseline configuration
if the MVP optimizations cause agent flooding or performance issues.

Usage:
    python rollback_to_safe_config.py
    
Or set ENABLE_DYNAMIC_SCALING=False in config.py for immediate fallback.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

def rollback_to_safe_baseline():
    """Restore original configuration files"""
    
    project_root = Path(__file__).resolve().parent
    backup_dir = project_root / "archive" / "backups" / "original_configs"
    
    if not backup_dir.exists():
        print("❌ ERROR: Backup directory not found!")
        print(f"Expected: {backup_dir}")
        return False
    
    files_to_restore = [
        ("config_original.py", "config.py"),
        ("knowledge_original.py", "tools/knowledge.py"),
        ("web_original.py", "tools/web.py"),
        ("orchestrator_original.py", "core/orchestrator.py")
    ]
    
    print("🔄 Rolling back to safe baseline configuration...")
    
    success = True
    for backup_file, target_file in files_to_restore:
        backup_path = backup_dir / backup_file
        target_path = project_root / target_file
        
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, target_path)
                print(f"✅ Restored: {target_file}")
            except Exception as e:
                print(f"❌ Failed to restore {target_file}: {e}")
                success = False
        else:
            print(f"❌ Backup not found: {backup_file}")
            success = False
    
    return success

def restart_services():
    """Restart MCP services with safe configuration"""
    print("🔄 Restarting MCP services...")
    
    try:
        # Kill existing processes
        subprocess.run(["pkill", "-f", "python.*main.py"], check=False)
        subprocess.run(["pkill", "-f", "python.*dual_endpoint_server.py"], check=False)
        
        print("⏳ Waiting for processes to stop...")
        import time
        time.sleep(3)
        
        # Start services in background
        os.chdir(Path(__file__).resolve().parent)

        main_process = subprocess.Popen(
            ["python", "main.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        os.chdir("rag")
        rag_process = subprocess.Popen(
            ["python", "dual_endpoint_server.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        print(f"✅ Main server started (PID: {main_process.pid})")
        print(f"✅ RAG server started (PID: {rag_process.pid})")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to restart services: {e}")
        return False

def check_service_health():
    """Verify services are responding"""
    print("🔍 Checking service health...")
    
    try:
        import requests
        import time
        
        # Wait for services to initialize
        time.sleep(5)
        
        # Check main server
        main_response = requests.get("http://localhost:8013/health", timeout=10)
        if main_response.status_code == 200:
            print("✅ Main server: Healthy")
        else:
            print(f"⚠️  Main server: Status {main_response.status_code}")
        
        # Check RAG server
        rag_response = requests.get("http://localhost:8008/health", timeout=10)
        if rag_response.status_code == 200:
            print("✅ RAG server: Healthy")
        else:
            print(f"⚠️  RAG server: Status {rag_response.status_code}")
            
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def main():
    """Main rollback procedure"""
    print("=" * 50)
    print("🚨 EMERGENCY CONFIGURATION ROLLBACK")
    print("=" * 50)
    
    print("This will restore the safe baseline configuration.")
    print("All MVP optimizations will be disabled.")
    
    confirm = input("\nContinue? (y/N): ").lower().strip()
    if confirm != 'y':
        print("❌ Rollback cancelled")
        return
    
    # Step 1: Restore files
    if not rollback_to_safe_baseline():
        print("❌ File restoration failed!")
        return
    
    # Step 2: Restart services
    if not restart_services():
        print("❌ Service restart failed!")
        return
    
    # Step 3: Health check
    if not check_service_health():
        print("⚠️  Health check issues detected")
    
    print("\n" + "=" * 50)
    print("✅ ROLLBACK COMPLETE")
    print("=" * 50)
    print("Configuration restored to safe baseline:")
    print("• RAG results: 5")
    print("• Web search: 5 results")
    print("• Memory: 5 interactions")
    print("• Content length: 800 chars")
    print("\nServices should be stable now.")

if __name__ == "__main__":
    main()