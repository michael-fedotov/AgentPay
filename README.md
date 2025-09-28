# InboxPay FastAPI

A FastAPI application for inbox-based payment processing using AgentMail.

## Setup

1. Install dependencies using uv or pip:
   ```bash
   # Using uv (recommended)
   uv pip install -e .
   
   # Or using pip
   pip install -e .
   ```

2. Copy `.env` file and fill in your API keys:
   ```bash
   cp .env .env.local
   # Edit .env.local with your actual API keys
   ```

## Running the Application

Start the FastAPI development server:

```bash
uvicorn app:app --reload --port 8000
```

The application will be available at `http://localhost:8000`

## Webhook Setup

To receive AgentMail webhooks, configure your AgentMail webhook endpoint to:

```
POST https://<your-host>/webhook/agentmail
```

Replace `<your-host>` with your actual domain or ngrok URL for local development.

## Environment Variables

Fill in the following environment variables in your `.env` file:

- `AGENTMAIL_API_KEY`: Your AgentMail API key
- `METHOD_API_KEY`: Your Method API key
- `USER_EMAIL`: Your email address
- `DEMO_MODE`: Set to `true` for demo mode
- `WEBHOOK_SECRET`: Webhook secret for AgentMail
- `AGENTMAIL_BASE`: AgentMail API base URL
- `DEMO_INBOX_ID`: Demo inbox ID from AgentMail dashboard
- `DEMO_AGENT_TO`: Demo agent email from AgentMail dashboard
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_MODEL`: OpenAI model to use (default: gpt-4o-mini)
- `DB_URL`: Database URL (default: SQLite)

## Development

For development with type checking and linting:

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run linting
ruff check .

# Format code
ruff format .
```
MHacks 2025
