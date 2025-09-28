#!/usr/bin/env python3
"""
AgentPay Startup Script
This script starts the server and automatic email processor
"""
import subprocess
import time
import requests
import sys
import os
import signal

def check_server_running(port=8000):
    """Check if server is running"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def start_server(port=8000):
    """Start the FastAPI server"""
    print(f"🚀 Starting AgentPay server on port {port}...")
    
    # Start server in background
    process = subprocess.Popen([
        'uvicorn', 'app:app', '--reload', '--port', str(port)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    for i in range(10):
        if check_server_running(port):
            print(f"✅ Server started successfully on port {port}")
            return process
        time.sleep(1)
    
    print(f"❌ Server failed to start")
    return None

def main():
    """Main startup function"""
    print("🎉 AgentPay Automatic Bill Processing System")
    print("=" * 70)
    print("This will start the server and automatic email processor")
    print("=" * 70)
    
    server_process = None
    
    try:
        # Check if server is already running
        if check_server_running(8000):
            print("✅ AgentPay server is already running on port 8000")
        else:
            # Try to start server
            server_process = start_server(8000)
            if not server_process:
                print("❌ Could not start server. Please start manually:")
                print("   uvicorn app:app --reload --port 8000")
                return
        
        print(f"\n🔄 Starting automatic email processor...")
        print(f"📧 Will monitor: happymirror836@agentmail.to")
        print(f"📬 Confirmations to: m_fedotov@hotmail.com")
        print(f"⏰ Checking every 30 seconds for new bills")
        print(f"\n💡 Send any bill to happymirror836@agentmail.to and it will be processed automatically!")
        print(f"🛑 Press Ctrl+C to stop\n")
        
        # Start the automatic processor
        os.system("python auto_processor.py")
        
    except KeyboardInterrupt:
        print(f"\n🛑 Shutting down AgentPay...")
        
        if server_process:
            print(f"🔄 Stopping server...")
            server_process.terminate()
            server_process.wait()
        
        print(f"✅ AgentPay stopped successfully")
        print(f"👋 Goodbye!")

if __name__ == "__main__":
    main()
