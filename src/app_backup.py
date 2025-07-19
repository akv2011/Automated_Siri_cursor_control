"""
SMS-to-Cursor Automation for VEOX Internship Challenge

This Flask app receives SMS messages via Twilio webhooks, processes them with Google's Gemini AI,
and executes corresponding actions in the Cursor AI editor.

Requirements:
1. Gemini API key    </html>
    """

@app.route('/trigger', methods=['POST'])om Google AI Studio
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

# Configure Twilio
twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone_number = '+12295970631'

if twilio_account_sid and twilio_auth_token:
    twilio_client = Client(twilio_account_sid, twilio_auth_token)
else:
    twilio_client = None
    print("⚠️ Twilio credentials not found - SMS sending disabled")

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
    
    IMPORTANT: You MUST respond with ONLY a valid JSON object, no other text.
    
    Respond with a JSON object containing:
    - action: one of [create_file, edit_file, run_code, search_code, open_file, execute_command]
    - command: the specific command or code to execute
    - description: a brief description of what will be done
    - file_path: if applicable, the file path to work with (REQUIRED for create_file)
    
    Example for file creation (always include file_path for create_file):
    {{"action": "create_file", "command": "Create a Python script that prints 'Hello World'", "description": "Creating a Python hello world script", "file_path": "hello_world.py"}}

    Example for opening a file:
    {{"action": "open_file", "command": "open_file", "description": "Opening app.py", "file_path": "app.py"}}
    
    For simple greetings like "hi" or "hello", create a simple file instead.
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
        print(f"🤖 Raw Gemini response: {response_text}")
        
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
        # Create a default action for unrecognized commands
        return CursorAction(
            action=ActionType.CREATE_FILE,
            description=f'Creating a response file for: {message}',
            command=f'Create a text file with response to: {message}',
            file_path="response.txt"
        )
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw response was: {response_text}")
        # Create a default action for JSON errors
        return CursorAction(
            action=ActionType.CREATE_FILE,
            description=f'Creating a file for command: {message}',
            command=f'Create a file based on: {message}',
            file_path="command_response.txt"
        )
    except Exception as e:
        print(f"General error: {e}")
        return CursorAction(
            action=ActionType.ERROR,
            description=f'Error processing with Gemini: {str(e)}',
            command=None
        )

