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
import os
from google import genai
from google.genai import types
import subprocess
import json
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
    """Perform the specified action in Cursor via MCP bridge"""
    action = action_data.action
    command = action_data.command
    file_path = action_data.file_path
    
    if action == ActionType.CREATE_FILE and file_path:
        # Send command to MCP bridge for Cursor integration
        try:
            # Prepare data for MCP bridge
            mcp_command = {
                "action": "create_file",
                "file_path": file_path,
                "instruction": command
            }
            
            # Save command to a special file that MCP can pick up
            mcp_file = f"mcp_command_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(mcp_file, 'w') as f:
                json.dump(mcp_command, f, indent=2)
            
            # Also create the target file with instruction
            with open(file_path, 'w') as f:
                f.write(f"# SMS Command: {command}\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# Please use Cursor AI to complete this file based on the command above\n\n")
            
            # Open the file in Cursor
            execute_cursor_command('open_file', file_path)
            
            return f"Created MCP command file and opened {file_path} in Cursor for AI completion"
        except Exception as e:
            return f"Error with MCP bridge: {str(e)}"
    elif action == ActionType.RUN_CODE:
        # Execute code in terminal
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout[:200] if result.stdout else "No output"
        return f"Code executed. Output: {output}..."
    
    elif action == ActionType.SEARCH_CODE:
        # Search for code in workspace
        try:
            result = subprocess.run(f'findstr /r /s "{command}" *.py *.js *.ts', shell=True, capture_output=True, text=True)
            output = result.stdout[:200] if result.stdout else "No matches found"
            return f"Search completed: {output}..."
        except Exception as e:
            return f"Search error: {str(e)}"
    
    elif action == ActionType.OPEN_FILE and file_path:
        # Open file in Cursor
        cursor_result = execute_cursor_command('open_file', file_path)
        return f"Opened file: {file_path}"
    
    elif action == ActionType.EXECUTE_COMMAND and command:
        # Execute terminal command
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            output = result.stdout[:200] if result.stdout else "No output"
            return f"Command executed: {output}..."
        except Exception as e:
            return f"Command error: {str(e)}"
    
    elif action == ActionType.ERROR:
        return f"Error: {action_data.description}"
    
    else:
        return f"Performed action: {action_data.description}"

@app.route('/')
def home():
    return """
    <h1>SMS-to-Cursor Automation</h1>
    <p>🚀 Server is running!</p>
    <p>📱 Send SMS to your Twilio number to control Cursor</p>
    <p>🔗 Webhook endpoint: <code>/sms</code></p>
    <p>💻 Ready to process commands via SMS!</p>
    """

@app.route('/sms', methods=['POST'])
def sms_webhook():
    # Get the incoming message
    incoming_msg = request.values.get('Body', '').strip()
    
    try:
        # Process the message with Gemini
        action_data = process_with_gemini(incoming_msg)
        
        # Perform the action in Cursor
        result = perform_cursor_action(action_data)
        
        # Create a structured response
        sms_response = SMSResponse(
            message=f"SMS: {incoming_msg[:40]}...\nAction: {action_data.description}\nResult: {result[:80]}...",
            success=action_data.action != ActionType.ERROR,
            action_performed=action_data.description
        )
        
        # Send back the summary
        resp = MessagingResponse()
        msg = resp.message()
        msg.body(sms_response.to_sms_format())
        
        return str(resp)
        
    except Exception as e:
        # Error handling with structured response
        error_response = SMSResponse(
            message=f"System error: {str(e)[:100]}",
            success=False
        )
        
        resp = MessagingResponse()
        msg = resp.message()
        msg.body(error_response.to_sms_format())
        return str(resp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)