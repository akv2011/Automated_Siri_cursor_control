# SMS to Cursor Automation - Setup Guide

## What this does:
- Receive SMS messages via Twilio
- Process them with Google Gemini AI
- Execute actions in Cursor editor
- Send back SMS summaries

## Quick Setup:

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up environment variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### 3. Get API Keys

**Twilio** (for SMS):
- Sign up at https://www.twilio.com/
- Get your Account SID, Auth Token, and Phone Number
- Add webhook URL: `https://your-ngrok-url.ngrok.io/sms`

**Gemini API** (for AI processing):
- Go to https://makersuite.google.com/app/apikey
- Create a new API key
- Add it to your `.env` file

**Ngrok** (for local development):
- Sign up at https://ngrok.com/
- Get your auth token
- Install ngrok: `npm install -g ngrok`

### 4. Run the app
```bash
# Terminal 1 - Start the Flask app
python app.py

# Terminal 2 - Start ngrok tunnel
ngrok http 5000
```

### 5. Test it
- Send SMS to your Twilio number
- Watch the magic happen in Cursor!

## Example SMS Commands:
- "Create a Python hello world script"
- "Open app.py file"
- "Search for flask in my code"
- "Run python --version"
- "Make a new file called test.js with console.log('Hello')"

## Troubleshooting:
- Make sure Cursor CLI is installed: `cursor --version`
- Check your API keys are correct
- Verify ngrok is exposing port 5000
- Check Flask app is running on port 5000
