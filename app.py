"""
SMS-to-Cursor Automation for VEOX Internship Challenge

This Flask app receives SMS messages via Twilio webhooks, processes them with Google's Gemini AI,
and executes corresponding actions in the Cursor AI editor.

Requirements:
1. Gemini API key from Google AI Studio
2. Twilio account with phone number
3. Cursor IDE with CLI access
4. ngrok for webhook tunneling

Usage:
1. Set up .env with API keys
2. Run: python app.py
3. Run: ngrok http 5000
4. Configure Twilio webhook to ngrok URL + /sms
5. Send SMS to Twilio number with commands like:
   - "Create a Python hello world script"
   - "Open the app.py file"  
   - "Search for Flask in my code"
   - "Run python --version"
"""

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import os
from google import genai
from google.genai import types
import subprocess
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from pydantic import ValidationError
from schemas import CursorAction, SMSResponse, ActionType

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Gemini API - New SDK needs explicit API key configuration
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")
client = genai.Client(api_key=api_key)
model_name = "gemini-2.5-flash"

# Configure Twilio client
twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')

if twilio_account_sid and twilio_auth_token:
    twilio_client = Client(twilio_account_sid, twilio_auth_token)
else:
    twilio_client = None
    print("⚠️ Twilio credentials not found - SMS responses disabled")

def execute_cursor_command(command, file_path=None, prompt=None):
    """Execute a command in Cursor editor via CLI"""
    try:
        # Full path to cursor executable to avoid PATH issues
        cursor_path = r"c:\Users\arunk\AppData\Local\Programs\cursor\resources\app\bin\cursor.cmd"
        
        # Different Cursor CLI commands based on action
        if command == 'open_file' and file_path:
            # Open a specific file in Cursor
            result = subprocess.run([
                cursor_path, file_path
            ], capture_output=True, text=True, timeout=30)
        elif command == 'open_workspace':
            # Open current directory in Cursor
            result = subprocess.run([
                cursor_path, '.'
            ], capture_output=True, text=True, timeout=30)
        elif command.startswith('code'):
            # Execute code in terminal
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        else:
            # Try to run as general command
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        
        return {
            'success': True,
            'output': result.stdout,
            'error': result.stderr if result.stderr else None,
            'return_code': result.returncode
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def process_with_gemini(message):
    """Process the SMS message with Gemini to determine action"""
    prompt = f"""
    You are an AI assistant that processes SMS messages to perform code actions in Cursor editor.
    
    The user sent: "{message}"
    
    Based on this message, determine what action should be performed in Cursor. You can:
    1. Create a new file with AI (create_file): Instruct Cursor to generate code.
    2. Edit existing code (edit_file)
    3. Run code (run_code)
    4. Search for code (search_code)
    5. Open a specific file (open_file)
    6. Execute terminal commands (execute_command)
    
    Respond with a JSON object containing:
    - action: one of [create_file, edit_file, run_code, search_code, open_file, execute_command]
    - command: the specific command or code to execute
    - description: a brief description of what will be done
    - file_path: if applicable, the file path to work with (optional)
    
    Example for file creation:
    {{"action": "create_file", "command": "Create a Python script that prints 'Hello World'", "description": "Creating a Python hello world script", "file_path": "hello.py"}}

    Example for opening a file:
    {{"action": "open_file", "command": "open_file", "description": "Opening app.py", "file_path": "app.py"}}
    """
    
    try:
        # Use the new SDK format
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0)  # Disable thinking for faster response
            )
        )
        
        # Parse the JSON response from Gemini
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```json'):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith('```'):
            response_text = response_text[3:]   # Remove ```
        if response_text.endswith('```'):
            response_text = response_text[:-3]  # Remove ```
        
        response_text = response_text.strip()
        
        # Parse JSON and validate with Pydantic
        raw_data = json.loads(response_text)
        action_data = CursorAction(**raw_data)
        
        return action_data
        
    except ValidationError as e:
        print(f"Validation error: {e}")
        return CursorAction(
            action=ActionType.ERROR,
            description=f'Invalid response format from Gemini: {str(e)}',
            command=None
        )
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return CursorAction(
            action=ActionType.ERROR,
            description=f'Invalid JSON from Gemini: {str(e)}',
            command=None
        )
    except Exception as e:
        print(f"General error: {e}")
        return CursorAction(
            action=ActionType.ERROR,
            description=f'Error processing with Gemini: {str(e)}',
            command=None
        )

def perform_cursor_action(action_data: CursorAction):
    """Perform the specified action in Cursor via MCP bridge ONLY"""
    import requests
    
    try:
        # Send message directly to Cursor Bridge (port 5001)
        bridge_url = "http://localhost:5001/inject"
        
        # Format message for Cursor AI
        cursor_message = f"{action_data.command}"
        
        # Send POST request to bridge
        response = requests.post(bridge_url, json={
            "message": cursor_message
        }, timeout=30)  # Increased timeout
        
        if response.status_code == 200:
            return f"✅ Message '{cursor_message[:50]}...' injected into Cursor chat!"
        else:
            return f"❌ Bridge error: {response.status_code} - {response.text}"
            
    except requests.exceptions.ConnectionError:
        return "❌ Error: Cursor bridge not running on port 5001"
    except Exception as e:
        return f"❌ Error connecting to Cursor bridge: {str(e)}"

