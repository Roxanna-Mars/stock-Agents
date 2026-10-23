"""
MCP服务器配置模块 - 包含连接A股MCP服务器的配置信息
"""

import sys
from pathlib import Path


# 根据当前配置文件的位置定位工作区，避免依赖特定机器上的绝对路径。
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
MCP_SERVER_PATH = WORKSPACE_ROOT / "MCP" / "mcp_server.py"

SERVER_CONFIGS = {
    "a_share_mcp_v2": {
        # 使用当前主程序所在虚拟环境的 Python，确保主程序和 MCP 服务
        # 共享同一套已安装依赖。
        "command": sys.executable,
        "args": [
            str(MCP_SERVER_PATH),
        ],
        "transport": "stdio",
    }
}
