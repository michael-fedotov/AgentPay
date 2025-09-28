#!/usr/bin/env python3
"""
Setup script for AgentPay webhook automation
This script will help you configure ngrok and AgentMail webhooks
"""
import subprocess
import time
import requests
import json
import os
from dotenv import load_dotenv

def check_server_running(port=8000):
    """Check if the AgentPay server is running"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def start_ngrok_tunnel(port=8000):
    """Start ngrok tunnel and return the public URL"""
    print(f"🚀 Starting ngrok tunnel for port {port}...")
    
    # Start ngrok in the background
    process = subprocess.Popen(
        ['ngrok', 'http', str(port), '--log=stdout'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for ngrok to start
    print("⏳ Waiting for ngrok to initialize...")
    time.sleep(3)
    
    # Get the public URL from ngrok API
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        if response.status_code == 200:
            tunnels = response.json()
            if tunnels.get('tunnels'):
                public_url = tunnels['tunnels'][0]['public_url']
                print(f"✅ ngrok tunnel active: {public_url}")
                return public_url, process
        
        print("❌ Could not get ngrok tunnel URL")
        return None, process
    except Exception as e:
        print(f"❌ Error getting ngrok URL: {e}")
        return None, process

def configure_agentmail_webhook(webhook_url):
    """Instructions for configuring AgentMail webhook"""
    print(f"\n📋 AgentMail Webhook Configuration")
    print("=" * 50)
    print(f"1. Go to your AgentMail dashboard")
    print(f"2. Navigate to Inbox Settings")
    print(f"3. Find the Webhooks section")
    print(f"4. Add a new webhook with these settings:")
    print(f"   📍 URL: {webhook_url}/webhook/agentmail")
    print(f"   🔧 Method: POST")
    print(f"   📧 Events: message.received")
    print(f"   🔐 Secret: (optional, but recommended)")
    print(f"\n✅ Once configured, emails will be processed automatically!")

def test_webhook_endpoint(webhook_url):
    """Test the webhook endpoint"""
    print(f"\n🧪 Testing webhook endpoint...")
    
    test_payload = {
        "type": "message.received",
        "data": {
            "inbox_id": "happymirror836@agentmail.to",
            "message_id": "test-webhook-setup",
            "from": "test@example.com",
            "subject": "Webhook Test",
            "timestamp": "2025-09-28T05:30:00Z"
        }
    }
    
    try:
        response = requests.post(
            f"{webhook_url}/webhook/agentmail",
            json=test_payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Webhook endpoint is working!")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ Webhook test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Webhook test error: {e}")
        return False

def show_monitoring_info(webhook_url):
    """Show information for monitoring the system"""
    print(f"\n📊 Monitoring Your AgentPay System")
    print("=" * 50)
    print(f"🌐 Public webhook URL: {webhook_url}/webhook/agentmail")
    print(f"💚 Health check: {webhook_url}/health")
    print(f"📧 AgentMail test: {webhook_url}/test/agentmail")
    print(f"🏠 Dashboard: {webhook_url}/")
    print(f"\n📱 Send emails to: happymirror836@agentmail.to")
    print(f"📬 Confirmations sent to: m_fedotov@hotmail.com")

def main():
    """Main setup function"""
    print("🚀 AgentPay Webhook Automation Setup")
    print("=" * 60)
    
    # Load environment
    load_dotenv()
    
    # Check if server is running
    port = 8000
    if not check_server_running(port):
        print(f"❌ AgentPay server is not running on port {port}")
        print(f"💡 Please start the server first:")
        print(f"   uvicorn app:app --reload --port {port}")
        return
    
    print(f"✅ AgentPay server is running on port {port}")
    
    # Start ngrok tunnel
    public_url, ngrok_process = start_ngrok_tunnel(port)
    
    if not public_url:
        print("❌ Failed to start ngrok tunnel")
        return
    
    # Test the webhook endpoint
    webhook_working = test_webhook_endpoint(public_url)
    
    if not webhook_working:
        print("❌ Webhook endpoint is not responding correctly")
        return
    
    # Show configuration instructions
    configure_agentmail_webhook(public_url)
    
    # Show monitoring information
    show_monitoring_info(public_url)
    
    # Keep the script running
    print(f"\n🔄 System Status")
    print("=" * 30)
    print(f"✅ AgentPay server: Running on port {port}")
    print(f"✅ ngrok tunnel: {public_url}")
    print(f"✅ Webhook endpoint: Ready")
    print(f"\n💡 Keep this script running to maintain the tunnel")
    print(f"🛑 Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(30)
            # Check if server is still running
            if not check_server_running(port):
                print("❌ AgentPay server stopped!")
                break
            print(f"💚 System healthy - {time.strftime('%H:%M:%S')}")
    except KeyboardInterrupt:
        print(f"\n🛑 Shutting down...")
        if ngrok_process:
            ngrok_process.terminate()
        print(f"✅ Cleanup complete")

if __name__ == "__main__":
    main()
