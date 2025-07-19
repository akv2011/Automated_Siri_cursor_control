"""
SMS-to-Cursor Automation for VEOX Internship Challenge

This Flask app receives SMS messages via Twilio webhooks, processes them with Google's Gemini AI,
and executes corresponding actions in the Cursor AI editor.
"""

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import os
from google import genai
from google.genai import types
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from pydantic import ValidationError
from schemas import CursorAction, SMSResponse, ActionType

# Load environment variables
load_dotenv()

app = Flask(__name__)

# In-memory logs for UI display
activity_logs = []
MAX_LOGS = 50  # Keep last 50 activities

def add_log(log_type, message, phone_number=None, action=None, result=None):
    """Add activity log entry"""
    log_entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'type': log_type,  # 'SMS_RECEIVED', 'SMS_SENT', 'ACTION_PERFORMED', 'ERROR'
        'message': message,
        'phone_number': phone_number,
        'action': action,
        'result': result
    }
    activity_logs.append(log_entry)
    
    # Keep only last MAX_LOGS entries
    if len(activity_logs) > MAX_LOGS:
        activity_logs.pop(0)
    
    print(f"📝 LOG: [{log_type}] {message}")

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
    command = action_data.command
    
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
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .container { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .section { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 10px 0; }
            .logs-section { grid-column: 1 / -1; max-height: 400px; overflow-y: auto; }
            .btn { padding: 12px 24px; font-size: 16px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
            .btn-primary { background: #007acc; color: white; }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            input[type="text"] { width: 300px; padding: 12px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; }
            .status { font-size: 18px; margin: 10px 0; color: #28a745; }
            .log-entry { padding: 8px; margin: 4px 0; border-left: 4px solid #007acc; background: white; border-radius: 4px; }
            .log-sms { border-color: #28a745; }
            .log-action { border-color: #ffc107; }
            .log-error { border-color: #dc3545; }
            .log-time { font-size: 12px; color: #666; }
            .log-message { font-weight: bold; margin: 4px 0; }
            .log-details { font-size: 12px; color: #555; }
            .stats { display: flex; gap: 20px; margin: 10px 0; }
            .stat-box { background: white; padding: 10px; border-radius: 4px; text-align: center; min-width: 80px; }
        </style>
        <script>
            function refreshLogs() {
                fetch('/logs')
                    .then(response => response.json())
                    .then(data => {
                        const logsContainer = document.getElementById('logs-container');
                        logsContainer.innerHTML = '';
                        
                        data.logs.forEach(log => {
                            const logDiv = document.createElement('div');
                            logDiv.className = `log-entry log-${log.type.toLowerCase().split('_')[0]}`;
                            logDiv.innerHTML = `
                                <div class="log-time">${log.timestamp}</div>
                                <div class="log-message">${log.message}</div>
                                ${log.phone_number ? `<div class="log-details">📱 ${log.phone_number}</div>` : ''}
                                ${log.action ? `<div class="log-details">🎯 ${log.action}</div>` : ''}
                                ${log.result ? `<div class="log-details">📄 ${log.result}</div>` : ''}
                            `;
                            logsContainer.appendChild(logDiv);
                        });
                        
                        // Update stats
                        document.getElementById('total-messages').textContent = data.stats.total_messages;
                        document.getElementById('successful-actions').textContent = data.stats.successful_actions;
                        document.getElementById('errors').textContent = data.stats.errors;
                    });
            }
            
            // Auto-refresh logs every 3 seconds
            setInterval(refreshLogs, 3000);
            
            // Load logs on page load
            window.onload = refreshLogs;
        </script>
    </head>
    <body>
        <h1>🚀 SMS-to-Cursor Automation Dashboard</h1>
        <div class="status">✅ Server Running | 📱 Twilio: +12295970631 | 💻 Bridge: Active</div>
        
        <div class="stats">
            <div class="stat-box">
                <div style="font-size: 24px; color: #007acc;" id="total-messages">0</div>
                <div>Total Messages</div>
            </div>
            <div class="stat-box">
                <div style="font-size: 24px; color: #28a745;" id="successful-actions">0</div>
                <div>Successful Actions</div>
            </div>
            <div class="stat-box">
                <div style="font-size: 24px; color: #dc3545;" id="errors">0</div>
                <div>Errors</div>
            </div>
        </div>
        
        <div class="container">
            <div class="section">
                <h3>🧪 Quick Test</h3>
                <p>Test automation instantly:</p>
                <form action="/trigger" method="post">
                    <input type="text" name="message" placeholder="Create a Python hello world script" value="Create a Python hello world script">
                    <button type="submit" class="btn btn-primary">🚀 Test Now</button>
                </form>
            </div>
            
            <div class="section">
                <h3>📱 Webhook Test</h3>
                <p>Simulate SMS webhook:</p>
                <a href="/simulate_sms?message=Create a Python calculator&from=+12295970631" class="btn btn-success">📱 Simulate SMS</a>
                <br><br>
                <a href="/clear_logs" class="btn btn-danger">🗑️ Clear Logs</a>
            </div>
        </div>
        
        <div class="section logs-section">
            <h3>📋 Activity Logs <button onclick="refreshLogs()" class="btn btn-primary" style="float: right;">🔄 Refresh</button></h3>
            <div id="logs-container">
                <div class="log-entry">Loading logs...</div>
            </div>
        </div>
        
        <div class="section">
            <h3>📝 Example Commands:</h3>
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

@app.route('/trigger', methods=['POST'])
def trigger_automation():
    """Manual trigger for testing automation without SMS"""
    message = request.form.get('message', '').strip()
    
    if not message:
        add_log('ERROR', 'No message provided for trigger', action='Manual Trigger')
        return "<h2>❌ No message provided</h2><a href='/'>Go back</a>"
    
    try:
        add_log('ACTION_PERFORMED', f'Manual trigger: {message[:50]}...', action='Direct Test')
        
        # Process with Gemini
        action_data = process_with_gemini(message)
        result = perform_cursor_action(action_data)
        
        add_log('ACTION_PERFORMED', f'Action completed: {action_data.description}', 
               action=f'{action_data.action.value}', result=result[:100] + '...' if len(result) > 100 else result)
        
        return f"""
        <h2>✅ Automation Triggered Successfully!</h2>
        <p><strong>Command:</strong> {message}</p>
        <p><strong>Action:</strong> {action_data.description}</p>
        <p><strong>Result:</strong> {result}</p>
        <a href='/'>← Back to Dashboard</a>
        """
        
    except Exception as e:
        add_log('ERROR', f'Trigger error: {str(e)}', action='Manual Trigger')
        return f"""
        <h2>❌ Error</h2>
        <p>{str(e)}</p>
        <a href='/'>← Back to Dashboard</a>
        """

@app.route('/simulate_sms', methods=['GET'])
def simulate_sms():
    """Simulate receiving an SMS (for testing)"""
    message = request.args.get('message', 'Create a hello world Python script')
    from_number = request.args.get('from', '+12295970631')
    to_number = request.args.get('to', '+18777804236')
    
    try:
        add_log('SMS_RECEIVED', f'Simulated SMS: {message}', phone_number=from_number)
        
        # Process the message with Gemini
        action_data = process_with_gemini(message)
        
        # Perform the action in Cursor
        result = perform_cursor_action(action_data)
        
        add_log('ACTION_PERFORMED', f'Processed: {action_data.description}', 
               phone_number=from_number, action=f'{action_data.action.value}', result=result[:100])
        
        # Create a structured response
        sms_response = SMSResponse(
            message=f"✅ Command: {message[:30]}...\n🎯 Action: {action_data.description[:50]}...\n📄 Result: {result[:50]}...",
            success=action_data.action != ActionType.ERROR,
            action_performed=action_data.description
        )
        
        add_log('SMS_SENT', f'Response sent: {sms_response.message[:50]}...', phone_number=from_number)
        
        return f"""
        <h2>✅ SMS Simulation Complete!</h2>
        <p><strong>Received from:</strong> {from_number}</p>
        <p><strong>Message:</strong> {message}</p>
        <p><strong>Action:</strong> {action_data.description}</p>
        <p><strong>Result:</strong> {result}</p>
        <p><strong>Response sent:</strong> {sms_response.message}</p>
        <a href='/'>← Back to Dashboard</a>
        """
        
    except Exception as e:
        add_log('ERROR', f'SMS simulation error: {str(e)}', phone_number=from_number)
        return f"""
        <h2>❌ Error</h2>
        <p>{str(e)}</p>
        <a href='/'>← Back to Dashboard</a>
        """

@app.route('/logs', methods=['GET'])
def get_logs():
    """API endpoint to get activity logs as JSON"""
    stats = {
        'total_messages': len([log for log in activity_logs if log['type'] in ['SMS_RECEIVED', 'ACTION_PERFORMED']]),
        'successful_actions': len([log for log in activity_logs if log['type'] == 'ACTION_PERFORMED' and 'error' not in log['message'].lower()]),
        'errors': len([log for log in activity_logs if log['type'] == 'ERROR'])
    }
    
    return {
        'logs': list(reversed(activity_logs)),  # Most recent first
        'stats': stats
    }

@app.route('/clear_logs', methods=['GET'])
def clear_logs():
    """Clear all activity logs"""
    global activity_logs
    activity_logs = []
    add_log('ACTION_PERFORMED', 'Logs cleared', action='System')
    return """
    <h2>✅ Logs Cleared!</h2>
    <a href='/'>← Back to Dashboard</a>
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
    add_log('SMS_RECEIVED', f'Real SMS: {incoming_msg}', phone_number=from_number)
    
    try:
        # Check if this is an outbound message FROM our Twilio number
        if from_number == '+12295970631':
            print(f"🔄 Outbound message detected, auto-forwarding to automation...")
            add_log('SMS_RECEIVED', 'Outbound message auto-forwarded', phone_number=from_number)
            # This is a message we sent, treat it as automation command
            incoming_msg = incoming_msg.replace("Sent from your Twilio trial account - ", "")
            
        # Process the message with Gemini
        action_data = process_with_gemini(incoming_msg)
        print(f"🤖 Gemini processed: {action_data.action} - {action_data.description}")
        add_log('ACTION_PERFORMED', f'Gemini processed: {action_data.description}', 
               phone_number=from_number, action=f'{action_data.action.value}')
        
        # Perform the action in Cursor
        result = perform_cursor_action(action_data)
        print(f"✅ Action result: {result}")
        add_log('ACTION_PERFORMED', f'Cursor action: {result[:100]}...', 
               phone_number=from_number, result=result[:100])
        
        # Create a structured response
        sms_response = SMSResponse(
            message=f"✅ Command: {incoming_msg[:30]}...\n🎯 Action: {action_data.description[:50]}...\n📄 Result: {result[:50]}...",
            success=action_data.action != ActionType.ERROR,
            action_performed=action_data.description
        )
        
        add_log('SMS_SENT', f'Response: {sms_response.message[:100]}...', phone_number=from_number)
        
        # Send back the summary
        resp = MessagingResponse()
        msg = resp.message()
        msg.body(sms_response.to_sms_format())
        
        return str(resp)
        
    except Exception as e:
        print(f"❌ Error processing SMS: {e}")
        add_log('ERROR', f'SMS processing error: {str(e)}', phone_number=from_number)
        
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
