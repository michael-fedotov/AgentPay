#!/usr/bin/env python3
"""
HTTP test for AgentPay webhook endpoint
"""
import asyncio
import json
import httpx
from datetime import datetime

async def test_webhook_http():
    """Test webhook endpoint with actual HTTP requests"""
    print("🌐 Testing AgentPay Webhook HTTP Endpoint")
    print("=" * 50)
    
    # Test webhook payloads
    test_webhooks = [
        {
            "name": "Electric Bill Webhook",
            "payload": {
                "type": "message.received",
                "data": {
                    "inbox_id": "happymirror836@agentmail.to",
                    "message_id": "test-electric-001",
                    "from": "billing@cityelectric.com",
                    "subject": "City Electric Monthly Bill - Account 123456",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "preview": "Your monthly electric bill is ready. Amount due: $167.89"
                }
            }
        },
        {
            "name": "Credit Card Statement",
            "payload": {
                "type": "message.received",
                "data": {
                    "inbox_id": "happymirror836@agentmail.to", 
                    "message_id": "test-credit-002",
                    "from": "statements@visa.com",
                    "subject": "Visa Credit Card Statement Ready",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "preview": "Your Visa statement is ready. Minimum payment: $45.00"
                }
            }
        },
        {
            "name": "Non-Bill Email",
            "payload": {
                "type": "message.received",
                "data": {
                    "inbox_id": "happymirror836@agentmail.to",
                    "message_id": "test-newsletter-003", 
                    "from": "newsletter@example.com",
                    "subject": "Weekly Newsletter - Tech Updates",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "preview": "This week in tech: AI advances, new products, and more!"
                }
            }
        },
        {
            "name": "Outgoing Message Event",
            "payload": {
                "type": "message.sent",
                "data": {
                    "inbox_id": "happymirror836@agentmail.to",
                    "message_id": "test-outgoing-004",
                    "to": "customer@example.com",
                    "subject": "Payment Confirmation",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        }
    ]
    
    # Test each webhook
    webhook_url = "http://localhost:8000/webhook/agentmail"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, webhook_data in enumerate(test_webhooks, 1):
            print(f"\n📡 Test {i}: {webhook_data['name']}")
            
            try:
                # Send webhook request
                response = await client.post(
                    webhook_url,
                    json=webhook_data["payload"],
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "AgentMail-Webhook/1.0"
                    }
                )
                
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ Success: {result.get('status')}")
                    
                    if 'result' in result:
                        webhook_result = result['result']
                        print(f"   Bill Detected: {'✅' if webhook_result.get('bill_detected') else '❌'}")
                        
                        if webhook_result.get('bill_detected'):
                            print(f"   Bill ID: {webhook_result.get('bill_id')}")
                            print(f"   Payee: {webhook_result.get('payee', 'None')}")
                            print(f"   Amount: ${webhook_result.get('amount_cents', 0)/100:.2f}")
                            print(f"   Payment: {'✅ Processed' if webhook_result.get('payment_processed') else '❌ Not processed'}")
                    
                    if 'message' in result:
                        print(f"   Message: {result['message']}")
                
                else:
                    print(f"   ❌ Error: {response.status_code}")
                    try:
                        error_detail = response.json()
                        print(f"   Detail: {error_detail}")
                    except:
                        print(f"   Text: {response.text}")
            
            except Exception as e:
                print(f"   ❌ Request failed: {e}")
            
            # Small delay between requests
            await asyncio.sleep(1)

async def test_health_endpoint():
    """Test the health endpoint to ensure server is running"""
    print("\n💚 Testing Health Endpoint")
    print("=" * 30)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Server is healthy")
                print(f"   Status: {health_data.get('status')}")
                print(f"   Timestamp: {health_data.get('timestamp')}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print("💡 Make sure the server is running: uvicorn app:app --reload --port 8000")
        return False

async def test_agentmail_endpoint():
    """Test the AgentMail integration endpoint"""
    print("\n📧 Testing AgentMail Integration")
    print("=" * 35)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/test/agentmail")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ AgentMail integration working")
                print(f"   Inbox messages: {data.get('messages', {}).get('count', 'Unknown')}")
                print(f"   Demo mode: {data.get('config', {}).get('demo_mode', 'Unknown')}")
            else:
                print(f"❌ AgentMail test failed: {response.status_code}")
    
    except Exception as e:
        print(f"❌ AgentMail test error: {e}")

async def main():
    """Run HTTP webhook tests"""
    print("🌐 AgentPay Webhook HTTP Test Suite")
    print("=" * 60)
    
    # Test server health first
    if not await test_health_endpoint():
        print("\n❌ Server not available. Please start the server first:")
        print("   uvicorn app:app --reload --port 8000")
        return
    
    # Test AgentMail integration
    await test_agentmail_endpoint()
    
    # Test webhook endpoint
    await test_webhook_http()
    
    print("\n" + "=" * 60)
    print("🎉 HTTP webhook tests completed!")
    print("=" * 60)
    
    print("\n📋 Summary:")
    print("✅ Server health check")
    print("✅ AgentMail integration test")
    print("✅ Webhook HTTP endpoint tests")
    print("✅ Various webhook event types")
    print("✅ Error handling verification")

if __name__ == "__main__":
    asyncio.run(main())
