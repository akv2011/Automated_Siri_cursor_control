# SMS-to-Cursor Automation 🚀

This project enables you to send SMS messages that trigger automated actions in the Cursor AI editor. Perfect for the VEOX internship challenge!

## Features

- 📱 **SMS Integration**: Send text messages via Twilio
- 🤖 **AI Processing**: Uses Google Gemini to understand your requests
- 💻 **Cursor Control**: Executes actions in the Cursor editor
- 📤 **Smart Responses**: Sends back SMS-friendly summaries

## Quick Start

1. **Clone and Setup**:
   ```bash
   git clone <your-repo>
   cd Automated_Siri_cursor_control
   python setup.py
   ```

2. **Environment Setup**:
   ```bash
   cp .env.example .env
   # Fill in your API keys in .env
   ```

3. **Required API Keys**:
   - **Twilio**: Account SID, Auth Token, Phone Number
   - **Gemini**: API Key from Google AI Studio
   - **Ngrok**: Auth token for webhook tunneling

4. **Run the Application**:
   ```bash
   python app.py
   ```

5. **Expose with Ngrok**:
   ```bash
   ngrok http 5000
   ```

6. **Configure Twilio Webhook**:
   - Set webhook URL to: `https://your-ngrok-url.ngrok.io/sms`

## How It Works

1. **SMS → Flask**: Twilio forwards your SMS to the Flask webhook
2. **AI Processing**: Gemini analyzes your message and determines the action
3. **Cursor Execution**: The app executes the appropriate action in Cursor
4. **Response**: You get an SMS summary of what happened

## Example Usage

Send these SMS messages to try it out:

- `"Create a hello world Python script"`
- `"Search for TODO comments in my code"`
- `"Run my main.py file"`
- `"Open the config.json file"`

## API Keys Setup

### Twilio
1. Sign up at [twilio.com](https://twilio.com)
2. Get your Account SID and Auth Token
3. Buy a phone number for SMS

### Google Gemini
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Add it to your .env file

### Ngrok
1. Sign up at [ngrok.com](https://ngrok.com)
2. Get your auth token
3. Install ngrok and authenticate

## Architecture

```
SMS → Twilio → Flask App → Gemini AI → Cursor Actions → SMS Response
```

## Troubleshooting

- **Cursor CLI not found**: Install Cursor editor with CLI support
- **API errors**: Check your .env file has correct keys
- **Webhook issues**: Ensure ngrok is running and webhook URL is correct

## Contributing

This is for the VEOX internship challenge! Make it awesome! 🎯

## License

MIT License - Feel free to use and modify!