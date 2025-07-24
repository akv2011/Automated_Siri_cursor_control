#!/usr/bin/env python3
"""
Working SMS MCP Bridge - Model Context Protocol server for SMS-to-Cursor automation
This is the main MCP server that provides SMS processing tools to Cursor.
"""

import asyncio
import json
import logging
from typing import Any, Sequence
import httpx
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    EmbeddedResource,
    ImageContent,
    ListResourcesRequestParams,
    ListToolsRequestParams,
    ReadResourceRequestParams,
    Resource,
    TextContent,
    Tool,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sms-cursor-bridge")

# Server instance
server = Server("sms-cursor-bridge")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools for SMS processing and Cursor automation."""
    return [
        Tool(
            name="send_sms_command",
            description="Process an SMS command and send it to Cursor for execution",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The SMS message/command to process and send to Cursor"
                    },
                    "phone_number": {
                        "type": "string", 
                        "description": "The phone number that sent the SMS (optional)",
                        "default": "+14322000592"
                    }
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="get_sms_status",
            description="Get the status of the SMS-to-Cursor automation system",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls for SMS processing."""
    
    if name == "send_sms_command":
        message = arguments.get("message", "") if arguments else ""
        phone_number = arguments.get("phone_number", "+14322000592") if arguments else "+14322000592"
        
        if not message:
            return [TextContent(type="text", text="Error: No message provided")]
        
        try:
            # Send to the main SMS app for processing
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "http://localhost:5000/api/sms_challenge",
                    json={
                        "message": message,
                        "from": phone_number
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        cursor_response = result.get("cursor_response", "Command processed successfully")
                        return [TextContent(
                            type="text", 
                            text=f"✅ SMS Command Processed Successfully!\n\n"
                                 f"📱 Message: {message}\n"
                                 f"🎯 Cursor Response: {cursor_response}\n"
                                 f"📞 From: {phone_number}"
                        )]
                    else:
                        error = result.get("error", "Unknown error")
                        return [TextContent(
                            type="text",
                            text=f"❌ SMS Command Failed: {error}"
                        )]
                else:
                    return [TextContent(
                        type="text",
                        text=f"❌ HTTP Error: {response.status_code} - {response.text}"
                    )]
                    
        except httpx.TimeoutException:
            return [TextContent(
                type="text",
                text="⏱️ Timeout: SMS processing is taking longer than expected. The command may still be executing."
            )]
        except httpx.RequestError as e:
            return [TextContent(
                type="text",
                text=f"🔌 Connection Error: Cannot connect to SMS app. Is it running on port 5000?\nError: {str(e)}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"💥 Unexpected Error: {str(e)}"
            )]
    
    elif name == "get_sms_status":
        try:
            # Check if the SMS app is running
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:5000/logs")
                
                if response.status_code == 200:
                    logs_data = response.json()
                    stats = logs_data.get("stats", {})
                    recent_logs = logs_data.get("logs", [])[:5]  # Get 5 most recent logs
                    
                    status_text = f"""📊 SMS-to-Cursor System Status
                    
✅ **System Status**: Online and Running
🏗️ **Port**: 5000
📱 **Total Messages**: {stats.get('total_messages', 0)}
✅ **Successful Actions**: {stats.get('successful_actions', 0)}
❌ **Errors**: {stats.get('errors', 0)}

📋 **Recent Activity**:"""
                    
                    for log in recent_logs:
                        timestamp = log.get('timestamp', 'N/A')
                        message = log.get('message', 'N/A')
                        log_type = log.get('type', 'INFO')
                        status_text += f"\n• [{timestamp}] {log_type}: {message[:50]}..."
                    
                    return [TextContent(type="text", text=status_text)]
                else:
                    return [TextContent(
                        type="text",
                        text=f"⚠️ SMS App Status: HTTP {response.status_code} - May be starting up"
                    )]
                    
        except httpx.RequestError:
            return [TextContent(
                type="text",
                text="🔴 SMS App Status: Offline\n\nTo start the system:\n1. Run: python src/app.py\n2. Run: python src/simple_ui_bridge.py\n3. Run: ./ngrok http 5000"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Status Check Error: {str(e)}"
            )]
    
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    """Main function to run the MCP server."""
    logger.info("🚀 Starting SMS-to-Cursor MCP Bridge...")
    logger.info("📋 Available tools: send_sms_command, get_sms_status")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="sms-cursor-bridge",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
