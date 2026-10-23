"""ReAct agent for explicit multi-stock comparisons."""

from __future__ import annotations

import os
import time
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.tools.mcp_client import get_mcp_tools
from src.utils.execution_logger import get_execution_logger
from src.utils.logging_config import ERROR_ICON, SUCCESS_ICON, WAIT_ICON, setup_logger
from src.utils.react_config import TOOL_USAGE_RULES, get_react_invoke_config
from src.utils.state_definition import AgentState
from src.utils.token_usage import collect_token_usage
from src.utils.tool_result_utils import inspect_tool_results
from src.utils.trace_context import bind_agent_trace
from src.utils.evidence import extract_evidence
from src.utils.agent_runtime import invoke_with_timeout


load_dotenv(override=True)
logger = setup_logger(__name__)


async def comparison_agent(state: AgentState) -> AgentState:
    execution_logger = get_execution_logger()
    agent_name = "comparison_agent"
    current_data = state.get("data", {})
    current_messages = state.get("messages", [])
    current_metadata = state.get("metadata", {})
    query = current_data.get("query", "")
    stocks = current_data.get("stocks", [])
    started = time.time()
    execution_logger.log_agent_start(
        agent_name,
        {"user_query": query, "stocks": stocks},
    )

    try:
        api_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        model_name = os.getenv("OPENAI_COMPATIBLE_MODEL")
        if not all([api_key, base_url, model_name]):
            raise ValueError("Missing OpenAI environment variables")
        if len(stocks) < 2:
            raise ValueError("Multi-stock comparison requires at least two stock codes")

        tools = await invoke_with_timeout(get_mcp_tools(), agent_name)
        if not tools:
            raise RuntimeError("No MCP tools available")
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.2,
            max_tokens=6000,
        )
        agent = create_react_agent(llm, tools)
        stock_text = "、".join(
            f"{stock.get('company_name') or '未知公司'}（{stock['stock_code']}）"
            for stock in stocks
        )
        prompt = f"""请对以下股票进行横向比较：{stock_text}

原始问题：{query}
当前时间：{current_data.get('current_time_info', '未知时间')}

要求：
1. 对每只股票使用相同口径和时间范围获取真实数据。
2. 按用户要求比较基本面、估值、技术走势或风险，不得遗漏任何股票。
3. 使用表格展示关键指标，并明确数据日期和缺失项。
4. 发现数据冲突时分别保留证据，不得自行编造或强行统一。
5. 给出相对结论和适用投资者，不作无依据的绝对推荐。

{TOOL_USAGE_RULES}"""
        invoke_started = time.time()
        with bind_agent_trace(agent_name):
            response = await invoke_with_timeout(
                agent.ainvoke(
                    {"messages": [HumanMessage(content=prompt)]},
                    config=get_react_invoke_config(),
                ),
                agent_name,
            )
        invoke_seconds = time.time() - invoke_started
        response_messages = response.get("messages", [])
        ai_messages = [message for message in response_messages if isinstance(message, AIMessage)]
        output = ai_messages[-1].content if ai_messages else "No comparison generated."
        tool_stats = inspect_tool_results(
            response_messages,
            ignored_tools={"get_market_analysis_timeframe"},
        )
        token_usage = collect_token_usage(response_messages)
        evidence_records = extract_evidence(response_messages, agent_name)
        execution_logger.log_evidence_records(evidence_records)
        success = tool_stats["succeeded"] > 0
        error = None if success else "No required data tools completed successfully."

        execution_logger.log_llm_interaction(
            agent_name=agent_name,
            interaction_type="react_agent",
            input_messages=[{"role": "user", "content": prompt}],
            output_content=output,
            model_config={
                "model": model_name,
                "temperature": 0.2,
                "max_tokens": 6000,
                "api_base": base_url,
            },
            execution_time=invoke_seconds,
            token_usage=token_usage,
        )
        current_data["comparison_analysis"] = output
        if error:
            current_data["comparison_analysis_error"] = error
        current_metadata["comparison_agent_executed"] = True
        total_seconds = time.time() - started
        execution_logger.log_agent_complete(
            agent_name,
            {
                "comparison_analysis_length": len(output),
                "analysis_preview": output[:500],
                "llm_execution_time": invoke_seconds,
                "total_execution_time": total_seconds,
                "tool_results": tool_stats,
                "token_usage": token_usage,
                "evidence_count": len(evidence_records),
            },
            total_seconds,
            success,
            error,
        )
        logger.info(f"{SUCCESS_ICON} ComparisonAgent completed")
        return {
            "data": current_data,
            "messages": current_messages + [{"role": "assistant", "content": "多股比较已完成"}],
            "metadata": current_metadata,
            "evidence": evidence_records,
        }
    except Exception as exc:
        message = str(exc)
        logger.error(f"{ERROR_ICON} ComparisonAgent failed: {message}", exc_info=True)
        current_data["comparison_analysis"] = f"多股比较过程中出现错误: {message}"
        current_data["comparison_analysis_error"] = message
        execution_logger.log_agent_complete(
            agent_name,
            current_data,
            time.time() - started,
            False,
            message,
        )
        return {"data": current_data, "messages": current_messages, "metadata": current_metadata}
