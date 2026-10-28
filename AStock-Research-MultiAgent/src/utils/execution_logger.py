"""
执行日志系统 - 为每次运行创建独立的日志文件夹
记录所有agent与LLM的交互信息，包括输入、输出、执行时间等
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import uuid
from contextvars import ContextVar
from typing import Callable


EventSink = Callable[[Dict[str, Any]], None]


class ExecutionLogger:
    """执行日志记录器"""

    def __init__(self, base_log_dir: str = "logs", event_sink: EventSink | None = None):
        """
        初始化执行日志记录器

        Args:
            base_log_dir: 基础日志目录
        """
        self.base_log_dir = Path(base_log_dir)
        self._event_sink = event_sink
        self.execution_id = self._generate_execution_id()
        self.execution_dir = self._create_execution_dir()
        self.start_time = time.time()

        # 记录执行开始信息
        self._log_execution_start()

    def emit_event(self, event_type: str, payload: Dict[str, Any] | None = None):
        """Emit a compact runtime event without making UI delivery a failure point."""
        event = {
            "type": event_type,
            "execution_id": self.execution_id,
            "timestamp": datetime.now().isoformat(),
            "payload": payload or {},
        }
        if self._event_sink is not None:
            try:
                self._event_sink(event)
            except Exception:
                pass
        return event

    def _generate_execution_id(self) -> str:
        """生成唯一的执行ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{timestamp}_{unique_id}"

    def _create_execution_dir(self) -> Path:
        """创建本次执行的日志目录"""
        execution_dir = self.base_log_dir / self.execution_id
        execution_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (execution_dir / "agents").mkdir(exist_ok=True)
        (execution_dir / "llm_interactions").mkdir(exist_ok=True)
        (execution_dir / "tools").mkdir(exist_ok=True)
        (execution_dir / "evidence").mkdir(exist_ok=True)
        (execution_dir / "reports").mkdir(exist_ok=True)

        return execution_dir

    def _log_execution_start(self):
        """记录执行开始信息"""
        start_info = {
            "execution_id": self.execution_id,
            "start_time": datetime.now().isoformat(),
            "start_timestamp": self.start_time,
            "environment": {
                "python_version": os.sys.version,
                "working_directory": os.getcwd(),
                "environment_variables": {
                    "OPENAI_COMPATIBLE_MODEL": os.getenv("OPENAI_COMPATIBLE_MODEL", "Not Set"),
                    "OPENAI_COMPATIBLE_BASE_URL": os.getenv("OPENAI_COMPATIBLE_BASE_URL", "Not Set"),
                    "OPENAI_COMPATIBLE_API_KEY": "***" if os.getenv("OPENAI_COMPATIBLE_API_KEY") else "Not Set"
                }
            }
        }

        self._save_json(start_info, "execution_info.json")
        self.emit_event("workflow.started", {"status": "running"})

    def log_agent_start(self, agent_name: str, input_data: Dict[str, Any]):
        """记录agent开始执行"""
        agent_log = {
            "agent_name": agent_name,
            "start_time": datetime.now().isoformat(),
            "start_timestamp": time.time(),
            "input_data": input_data,
            "status": "started"
        }

        agent_file = f"agents/{agent_name}_execution.json"
        self._save_json(agent_log, agent_file)
        self.emit_event(
            "agent.started",
            {"agent_name": agent_name, "status": "running"},
        )

        return agent_log

    def log_agent_complete(self, agent_name: str, output_data: Dict[str, Any],
                           execution_time: float, success: bool = True, error: str = None):
        """记录agent执行完成"""
        # 读取现有的agent日志
        agent_file = f"agents/{agent_name}_execution.json"
        agent_log = self._load_json(agent_file) or {}

        # 更新完成信息
        agent_log.update({
            "end_time": datetime.now().isoformat(),
            "end_timestamp": time.time(),
            "execution_time_seconds": execution_time,
            "output_data": output_data,
            "success": success,
            "error": error,
            "status": "completed" if success else "failed"
        })

        self._save_json(agent_log, agent_file)
        self.emit_event(
            "agent.completed" if success else "agent.failed",
            {
                "agent_name": agent_name,
                "status": "completed" if success else "failed",
                "execution_time_seconds": execution_time,
                "success": success,
                "error": error,
            },
        )
        return agent_log

    def log_llm_interaction(self, agent_name: str, interaction_type: str,
                            input_messages: List[Dict], output_content: str,
                            model_config: Dict[str, Any], execution_time: float,
                            token_usage: Optional[Dict] = None):
        """记录LLM交互详情"""
        interaction_id = str(uuid.uuid4())[:8]
        interaction_log = {
            "interaction_id": interaction_id,
            "agent_name": agent_name,
            # "react_agent", "summary", etc.
            "interaction_type": interaction_type,
            "timestamp": datetime.now().isoformat(),
            "model_config": model_config,
            "input": {
                "messages": input_messages,
                "message_count": len(input_messages),
                "total_input_length": sum(len(str(msg.get("content", ""))) for msg in input_messages)
            },
            "output": {
                "content": output_content,
                "content_length": len(output_content)
            },
            "performance": {
                "execution_time_seconds": execution_time,
                "token_usage": token_usage
            }
        }

        # 保存到LLM交互目录
        interaction_file = f"llm_interactions/{agent_name}_{interaction_type}_{interaction_id}.json"
        self._save_json(interaction_log, interaction_file)

        # 同时保存输入输出的纯文本版本，方便查看
        self._save_text(
            f"=== INPUT MESSAGES ===\n{json.dumps(input_messages, ensure_ascii=False, indent=2)}\n\n"
            f"=== OUTPUT CONTENT ===\n{output_content}",
            f"llm_interactions/{agent_name}_{interaction_type}_{interaction_id}.txt"
        )

        self.emit_event(
            "llm.completed",
            {
                "agent_name": agent_name,
                "interaction_type": interaction_type,
                "execution_time_seconds": execution_time,
                "output_length": len(output_content),
                "token_usage": token_usage or {},
            },
        )

        return interaction_log

    def log_tool_start(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: Dict,
        *,
        call_id: str | None = None,
    ):
        """Emit the actual tool start before the MCP invocation begins."""
        return self.emit_event(
            "tool.started",
            {
                "call_id": call_id,
                "agent_name": agent_name,
                "tool_name": tool_name,
                "input": tool_input,
                "status": "running",
            },
        )

    def log_tool_usage(self, agent_name: str, tool_name: str, tool_input: Dict,
                       tool_output: Any, execution_time: float, success: bool = True,
                       error: str = None, *, call_id: str = None,
                       queue_wait_seconds: float = 0.0,
                       duplicate_call: bool = False,
                       cache_hit: bool = False,
                       error_type: str = None,
                       input_fingerprint: str = None):
        """记录工具使用情况"""
        tool_log = {
            "call_id": call_id,
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent_name,
            "tool_name": tool_name,
            "input": tool_input,
            "input_fingerprint": input_fingerprint,
            "output": str(tool_output),
            "output_length": len(str(tool_output)),
            "queue_wait_seconds": queue_wait_seconds,
            "execution_time_seconds": execution_time,
            "duplicate_call": duplicate_call,
            "cache_hit": cache_hit,
            "success": success,
            "error_type": error_type,
            "error": error,
        }

        # 追加到工具使用日志文件
        tools_file = f"tools/{agent_name}_tools.jsonl"
        self._append_jsonl(tool_log, tools_file)

        self.emit_event(
            "tool.completed" if success else "tool.failed",
            {
                "call_id": call_id,
                "agent_name": agent_name,
                "tool_name": tool_name,
                "status": "completed" if success else "failed",
                "success": success,
                "error": error,
                "error_type": error_type,
                "cache_hit": cache_hit,
                "duplicate_call": duplicate_call,
                "queue_wait_seconds": queue_wait_seconds,
                "execution_time_seconds": execution_time,
                "output_summary": str(tool_output)[:500],
            },
        )

        return tool_log

    def log_final_report(self, report_content: str, report_path: str):
        """记录最终生成的报告"""
        report_log = {
            "timestamp": datetime.now().isoformat(),
            "report_path": report_path,
            "report_length": len(report_content),
            "report_preview": report_content
        }

        # 保存报告日志
        self._save_json(report_log, "reports/final_report_info.json")

        # 保存报告副本
        self._save_text(report_content, "reports/final_report.md")
        self.emit_event(
            "report.completed",
            {
                "report_path": report_path,
                "report_length": len(report_content),
            },
        )

        return report_log

    def log_evidence_records(self, records: List[Dict[str, Any]]):
        """Persist compact evidence records used by the summary agent."""
        for record in records:
            self._append_jsonl(record, "evidence/evidence.jsonl")

    def finalize_execution(self, success: bool = True, error: str = None):
        """完成执行日志记录"""
        end_time = time.time()
        total_execution_time = end_time - self.start_time

        # 读取执行信息
        execution_info = self._load_json("execution_info.json") or {}

        # 更新完成信息
        execution_info.update({
            "end_time": datetime.now().isoformat(),
            "end_timestamp": end_time,
            "total_execution_time_seconds": total_execution_time,
            "success": success,
            "error": error,
            "status": "completed" if success else "failed"
        })

        # 生成执行摘要
        summary = self._generate_execution_summary()
        execution_info["summary"] = summary

        self._save_json(execution_info, "execution_info.json")

        # 生成可读的摘要报告
        self._generate_readable_summary(execution_info)
        self.emit_event(
            "workflow.completed" if success else "workflow.failed",
            {
                "status": "completed" if success else "failed",
                "success": success,
                "error": error,
                "total_execution_time_seconds": total_execution_time,
            },
        )

        return execution_info

    def _generate_execution_summary(self) -> Dict[str, Any]:
        """生成执行摘要"""
        summary = {
            "agents_executed": [],
            "llm_interactions_count": 0,
            "tools_used_count": 0,
            "total_files_created": 0
        }

        # 统计agent执行情况
        agents_dir = self.execution_dir / "agents"
        if agents_dir.exists():
            for agent_file in agents_dir.glob("*_execution.json"):
                agent_data = self._load_json(f"agents/{agent_file.name}")
                if agent_data:
                    summary["agents_executed"].append({
                        "name": agent_data.get("agent_name"),
                        "success": agent_data.get("success", False),
                        "execution_time": agent_data.get("execution_time_seconds", 0)
                    })

        # 统计LLM交互次数
        llm_dir = self.execution_dir / "llm_interactions"
        if llm_dir.exists():
            summary["llm_interactions_count"] = len(
                list(llm_dir.glob("*.json")))

        # 统计工具使用次数
        tools_dir = self.execution_dir / "tools"
        if tools_dir.exists():
            for tool_file in tools_dir.glob("*.jsonl"):
                with open(tool_file, 'r', encoding='utf-8') as f:
                    summary["tools_used_count"] += len(f.readlines())

        # 统计创建的文件数量
        summary["total_files_created"] = len(
            list(self.execution_dir.rglob("*")))

        return summary

    def _generate_readable_summary(self, execution_info: Dict[str, Any]):
        """生成可读的摘要报告"""
        summary_text = f"""
# 执行摘要报告

## 基本信息
- 执行ID: {execution_info['execution_id']}
- 开始时间: {execution_info['start_time']}
- 结束时间: {execution_info.get('end_time', 'N/A')}
- 总执行时间: {execution_info.get('total_execution_time_seconds', 0):.2f} 秒
- 执行状态: {'成功' if execution_info.get('success', False) else '失败'}

## 环境信息
- 模型: {execution_info['environment']['environment_variables']['OPENAI_COMPATIBLE_MODEL']}
- API地址: {execution_info['environment']['environment_variables']['OPENAI_COMPATIBLE_BASE_URL']}

## 执行统计
- 执行的Agent数量: {len(execution_info.get('summary', {}).get('agents_executed', []))}
- LLM交互次数: {execution_info.get('summary', {}).get('llm_interactions_count', 0)}
- 工具使用次数: {execution_info.get('summary', {}).get('tools_used_count', 0)}
- 创建文件数量: {execution_info.get('summary', {}).get('total_files_created', 0)}

## Agent执行详情
"""

        for agent in execution_info.get('summary', {}).get('agents_executed', []):
            status = '✅ 成功' if agent.get('success') else '❌ 失败'
            summary_text += f"- {agent.get('name', 'Unknown')}: {status} (耗时: {agent.get('execution_time', 0):.2f}s)\n"

        if execution_info.get('error'):
            summary_text += f"\n## 错误信息\n{execution_info['error']}\n"

        summary_text += f"\n## 日志文件位置\n{self.execution_dir}\n"

        self._save_text(summary_text, "EXECUTION_SUMMARY.md")

    def _save_json(self, data: Dict[str, Any], filename: str):
        """保存JSON数据"""
        file_path = self.execution_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_json(self, filename: str) -> Optional[Dict[str, Any]]:
        """加载JSON数据"""
        file_path = self.execution_dir / filename
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _append_jsonl(self, data: Dict[str, Any], filename: str):
        """追加JSONL数据"""
        file_path = self.execution_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

    def _save_text(self, content: str, filename: str):
        """保存文本内容"""
        file_path = self.execution_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)


# 全局执行日志记录器实例
_execution_logger: ContextVar[Optional[ExecutionLogger]] = ContextVar(
    "execution_logger",
    default=None,
)


def get_execution_logger() -> ExecutionLogger:
    """获取全局执行日志记录器"""
    execution_logger = _execution_logger.get()
    if execution_logger is None:
        execution_logger = ExecutionLogger()
        _execution_logger.set(execution_logger)
    return execution_logger


def get_active_execution_logger() -> Optional[ExecutionLogger]:
    """Return the current logger without creating an unrelated execution."""
    return _execution_logger.get()


def initialize_execution_logger(
    base_log_dir: str = "logs",
    event_sink: EventSink | None = None,
) -> ExecutionLogger:
    """初始化执行日志记录器"""
    execution_logger = ExecutionLogger(base_log_dir, event_sink=event_sink)
    _execution_logger.set(execution_logger)
    return execution_logger


def finalize_execution_logger(success: bool = True, error: str = None):
    """完成执行日志记录"""
    execution_logger = _execution_logger.get()
    if execution_logger:
        execution_logger.finalize_execution(success, error)
        _execution_logger.set(None)
