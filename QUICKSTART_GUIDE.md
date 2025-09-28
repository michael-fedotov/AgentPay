# InboxPay QuickStart Guide

## 🚀 How to Run Your AgentPay app.py

### Step 1: Environment Setup
Make sure your `.env` file has all required variables:

```bash
cat .env
```

**Required variables:**
```env
AGENTMAIL_API_KEY=your_key_here
DEMO_INBOX_ID=your_inbox_id
GEMINI_API_KEY=your_gemini_key
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
# OR if using pyproject.toml:
pip install -e .
```

### Step 3: Check Database
```bash
# If you want a fresh start, delete the old database:
rm inboxpay.db
```

### Step 4: Start the Server
```bash
python -m uvicorn app:app --reload --port 8000
```

**Expected output:**
```
INFO:     Will watch for changes in these directories: ['/Users/.../AgentPay']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using watchfiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 5: Test the Server
Open another terminal and test:
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","timestamp":"..."}
```

### Step 6: Open Dashboard
Open in browser: **http://localhost:8000**

---

## 🧪 Testing Your System

### Option A: Manual Processing
```bash
# Process emails already in your inbox:
python quick_process.py
```

### Option B: Send Test Email
```bash
# Send a test bill email:
python test_send_email.py
```

### Option C: Complete Workflow Test
```bash
# Test the full send → extract → pay → confirm workflow:
python test_complete_flow.py
```

---

## 📧 For Demo (Automatic Processing)

### Option 1: Use Polling (No ngrok needed)
```bash
# Terminal 1: Start server
python -m uvicorn app:app --reload --port 8000

# Terminal 2: Start automatic processor
python auto_processor.py
```

### Option 2: Use Real Webhooks (Requires ngrok)
```bash
# Terminal 1: Start server
python -m uvicorn app:app --reload --port 8000

# Terminal 2: Setup ngrok (need to sign up)
ngrok http 8000

# Terminal 3: Configure webhook in AgentMail dashboard
# Then send emails and they'll be processed automatically
```

---

## 🛠️ Troubleshooting

### Problem: Server won't start
**Error:** `[Errno 48] Address already in use`
```bash
# Kill processes on port 8000
lsof -ti:8000 | xargs kill -9
```

### Problem: Database errors
**Error:** `table bills has no column named inbox_id`
```bash
# Delete and recreate database
rm inboxpay.db
# Restart server - it will recreate the tables
```

### Problem: Import errors
**Error:** `ModuleNotFoundError: No module named 'google.generativeai'`
```bash
pip install google-generativeai
```

### Problem: AgentMail connection
**Error:** `Failed to fetch messages`
```bash
# Test AgentMail connection:
python test_agentmail.py
```

### Problem: Gemini not working
**Error:** `LLM API error 404`
```bash
# Test Gemini specifically:
python test_gemini_fix.py
```

---

## 🎯 Current Endpoints

Your `app.py` has these endpoints:

- `GET /` - Dashboard (main page)
- `GET /health` - Health check
- `POST /webhook/agentmail` - AgentMail webhook handler
- `GET /bills` - List all bills (JSON API)
- `POST /bills/{bill_id}/pay` - Manual payment trigger
- Various test endpoints for development

---

## 📋 What Each File Does

- **`app.py`** - Main FastAPI application (the one you want to run)
- **`test_agentmail.py`** - Test AgentMail connection
- **`test_send_email.py`** - Send test bills
- **`test_complete_flow.py`** - End-to-end workflow test
- **`auto_processor.py`** - Automatic email processing (polling)
- **`quick_process.py`** - Interactive email processing tool
- **`process_inbox.py`** - Batch process all emails

---

## 🎬 For Live Demo

**Recommended flow:**
1. Start server: `python -m uvicorn app:app --reload --port 8000`
2. Open dashboard: http://localhost:8000
3. Send test email: `python test_send_email.py`
4. Process manually: `python quick_process.py` (option 1)
5. Show the dashboard - bill appears!
6. Show the confirmation email in your personal inbox

**For fully automatic demo:**
1. Start server: `python -m uvicorn app:app --reload --port 8000`
2. Start processor: `python auto_processor.py`
3. Send email to `happymirror836@agentmail.to`
4. Watch it get processed automatically!

---

## 💳 Method API Integration

Your system is ready for Method API! See `METHOD_INTEGRATION.md` for how to add real payments.

Currently using "DRYRUN" payments which are perfect for demos.

---

## ✅ Success Criteria

You'll know it's working when:

1. ✅ Server starts without errors
2. ✅ Dashboard loads at http://localhost:8000
3. ✅ Health check returns `{"status":"healthy"}`
4. ✅ You can send a test email and see it processed
5. ✅ Bills appear in the dashboard
6. ✅ Confirmation emails are sent

**That's it! Your AgentPay system is ready! 🚀**
