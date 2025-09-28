#!/usr/bin/env python3
"""
Automatic email processor for AgentPay
This script continuously monitors the AgentMail inbox and automatically processes new bills
"""
import asyncio
import requests
import json
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Set

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import agentmail_get_messages, settings

class AutoProcessor:
    def __init__(self):
        self.processed_message_ids: Set[str] = set()
        self.last_check = datetime.now()
        self.check_interval = 30  # Check every 30 seconds
        
    def load_processed_messages(self):
        """Load previously processed message IDs from file"""
        try:
            if os.path.exists('processed_messages.json'):
                with open('processed_messages.json', 'r') as f:
                    data = json.load(f)
                    self.processed_message_ids = set(data.get('processed_ids', []))
                    print(f"📋 Loaded {len(self.processed_message_ids)} previously processed messages")
        except Exception as e:
            print(f"⚠️ Could not load processed messages: {e}")
    
    def save_processed_messages(self):
        """Save processed message IDs to file"""
        try:
            with open('processed_messages.json', 'w') as f:
                json.dump({
                    'processed_ids': list(self.processed_message_ids),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save processed messages: {e}")
    
    def is_bill_like(self, message) -> bool:
        """Determine if a message looks like a bill"""
        subject = getattr(message, 'subject', '').lower()
        preview = getattr(message, 'preview', '').lower()
        from_email = getattr(message, 'from_', '').lower()
        
        # Skip messages from AgentMail itself (confirmations, etc.)
        if 'agentmail.to' in from_email:
            return False
        
        # Look for bill-like keywords
        bill_keywords = [
            'bill', 'invoice', 'statement', 'payment', 'due', 'amount',
            'electric', 'gas', 'water', 'phone', 'internet', 'credit card',
            'utility', 'wireless', 'cable', 'insurance', 'mortgage', 'comed',
            'pge', 'verizon', 'chase', 'visa', 'mastercard', 'amex'
        ]
        
        text_to_check = f"{subject} {preview}".lower()
        
        # Also check if it contains dollar amounts or due dates
        has_amount = any(word in text_to_check for word in ['$', 'dollar', 'amount', 'total', 'balance'])
        has_bill_keywords = any(keyword in text_to_check for keyword in bill_keywords)
        
        return has_bill_keywords or has_amount
    
    def is_recent_message(self, message) -> bool:
        """Check if message is recent (within last hour)"""
        try:
            msg_time = getattr(message, 'timestamp', None)
            if not msg_time:
                return True  # Process if we can't determine time
            
            # Convert to datetime if it's a string
            if isinstance(msg_time, str):
                # Handle different timestamp formats
                try:
                    if msg_time.endswith('Z'):
                        msg_time = datetime.fromisoformat(msg_time.replace('Z', '+00:00'))
                    else:
                        msg_time = datetime.fromisoformat(msg_time)
                except:
                    return True
            
            # Check if message is from the last hour
            time_diff = datetime.now(msg_time.tzinfo) - msg_time
            return time_diff < timedelta(hours=1)
        except:
            return True  # Process if we can't determine time
    
    def process_message(self, message) -> bool:
        """Process a single message via webhook"""
        webhook_payload = {
            "type": "message.received",
            "data": {
                "inbox_id": message.inbox_id,
                "message_id": message.message_id,
                "from": getattr(message, 'from_', 'unknown@example.com'),
                "subject": getattr(message, 'subject', 'No Subject'),
                "timestamp": getattr(message, 'timestamp', datetime.utcnow()).isoformat() + "Z",
                "preview": getattr(message, 'preview', '')
            }
        }
        
        try:
            response = requests.post(
                "http://localhost:8000/webhook/agentmail",
                json=webhook_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('result', {}).get('success'):
                    webhook_result = result['result']
                    if webhook_result.get('bill_detected'):
                        print(f"   ✅ Bill processed successfully!")
                        print(f"      💰 Amount: ${webhook_result.get('amount_cents', 0)/100:.2f}")
                        print(f"      🏢 Payee: {webhook_result.get('payee', 'Unknown')}")
                        print(f"      💳 Payment: {'✅ Processed' if webhook_result.get('payment_processed') else '❌ Failed'}")
                        return True
                    else:
                        print(f"   ⚠️ Not identified as a bill")
                        return False
                else:
                    webhook_result = result.get('result', {})
                    print(f"   ❌ Processing failed: {webhook_result.get('error', 'Unknown error')}")
                    return False
            else:
                print(f"   ❌ Webhook failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Error processing: {e}")
            return False
    
    async def check_for_new_messages(self):
        """Check for new messages and process them"""
        try:
            # Get messages from inbox
            messages_result = agentmail_get_messages(settings.demo_inbox_id)
            if not messages_result["success"]:
                print(f"❌ Failed to fetch messages: {messages_result.get('error')}")
                return
            
            messages = messages_result["messages"]
            new_messages = []
            
            # Find new messages that haven't been processed
            for message in messages:
                if (message.message_id not in self.processed_message_ids and 
                    self.is_bill_like(message) and 
                    self.is_recent_message(message)):
                    new_messages.append(message)
            
            if new_messages:
                print(f"\n📧 Found {len(new_messages)} new bill-like messages to process")
                
                for i, message in enumerate(new_messages, 1):
                    print(f"\n📋 Processing {i}/{len(new_messages)}:")
                    print(f"   📧 Subject: {getattr(message, 'subject', 'No Subject')}")
                    print(f"   👤 From: {getattr(message, 'from_', 'Unknown')}")
                    print(f"   🕒 Time: {getattr(message, 'timestamp', 'Unknown')}")
                    
                    success = self.process_message(message)
                    
                    # Mark as processed regardless of success to avoid reprocessing
                    self.processed_message_ids.add(message.message_id)
                    
                    if success:
                        print(f"   🎉 Successfully processed and payment scheduled!")
                    
                    # Small delay between processing
                    await asyncio.sleep(2)
                
                # Save processed IDs
                self.save_processed_messages()
                print(f"✅ Processed {len(new_messages)} new messages")
            
        except Exception as e:
            print(f"❌ Error checking messages: {e}")
    
    async def run(self):
        """Main processing loop"""
        print("🚀 AgentPay Automatic Email Processor")
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
                print("❌ AgentPay server is not responding")
                return
        except:
            print("❌ Cannot connect to AgentPay server")
            print("💡 Please start the server: uvicorn app:app --reload --port 8000")
            return
        
        print("✅ AgentPay server is running")
        
        try:
            while True:
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"\n🔍 Checking for new messages... ({current_time})")
                
                await self.check_for_new_messages()
                
                print(f"⏳ Next check in {self.check_interval} seconds...")
                await asyncio.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Stopping automatic processor...")
            self.save_processed_messages()
            print(f"✅ Processed message IDs saved")
            print(f"👋 Goodbye!")

def main():
    """Main function"""
    processor = AutoProcessor()
    asyncio.run(processor.run())

if __name__ == "__main__":
    main()
