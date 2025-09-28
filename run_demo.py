#!/usr/bin/env python3
"""
InboxPay Demo Runner
Starts the demo server and processor
"""
import subprocess
import time
import requests
import sys
import os
import signal
import threading

def check_server_running(port=8000):
    """Check if server is running"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def start_server():
    """Start the demo server"""
    print("🚀 Starting InboxPay Demo Server...")
    
    process = subprocess.Popen([
        sys.executable, 'demo_app.py'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    for i in range(15):
        if check_server_running(8000):
            print("✅ Demo server started on http://localhost:8000")
            return process
        time.sleep(1)
    
    print("❌ Server failed to start")
    return None

def start_processor():
    """Start the demo processor"""
    print("🤖 Starting bill processor...")
    
    process = subprocess.Popen([
        sys.executable, 'demo_processor.py'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    return process

def main():
    """Main demo runner"""
    print("🎉 InboxPay Demo - Autonomous Bill Processing")
    print("=" * 70)
    print("This demo shows how AgentMail can process bills automatically")
    print("=" * 70)
    
    server_process = None
    processor_process = None
    
    try:
        # Start server
        if check_server_running(8000):
            print("✅ Demo server already running")
        else:
            server_process = start_server()
            if not server_process:
                return
        
        # Start processor
        processor_process = start_processor()
        time.sleep(2)
        
        print(f"\n🎯 DEMO IS READY!")
        print(f"=" * 50)
        print(f"📊 Dashboard: http://localhost:8000")
        print(f"📧 Agent Inbox: bills@...agentmail.to")
        print(f"🤖 Processor: Running (checking every 10s)")
        print(f"=" * 50)
        print(f"\n💡 HOW TO TEST:")
        print(f"1. Open http://localhost:8000 in your browser")
        print(f"2. Click 'Send Test Bill' to see it work")
        print(f"3. Or send real bills to the agent inbox")
        print(f"\n🛑 Press Ctrl+C to stop everything")
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n🛑 Stopping InboxPay Demo...")
        
        if processor_process:
            print("🔄 Stopping processor...")
            processor_process.terminate()
            processor_process.wait()
        
        if server_process:
            print("🔄 Stopping server...")
            server_process.terminate()
            server_process.wait()
        
        print("✅ Demo stopped successfully")
        print("👋 Thanks for trying InboxPay!")

if __name__ == "__main__":
    main()
