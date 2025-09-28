#!/usr/bin/env python3
"""
Simple test script for AgentMail integration
"""
from agentmail import AgentMail
import os
from dotenv import load_dotenv

def test_agentmail():
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("AGENTMAIL_API_KEY")
    demo_inbox_id = os.getenv("DEMO_INBOX_ID")
    
    if not api_key:
        print("❌ AGENTMAIL_API_KEY not found in .env file")
        return False
    
    if not demo_inbox_id:
        print("❌ DEMO_INBOX_ID not found in .env file")
        return False
    
    print(f"✅ Found API key: {api_key[:8]}...")
    print(f"✅ Found inbox ID: {demo_inbox_id}")
    
    try:
        # Initialize client
        client = AgentMail(api_key=api_key)
        print("✅ AgentMail client initialized")
        
        # Test getting inbox
        print(f"\n📬 Testing inbox retrieval...")
        inbox = client.inboxes.get(inbox_id=demo_inbox_id)
        print(f"✅ Inbox retrieved: {inbox}")
        print(f"   Inbox ID: {getattr(inbox, 'id', 'N/A')}")
        print(f"   Inbox details: {vars(inbox) if hasattr(inbox, '__dict__') else 'No details available'}")
        
        # Test getting messages
        print(f"\n📧 Testing message listing...")
        messages = client.inboxes.messages.list(inbox_id=demo_inbox_id)
        print(f"✅ Found {messages.count} messages")
        
        # Show first few messages
        if messages.count > 0:
            print("\n📋 Recent messages:")
            for i, msg in enumerate(messages.messages[:3]):
                print(f"  {i+1}. From: {msg.from_} | Subject: {msg.subject}")
        
        print("\n🎉 AgentMail integration test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ AgentMail test FAILED: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 Testing AgentMail Integration...")
    print("=" * 50)
    success = test_agentmail()
    exit(0 if success else 1)
