"""
Simple Cursor Bridge Server
Injects SMS messages directly into Cursor's chat input field
"""

import pyautogui
import time
import psutil
import win32gui
import win32con
from flask import Flask, request, jsonify
import json
from datetime import datetime
import logging
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def find_cursor_window():
    """Find Cursor window using win32gui"""
    cursor_windows = []
    
    def enum_windows_callback(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd)
            if 'cursor' in window_text.lower() or 'code' in window_text.lower():
                windows.append((hwnd, window_text))
        return True
    
    win32gui.EnumWindows(enum_windows_callback, cursor_windows)
    return cursor_windows

def activate_cursor_window():
    """Activate Cursor window and find chat input"""
    try:
        cursor_windows = find_cursor_window()
        
        if not cursor_windows:
            logger.error("No Cursor window found")
            return False
        
        # Use the first Cursor window found
        hwnd, window_text = cursor_windows[0]
        logger.info(f"Found Cursor window: {window_text}")
        
        # Bring window to foreground
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        
        # Wait for window to activate
        time.sleep(0.5)
        
        return True
        
    except Exception as e:
        logger.error(f"Error activating Cursor window: {e}")
        return False

def send_to_cursor_chat(message):
    """Send a message directly to Cursor's chat input field"""
    try:
        # Step 1: Activate Cursor window
        if not activate_cursor_window():
            return {"success": False, "error": "Could not find or activate Cursor window"}
        
        # Step 2: Try to find and click the chat input area
        # First, try to open a new chat (Ctrl+Shift+L is common for AI chat)
        pyautogui.hotkey('ctrl', 'shift', 'l')
        time.sleep(1)
        
        # Alternative: Try Ctrl+L for chat
        pyautogui.hotkey('ctrl', 'l')
        time.sleep(1)
        
        # Step 3: Type the message
        pyautogui.typewrite(message, interval=0.02)
        time.sleep(0.5)
        
        # Step 4: Press Enter to send (comment out if you want user to review first)
        # pyautogui.press('enter')
        
        logger.info(f"Successfully injected message: {message[:50]}...")
        
        return {
            "success": True, 
            "message": f"Message injected into Cursor: {message}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error injecting message: {e}")
        return {"success": False, "error": str(e)}

def inject_sms_to_cursor(sms_body, from_number):
    """Process SMS and inject into Cursor"""
    # Format the message for Cursor's AI
    cursor_message = f"{sms_body}"
    
    # Send to Cursor chat
    result = send_to_cursor_chat(cursor_message)
    
    # Log the interaction
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "sms_from": from_number,
        "sms_body": sms_body,
        "cursor_message": cursor_message,
        "result": result
    }
    
    # Save log
    with open("sms_cursor_log.json", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    return result

@app.route('/')
def home():
    return """
    <h1>Simple Cursor Bridge Server</h1>
    <p>🚀 Server is running!</p>
    <p>📱 Send POST requests to /inject with SMS messages</p>
    <p>💻 Messages will appear in Cursor's chat interface</p>
    
    <h3>Test Interface:</h3>
    <form action="/inject" method="post">
        <input type="text" name="message" placeholder="Enter message to inject..." style="width: 400px; padding: 5px;">
        <button type="submit">Inject to Cursor</button>
    </form>
    """

@app.route('/inject', methods=['POST'])
def inject_message():
    """Endpoint to inject messages into Cursor"""
    try:
        # Get message from form data or JSON
        if request.is_json:
            data = request.get_json()
            message = data.get('message', '')
        else:
            message = request.form.get('message', '')
        
        if not message:
            return jsonify({"success": False, "error": "No message provided"}), 400
        
        # Inject the message
        result = send_to_cursor_chat(message)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Error in inject endpoint: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/sms', methods=['POST'])
def sms_webhook():
    """Webhook endpoint for SMS messages from Twilio"""
    try:
        # Get the SMS message
        sms_body = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '')
        
        if not sms_body:
            return jsonify({"success": False, "error": "No SMS body"}), 400
        
        logger.info(f"Received SMS from {from_number}: {sms_body}")
        
        # Inject the SMS message into Cursor
        result = inject_sms_to_cursor(sms_body, from_number)
        
        # Return Twilio-compatible response
        if result.get("success", True):  # Default to success for string results
            response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>✅ SMS injected into Cursor: {sms_body[:50]}...</Message>
</Response>"""
            return response_xml, 200, {'Content-Type': 'text/xml'}
        else:
            response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>❌ Failed to inject SMS: {result.get('error', 'Unknown error')}</Message>
</Response>"""
            return response_xml, 200, {'Content-Type': 'text/xml'}
            
    except Exception as e:
        logger.error(f"Error in SMS webhook: {e}")
        response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>❌ Server error: {str(e)[:100]}</Message>
</Response>"""
        return response_xml, 200, {'Content-Type': 'text/xml'}

@app.route('/test')
def test_cursor():
    """Test endpoint to check if Cursor is accessible"""
    try:
        cursor_windows = find_cursor_window()
        
        if cursor_windows:
            window_info = [{"handle": hwnd, "title": title} for hwnd, title in cursor_windows]
            return jsonify({
                "success": True, 
                "cursor_found": True,
                "windows": window_info
            })
        else:
            return jsonify({
                "success": True,
                "cursor_found": False,
                "message": "No Cursor windows found"
            })
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    # Install required packages if not available
    try:
        import pyautogui
        import win32gui
        import win32con
        import psutil
        from flask import Flask
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("Please install: pip install pyautogui pywin32 psutil flask")
        exit(1)
    
    # Set PyAutoGUI settings
    pyautogui.PAUSE = 0.1
    pyautogui.FAILSAFE = True
    
    print("🚀 Simple Cursor Bridge Server starting...")
    print("📱 SMS webhook endpoint: /sms")
    print("💻 Manual inject endpoint: /inject") 
    print("🧪 Test endpoint: /test")
    print("🏠 Home page: http://localhost:5001")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