def perform_cursor_action(action_data: CursorAction):
    """Send the command directly to Cursor's chat via Simple Cursor Bridge"""
    action = action_data.action
    command = action_data.command
    file_path = action_data.file_path
    
    # For ALL actions, just send the original message to Cursor's chat
    try:
        # Send message to Simple Cursor Bridge to inject into Cursor chat
        message = f"{command}"
        bridge_response = requests.post(
            "http://localhost:5001/inject",
            json={"message": message},
            timeout=10
        )
        
        if bridge_response.status_code == 200:
            return f"✅ Message '{message[:50]}...' injected into Cursor chat!"
        else:
            return f"❌ Failed to inject message to Cursor bridge (status: {bridge_response.status_code})"
            
    except Exception as e:
        return f"❌ Error connecting to Cursor bridge: {str(e)}"

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SMS-to-Cursor Automation</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .test-section { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .btn { padding: 12px 24px; font-size: 16px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
            .btn-primary { background: #007acc; color: white; }
            .btn-success { background: #28a745; color: white; }
            input[type="text"] { width: 400px; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; }
            .status { font-size: 18px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>🚀 SMS-to-Cursor Automation</h1>
        <div class="status">✅ Server Running | 📱 Twilio: +12295970631 | 💻 Bridge: Active</div>
        
        <div class="test-section">
            <h3>🧪 Method 1: Direct Test (Instant)</h3>
            <p>Type a command and test immediately:</p>
            <form action="/trigger" method="post">
                <input type="text" name="message" placeholder="Type: Create a Python hello world script" value="Create a Python hello world script">
                <button type="submit" class="btn btn-primary">🚀 Test Now</button>
            </form>
        </div>
        
        <div class="test-section">
            <h3>📱 Method 2: SMS Auto-Forward (Real SMS)</h3>
            <p>Click to send real SMS FROM your Twilio number (tests full SMS workflow):</p>
            <a href="/send_sms?message=Create a hello world Python script&to=+1234567890" class="btn btn-success">📱 Send Test SMS</a>
            <p><small>This sends SMS from +12295970631 → +1234567890 → triggers webhook → injects to Cursor</small></p>
        </div>
        
        <div class="test-section">
            <h3>📝 Example Commands to Try:</h3>
            <ul>
                <li>"Create a Python hello world script"</li>
                <li>"Write a calculator function"</li>
                <li>"Make a simple HTML webpage"</li>
                <li>"Create a Flask REST API"</li>
            </ul>
        </div>
    </body>
    </html>
    """
    <p>� Server is running! Control Cursor through multiple channels:</p>
    
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0;">
        
        <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
            <h3>📱 SMS Channel</h3>
            <p><strong>Number:</strong> +12295970631</p>
            <p><strong>Webhook:</strong> <code>/sms</code></p>
            <p>Send SMS from your verified phone to trigger automation</p>
        </div>
        
        <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
            <h3>📧 Email Channel</h3>
            <p><strong>Webhook:</strong> <code>/email</code></p>
            <p>Configure email service (Mailgun/SendGrid) to POST here</p>
        </div>
        
        <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
            <h3>💬 WhatsApp Channel</h3>
            <p><strong>Webhook:</strong> <code>/whatsapp</code></p>
            <p>Connect Twilio WhatsApp sandbox for instant messaging</p>
        </div>
        
        <div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px;">
            <h3>🎤 Voice Channel</h3>
            <p><strong>Webhook:</strong> <code>/voice</code></p>
            <p>Call your Twilio number and speak commands</p>
        </div>
        
    </div>
    
    <h3>🧪 Test Your Automation:</h3>
    <form action="/trigger" method="post" style="margin: 20px 0; padding: 20px; border: 2px solid #007acc; border-radius: 8px; background: #f8f9fa;">
        <input type="text" name="message" placeholder="Enter command to test..." style="width: 400px; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px;">
        <button type="submit" style="padding: 12px 24px; font-size: 16px; background: #007acc; color: white; border: none; border-radius: 4px; cursor: pointer;">🚀 Trigger Automation</button>
    </form>
    
    <h3>📱 SMS Auto-Forward Test:</h3>
    <p>Click a link below to send SMS FROM your Twilio number, which will auto-trigger the automation:</p>
    <div style="margin: 20px 0;">
        <a href="/send_sms?message=Create a hello world Python script&to=+1234567890" style="display: inline-block; margin: 5px; padding: 10px 15px; background: #28a745; color: white; text-decoration: none; border-radius: 4px;">📱 Test: Hello World Script</a>
        <a href="/send_sms?message=Write a calculator function&to=+1234567890" style="display: inline-block; margin: 5px; padding: 10px 15px; background: #28a745; color: white; text-decoration: none; border-radius: 4px;">📱 Test: Calculator Function</a>
        <a href="/send_sms?message=Create a simple web page&to=+1234567890" style="display: inline-block; margin: 5px; padding: 10px 15px; background: #28a745; color: white; text-decoration: none; border-radius: 4px;">📱 Test: Web Page</a>
    </div>
    
    <h3>📝 Example Commands:</h3>
    <ul style="columns: 2; column-gap: 40px;">
        <li>"Create a hello world Python script"</li>
        <li>"Write me a calculator function"</li>
        <li>"Make a simple web page with HTML"</li>
        <li>"Search for TODO in my code"</li>
        <li>"Create a REST API with Flask"</li>
        <li>"Write a data visualization script"</li>
    </ul>
    
    <h3>🔗 Available Endpoints:</h3>
    <ul>
        <li><code>POST /sms</code> - Twilio SMS webhook</li>
        <li><code>POST /email</code> - Email automation webhook</li>
        <li><code>POST /whatsapp</code> - WhatsApp webhook</li>
        <li><code>POST /voice</code> - Voice call webhook</li>
        <li><code>POST /trigger</code> - Manual web form trigger</li>
    </ul>
    """

@app.route('/trigger', methods=['POST'])
def trigger_automation():
    """Manual trigger for testing automation without SMS"""
    message = request.form.get('message', '').strip()
    
    if not message:
        return "<h2>❌ No message provided</h2><a href='/'>Go back</a>"
    
    try:
        # Process with Gemini
        action_data = process_with_gemini(message)
        result = perform_cursor_action(action_data)
        
        return f"""
        <h2>✅ Automation Triggered Successfully!</h2>
        <p><strong>Command:</strong> {message}</p>
        <p><strong>Action:</strong> {action_data.description}</p>
        <p><strong>Result:</strong> {result}</p>
        <a href='/'>Test another command</a>
        """
        
    except Exception as e:
        return f"""
        <h2>❌ Error</h2>
        <p>{str(e)}</p>
        <a href='/'>Go back</a>
        """

@app.route('/send_sms', methods=['GET'])
def send_sms():
    """Send SMS FROM Twilio number to trigger automation"""
    message = request.args.get('message', 'Create a hello world Python script')
    to_number = request.args.get('to', '+1234567890')  # Default test number
    
    if not twilio_client:
        return """
        <h2>❌ Twilio Not Configured</h2>
        <p>Please add TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN to your .env file</p>
        <a href='/'>Go back</a>
        """
    
    try:
        # Send SMS FROM your Twilio number
        sms = twilio_client.messages.create(
            body=message,
            from_=twilio_phone_number,
            to=to_number
        )
        
        return f"""
        <h2>✅ SMS Sent Successfully!</h2>
        <p><strong>Message:</strong> {message}</p>
        <p><strong>From:</strong> {twilio_phone_number}</p>
        <p><strong>To:</strong> {to_number}</p>
        <p><strong>SID:</strong> {sms.sid}</p>
        <p>The webhook should trigger automatically when Twilio processes this message!</p>
        <a href='/'>Go back</a>
        """
        
    except Exception as e:
        return f"""
        <h2>❌ SMS Send Failed</h2>
        <p><strong>Error:</strong> {str(e)}</p>
        <a href='/'>Go back</a>
        """

@app.route('/sms', methods=['POST'])
def sms_webhook():
    # Get the incoming message details
    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '')
    to_number = request.values.get('To', '')
    direction = request.values.get('Direction', 'inbound')
    
    print(f"📱 SMS Received: '{incoming_msg}' from {from_number} to {to_number} ({direction})")
    
    try:
        # Check if this is an outbound message FROM our Twilio number
        if from_number == '+12295970631':
            print(f"🔄 Outbound message detected, auto-forwarding to automation...")
            # This is a message we sent, treat it as automation command
            incoming_msg = incoming_msg.replace("Sent from your Twilio trial account - ", "")
            
        # Process the message with Gemini
        action_data = process_with_gemini(incoming_msg)
        print(f"🤖 Gemini processed: {action_data.action} - {action_data.description}")
        
        # Perform the action in Cursor
        result = perform_cursor_action(action_data)
        print(f"✅ Action result: {result}")
        
        # Create a structured response
        sms_response = SMSResponse(
            message=f"✅ Command: {incoming_msg[:30]}...\n🎯 Action: {action_data.description[:50]}...\n📄 Result: {result[:50]}...",
            success=action_data.action != ActionType.ERROR,
            action_performed=action_data.description
        )
        
        # Send back the summary
        resp = MessagingResponse()
        msg = resp.message()
        msg.body(sms_response.to_sms_format())
        
        return str(resp)
        
    except Exception as e:
        print(f"❌ Error processing SMS: {e}")
        # Error handling with structured response
        error_response = SMSResponse(
            message=f"❌ System error: {str(e)[:80]}",
            success=False
        )
        
        resp = MessagingResponse()
        msg = resp.message()
        msg.body(error_response.to_sms_format())
        return str(resp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)