"""
MCP Install Link Generator for SMS Cursor Bridge
"""
import json
import base64

def generate_mcp_install_link():
    # MCP Server configuration
    config = {
        "sms-cursor-bridge": {
            "command": "python",
            "args": [
                "c:\\Users\\arunk\\Automated_Siri_cursor_control\\sms_mcp_bridge.py"
            ]
        }
    }
    
    # Convert to JSON string
    config_json = json.dumps(config)
    
    # Base64 encode the configuration
    config_b64 = base64.b64encode(config_json.encode('utf-8')).decode('utf-8')
    
    # Generate the install link
    server_name = "sms-cursor-bridge"
    install_link = f"cursor://anysphere.cursor-deeplink/mcp/install?name={server_name}&config={config_b64}"
    
    print("🚀 SMS Cursor Bridge MCP Server Install Link Generator")
    print("=" * 60)
    print()
    print("📋 Server Configuration:")
    print(json.dumps(config, indent=2))
    print()
    print("🔗 Install Link:")
    print(install_link)
    print()
    print("📝 Web Link (for sharing):")
    web_link = f"https://cursor.com/mcp/install?name={server_name}&config={config_b64}"
    print(web_link)
    print()
    print("🎯 Installation Instructions:")
    print("1. Copy the install link above")
    print("2. Paste it into your browser or Cursor")
    print("3. Cursor will prompt to install the MCP server")
    print("4. Accept the installation")
    print("5. The SMS Cursor Bridge will be available in Cursor!")
    print()
    print("💡 Alternative: Add to mcp.json manually:")
    print("Add this to your Cursor mcp.json configuration file:")
    print(json.dumps(config, indent=2))
    
    return install_link, config

if __name__ == "__main__":
    generate_mcp_install_link()