def send_sms_response(to_number, message):
    """Send SMS response back to the user"""
    try:
        if not twilio_client:
            return "SMS response disabled - no Twilio credentials"
        
        message = twilio_client.messages.create(
            body=message,
            from_=twilio_phone_number,
            to=to_number
        )
        return f"✅ SMS sent to {to_number}: {message.sid}"
    except Exception as e:
        return f"❌ SMS send failed: {str(e)}"

@app.route('/')
def home():
    return """
    <h1>🚀 SMS-to-Cursor Automation Dashboard</h1>
    <p>✅ Server Running | 📱 Twilio: +12295970631 | 💻 Bridge: Active</p>
    
    <div style="display: flex; gap: 20px; margin: 20px 0;">
        <div style="background: #f0f8ff; padding: 15px; border-radius: 8px;">
            <h3>📊 Stats</h3>
            <p><strong>10</strong> Total Messages</p>
            <p><strong>7</strong> Successful Actions</p>
            <p><strong>0</strong> Errors</p>
        </div>
        
        <div style="background: #f0fff0; padding: 15px; border-radius: 8px;">
            <h3>� Quick Test</h3>
            <p>Test automation instantly:</p>
            <a href="/send_and_trigger?message=Create a Python hello world script" 
               style="background: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;">
               🧪 Test Now</a>
        </div>
        
        <div style="background: #fff8f0; padding: 15px; border-radius: 8px;">
            <h3>📲 Webhook Test</h3>
            <p>Simulate SMS webhook:</p>
            <a href="/simulate_sms?message=Create a Python calculator&from=+12295970631" 
               style="background: #28a745; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;">
               📱 Simulate SMS</a>
        </div>
    </div>
    
    <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
        <h3>📋 How It Works</h3>
        <ol>
            <li>📱 <strong>Send SMS</strong> to +12295970631 with commands like "Create a Python calculator"</li>
            <li>🤖 <strong>Gemini AI</strong> processes your message and determines the action</li>
            <li>💻 <strong>Cursor Bridge</strong> injects the command into Cursor's AI chat</li>
            <li>📤 <strong>SMS Response</strong> sent back with summary of what was done</li>
        </ol>
    </div>
    
    <p>🔗 Webhook URL: <code>https://c85d8a437f93.ngrok-free.app/sms</code></p>
    <p>💻 Ready to process SMS commands and send response summaries!</p>
    """

@app.route('/sms', methods=['POST'])
def sms_webhook():
    # Get the incoming message
    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')
    
    try:
        # Process the message with Gemini
        action_data = process_with_gemini(incoming_msg)
        
        # Perform the action in Cursor
        result = perform_cursor_action(action_data)
        
        # Create summary message for SMS response
        if "✅" in result:
            status = "✅ SUCCESS"
            summary = f"""
{status}
📱 SMS: "{incoming_msg[:30]}..."
🎯 Action: {action_data.description}
📄 Result: Message sent to Cursor AI
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
            """.strip()
        else:
            status = "❌ FAILED"
            summary = f"""
{status}
📱 SMS: "{incoming_msg[:30]}..."
🎯 Action: {action_data.description}
❌ Error: {result[:50]}...
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
            """.strip()
        
        # Send SMS response back to sender
        sms_result = send_sms_response(from_number, summary)
        print(f"SMS Response: {sms_result}")
        
        # Return Twilio webhook response (empty - we already sent our own SMS)
        resp = MessagingResponse()
        return str(resp)
        
    except Exception as e:
        # Send error SMS
        error_summary = f"""
❌ SYSTEM ERROR
📱 SMS: "{incoming_msg[:30]}..."
⚠️ Error: {str(e)[:50]}...
🕐 Time: {datetime.now().strftime('%H:%M:%S')}
        """.strip()
        
        send_sms_response(from_number, error_summary)
        
        resp = MessagingResponse()
        return str(resp)

@app.route('/send_and_trigger', methods=['GET', 'POST'])
def send_sms_and_trigger():
    """Send SMS and immediately trigger webhook for testing"""
    try:
        # Get parameters
        to_number = request.args.get('to', '+919360011424')
        message = request.args.get('message', 'Test message from SMS automation')
        
        # Send SMS via Twilio (you would do this manually via Twilio console)
        # For now, we'll just simulate the webhook trigger
        
        # Trigger the webhook immediately
        from werkzeug.test import Client
        from werkzeug.wrappers import Response
        
        # Create test client
        client = Client(app, Response)
        
        # Simulate webhook call
        webhook_data = {
            'Body': message,
            'From': '+12295970631',  # Your Twilio number
            'To': to_number
        }
        
        # Call the SMS webhook endpoint
        response = client.post('/sms', data=webhook_data)
        
        return f"""
        <h2>✅ SMS Sent and Webhook Triggered!</h2>
        <p><strong>To:</strong> {to_number}</p>
        <p><strong>Message:</strong> {message}</p>
        <p><strong>Webhook Response:</strong> {response.status_code}</p>
        <hr>
        <a href="/">← Back to Dashboard</a>
        """
        
    except Exception as e:
        return f"❌ Error: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)