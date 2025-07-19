import anyio
import click
import json
import mcp.types as types
from mcp.server.lowlevel import Server
from datetime import datetime
import os
import tempfile


async def create_file_with_cursor(
    file_path: str,
    instruction: str,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Create a file using Cursor's AI with the given instruction."""
    try:
        # Create a detailed instruction for Cursor's AI
        cursor_instruction = f"""
SMS-to-Cursor Automation Request:
====================================

TASK: {instruction}
TARGET FILE: {file_path}
TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

INSTRUCTIONS FOR CURSOR AI:
Please create the file '{file_path}' according to this request: {instruction}

Make the file complete, functional, and well-commented.
Use best practices for the file type based on the extension.
"""
        
        # Create the target file with a placeholder
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(f"# TODO: {instruction}\n")
            f.write(f"# File created by SMS-to-Cursor automation at {datetime.now()}\n")
            f.write("# Please use Cursor AI to complete this file\n\n")
        
        return [types.TextContent(
            type="text", 
            text=f"✅ File '{file_path}' created! Cursor AI instruction: {cursor_instruction}"
        )]
        
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Error creating file: {str(e)}"
        )]


async def sms_command_handler(
    command: str,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle SMS commands sent through the MCP bridge."""
    try:
        # Parse the command (expecting JSON format)
        cmd_data = json.loads(command)
        action = cmd_data.get('action')
        file_path = cmd_data.get('file_path')
        instruction = cmd_data.get('instruction')
        
        if action == 'create_file' and file_path and instruction:
            return await create_file_with_cursor(file_path, instruction)
        else:
            return [types.TextContent(
                type="text",
                text=f"Unknown command format. Expected: {{'action': 'create_file', 'file_path': '...', 'instruction': '...'}}"
            )]
            
    except json.JSONDecodeError:
        # Treat as simple text command
        return [types.TextContent(
            type="text",
            text=f"📱 SMS Command received: {command}\n🎯 Use this with Cursor AI to execute the command!"
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"❌ Error processing SMS command: {str(e)}"
        )]


@click.command()
@click.option("--transport", type=str, default="stdio", help="Transport to use")
@click.option("--port", type=int, default=8000, help="Port to run on (SSE only)")
def main(transport: str, port: int):
    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route
        import uvicorn

        app = Starlette()
        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await main_loop(streams[0], streams[1])

        async def handle_messages(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await main_loop(streams[0], streams[1])

        app.add_route("/sse", handle_sse)
        app.add_route("/messages", handle_messages)
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # Default stdio transport
        async def run_stdio():
            from mcp.server.stdio import stdio_server
            async with stdio_server() as streams:
                await main_loop(streams[0], streams[1])

        anyio.run(run_stdio)


async def main_loop(read_stream, write_stream):
    server = Server("sms-cursor-bridge")

    # Register the SMS command handler tool
    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="sms_command",
                description="Process SMS commands for Cursor automation",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "SMS command to process (can be JSON or plain text)"
                        }
                    },
                    "required": ["command"]
                }
            ),
            types.Tool(
                name="create_cursor_file",
                description="Create a file with Cursor AI instructions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path for the new file"
                        },
                        "instruction": {
                            "type": "string",
                            "description": "Instruction for what the file should contain"
                        }
                    },
                    "required": ["file_path", "instruction"]
                }
            )
        ]

    # Handle tool calls
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name == "sms_command":
            return await sms_command_handler(arguments["command"])
        elif name == "create_cursor_file":
            return await create_file_with_cursor(
                arguments["file_path"], 
                arguments["instruction"]
            )
        else:
            raise ValueError(f"Unknown tool: {name}")

    # Run the server
    async with anyio.create_task_group() as tg:
        tg.start_soon(server.run, read_stream, write_stream, None, tg)


if __name__ == "__main__":
    main()
