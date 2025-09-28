#!/usr/bin/env python3
"""
InboxPay Demo Processor
Polls AgentMail inbox and processes new bills automatically
No webhooks or ngrok needed - perfect for demos!
"""
import asyncio
import json
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Set
import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from demo_app import settings, agentmail_client

class DemoProcessor:
    def __init__(self):
        self.processed_message_ids: Set[str] = set()
        self.check_interval = 10  # Check every 10 seconds for demo
        
    def load_processed_messages(self):
        """Load previously processed message IDs"""
        try:
            if os.path.exists('demo_processed.json'):
                with open('demo_processed.json', 'r') as f:
                    data = json.load(f)
                    self.processed_message_ids = set(data.get('processed_ids', []))
                    print(f"📋 Loaded {len(self.processed_message_ids)} previously processed messages")
        except Exception as e:
            print(f"⚠️ Could not load processed messages: {e}")
    
    def save_processed_messages(self):
        """Save processed message IDs"""
        try:
            with open('demo_processed.json', 'w') as f:
                json.dump({
                    'processed_ids': list(self.processed_message_ids),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save processed messages: {e}")
    
    def is_bill_like(self, message) -> bool:
        """Determine if message looks like a bill"""
        subject = getattr(message, 'subject', '').lower()
        from_email = getattr(message, 'from_', '').lower()
        
        # Skip our own messages
        if 'agentmail.to' in from_email:
            return False
        
        # Look for bill keywords
        bill_keywords = [
            'bill', 'invoice', 'statement', 'payment', 'due', 'amount',
            'electric', 'gas', 'water', 'phone', 'internet', 'credit card',
            'utility', 'wireless', 'cable', 'insurance', 'comed', 'chase'
        ]
        
        return any(keyword in subject for keyword in bill_keywords)
    
    def process_message_via_webhook(self, message) -> bool:
        """Process message by calling our webhook endpoint"""
        webhook_payload = {
            "type": "message.received",
            "data": {
                "id": message.message_id,
                "inbox_id": message.inbox_id,
                "thread_id": getattr(message, 'thread_id', None),
                "from": [getattr(message, 'from_', 'unknown@example.com')],
                "subject": getattr(message, 'subject', 'No Subject'),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        try:
            response = requests.post(
                "http://localhost:8000/api/agentmail/webhook",
                json=webhook_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'processed':
                    print(f"   ✅ Bill processed successfully!")
                    parsed = result.get('parsed_data', {})
                    print(f"      💰 Amount: ${parsed.get('amount_cents', 0)/100:.2f}")
                    print(f"      🏢 Payee: {parsed.get('payee', 'Unknown')}")
                    print(f"      🤖 Action: {result.get('agent_action', 'Unknown')}")
                    return True
                elif result.get('status') == 'duplicate':
                    print(f"   ⚠️ Already processed")
                    return True
                else:
                    print(f"   ❌ Processing failed: {result}")
                    return False
            else:
                print(f"   ❌ Webhook failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error processing: {e}")
            return False
    
    def check_for_new_messages(self):
        """Check for new messages and process them"""
        try:
            # Get messages from inbox
            messages = agentmail_client.inboxes.messages.list(
                inbox_id=settings.demo_inbox_id,
                limit=10
            )
            
            new_messages = []
            
            # Find new bill-like messages
            for message in messages:
                if (message.message_id not in self.processed_message_ids and 
                    self.is_bill_like(message)):
                    new_messages.append(message)
            
            if new_messages:
                print(f"\n📧 Found {len(new_messages)} new bill-like messages")
                
                for i, message in enumerate(new_messages, 1):
                    print(f"\n📋 Processing {i}/{len(new_messages)}:")
                    print(f"   📧 Subject: {getattr(message, 'subject', 'No Subject')}")
                    print(f"   👤 From: {getattr(message, 'from_', 'Unknown')}")
                    
                    success = self.process_message_via_webhook(message)
                    
                    # Mark as processed
                    self.processed_message_ids.add(message.message_id)
                    
                    if success:
                        print(f"   🎉 Agent replied and user notified!")
                    
                    # Small delay
                    time.sleep(1)
                
                # Save processed IDs
                self.save_processed_messages()
                print(f"✅ Processed {len(new_messages)} new messages")
            
        except Exception as e:
            print(f"❌ Error checking messages: {e}")
    
    def run(self):
        """Main processing loop"""
        print("🤖 InboxPay Demo Processor")
        print("=" * 60)
        print("🔄 Monitoring AgentMail inbox for new bills...")
        print(f"📧 Inbox: {settings.demo_inbox_id}")
        print(f"⏰ Check interval: {self.check_interval} seconds")
        print("🛑 Press Ctrl+C to stop")
        print("=" * 60)
        
        # Load previously processed messages
        self.load_processed_messages()
        
        # Check server is running
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code != 200:
                print("❌ Demo server is not responding")
                print("💡 Please start: python demo_app.py")
                return
        except:
            print("❌ Cannot connect to demo server")
            print("💡 Please start: python demo_app.py")
            return
        
        print("✅ Demo server is running")
        
        try:
            while True:
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"\n🔍 Checking for new messages... ({current_time})")
                
                self.check_for_new_messages()
                
                print(f"⏳ Next check in {self.check_interval} seconds...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Stopping demo processor...")
            self.save_processed_messages()
            print(f"✅ Processed message IDs saved")
            print(f"👋 Goodbye!")

def main():
    """Main function"""
    processor = DemoProcessor()
    processor.run()

if __name__ == "__main__":
    main()
