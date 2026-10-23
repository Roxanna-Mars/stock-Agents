"""
金融分析智能体系统主程序 (Financial Analysis AI Agent System Main Program)

本文件是金融分析智能体系统的核心入口点，实现了以下主要功能：

1. 多智能体工作流管理：使用LangGraph构建并行执行的智能体工作流
2. 命令行界面：提供用户友好的交互式命令行界面
3. 自然语言处理：自动识别和提取股票代码、公司名称
4. 日志系统：完整的执行日志记录和错误处理
5. 报告生成：生成综合性的金融分析报告

工作流程：
start_node → [fundamental_analyst, technical_analyst, value_analyst] → summarizer → END
"""

# ============================================================================
# 导入必要的模块和依赖
# ============================================================================

# 在导入其他模块之前设置环境变量，抑制无用输出
import os
import sys

# 设置环境变量来抑制transformers和其他库的冗余输出
os.environ["TRANSFORMERS_VERBOSITY"] = "error"  # 只显示错误信息
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # 禁用tokenizer并行化警告
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"  # 减少CUDA相关输出
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"  # 减少内存分配信息

# 设置日志级别，抑制第三方库的INFO级别输出
import logging
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("accelerate").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

# 日志和状态管理相关导入
from src.utils.logging_config import setup_logger, SUCCESS_ICON, ERROR_ICON, WAIT_ICON
from src.utils.state_definition import AgentState
from src.utils.execution_logger import initialize_execution_logger, finalize_execution_logger

# 智能体模块导入 - 五个核心分析智能体
from src.agents.summary_agent import summary_agent      # 总结智能体：整合所有分析结果
from src.agents.value_agent import value_agent          # 估值智能体：分析股票估值水平
from src.agents.technical_agent import technical_agent  # 技术分析智能体：分析价格趋势和技术指标
from src.agents.fundamental_agent import fundamental_agent  # 基本面智能体：分析财务状况和盈利能力
from src.agents.news_agent import news_agent            # 新闻分析智能体：分析新闻情感和风险
from src.agents.comparison_agent import comparison_agent
from src.agents.single_agent import single_agent
from src.planning.query_planner import (
    VALID_ARCHITECTURES,
    plan_query,
    select_architecture_agents,
)

# LangGraph工作流框架导入
from langgraph.graph import StateGraph, END

# 环境变量和系统相关导入
from dotenv import load_dotenv
import argparse
import asyncio
import re
import time
from datetime import datetime

# ============================================================================
# 初始化和配置
# ============================================================================

# 设置日志记录器
logger = setup_logger(__name__)


AGENT_NODES = {
    "fundamental": ("fundamental_analyst", fundamental_agent),
    "technical": ("technical_analyst", technical_agent),
    "value": ("value_analyst", value_agent),
    "news": ("news_analyst", news_agent),
    "comparison": ("comparison_analyst", comparison_agent),
    "single": ("single_analyst", single_agent),
}


def build_workflow(requested_agents, architecture="react_multi_agent"):
    """Build only the branches required by the deterministic task plan."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", lambda state: state)
    workflow.add_node("summarizer", summary_agent)
    workflow.set_entry_point("start_node")

    selected_nodes = []
    for agent_key in select_architecture_agents(requested_agents, architecture):
        if agent_key not in AGENT_NODES:
            continue
        node_name, node_function = AGENT_NODES[agent_key]
        workflow.add_node(node_name, node_function)
        workflow.add_edge("start_node", node_name)
        workflow.add_edge(node_name, "summarizer")
        selected_nodes.append(node_name)

    if not selected_nodes:
        raise ValueError("Task planner did not select any analysis agent")
    workflow.add_edge("summarizer", END)
    return workflow.compile()

# 添加项目根目录到Python路径，确保模块导入正常工作
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 加载环境变量（从.env文件）
load_dotenv(override=True)

# 调试：打印关键环境变量以验证配置
logger.info(f"Environment Variables Loaded:")
logger.info(
    f"  OPENAI_COMPATIBLE_MODEL: {os.getenv('OPENAI_COMPATIBLE_MODEL', 'Not Set')}")
logger.info(
    f"  OPENAI_COMPATIBLE_BASE_URL: {os.getenv('OPENAI_COMPATIBLE_BASE_URL', 'Not Set')}")
logger.info(
    f"  OPENAI_COMPATIBLE_API_KEY: {'*' * 20 if os.getenv('OPENAI_COMPATIBLE_API_KEY') else 'Not Set'}")

# 重新设置日志记录器（确保正确配置）
logger = setup_logger(__name__)


async def main():
    """
    主函数：金融分析智能体系统的核心执行逻辑
    
    功能包括：
    1. 初始化执行日志系统
    2. 构建LangGraph工作流
    3. 处理命令行参数和用户输入
    4. 提取股票信息（代码、公司名称）
    5. 执行多智能体分析工作流
    6. 生成和保存分析报告
    7. 错误处理和日志记录
    """
    
    # 初始化执行日志系统
    execution_logger = initialize_execution_logger()
    logger.info(
        f"{SUCCESS_ICON} 执行日志系统已初始化，日志目录: {execution_logger.execution_dir}")
    main_start_time = None
    main_log_started = False

    try:
        # ============================================================================
        # 2. 实现命令行界面 
        # ============================================================================
        
        # 创建命令行参数解析器
        parser = argparse.ArgumentParser(description="Financial Agent CLI")
        parser.add_argument(
            "--command",
            type=str,
            required=False,  # 改为非必需，支持交互式输入
            help="The user query for financial analysis (e.g., '分析嘉友国际')"
        )
        parser.add_argument(
            "--architecture",
            choices=sorted(VALID_ARCHITECTURES),
            default="react_multi_agent",
            help="Architecture variant used for controlled evaluation",
        )
        args = parser.parse_args()

        # 处理用户查询输入
        if args.command:
            # 如果通过命令行参数提供查询
            user_query = args.command
        else:
            # 显示ASCII艺术开屏图像和交互式界面
            print("\n")
            print(
                "╔══════════════════════════════════════════════════════════════════════════════╗")
            print(
                "║                                                                              ║")
            print(
                "║      ███████╗██╗███╗   ██╗ █████╗ ███╗   ██╗ ██████╗██╗ █████╗ ██╗          ║")
            print(
                "║      ██╔════╝██║████╗  ██║██╔══██╗████╗  ██║██╔════╝██║██╔══██╗██║          ║")
            print(
                "║      █████╗  ██║██╔██╗ ██║███████║██╔██╗ ██║██║     ██║███████║██║          ║")
            print(
                "║      ██╔══╝  ██║██║╚██╗██║██╔══██║██║╚██╗██║██║     ██║██╔══██║██║          ║")
            print(
                "║      ██║     ██║██║ ╚████║██║  ██║██║ ╚████║╚██████╗██║██║  ██║███████╗      ║")
            print(
                "║      ╚═╝     ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝╚═╝╚═╝  ╚═╝╚══════╝      ║")
            print(
                "║                                                                              ║")
            print(
                "║                █████╗  ██████╗ ███████╗███╗   ██╗████████╗                  ║")
            print(
                "║               ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝                  ║")
            print(
                "║               ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║                     ║")
            print(
                "║               ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║                     ║")
            print(
                "║               ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║                     ║")
            print(
                "║               ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝                     ║")
            print(
                "║                                                                              ║")
            print("║                          🏦 金融分析智能体系统                              ║")
            print(
                "║                     Financial Analysis AI Agent System                      ║")
            print(
                "║                                                                              ║")
            print(
                "║    ┌─────────────────────────────────────────────────────────────────┐     ║")
            print("║    │  📊 基本面分析  │  📈 技术分析  │  💰 估值分析  │  📰 新闻分析  │  🤖 智能总结  │    ║")
            print(
                "║    └─────────────────────────────────────────────────────────────────┘     ║")
            print(
                "║                                                                              ║")
            print(
                "╚══════════════════════════════════════════════════════════════════════════════╝")
            print("\n🔹 本系统可以对A股公司进行全面分析，包括：")
            print("  • 基本面分析 - 财务状况、盈利能力和行业地位")
            print("  • 技术面分析 - 价格趋势、交易量和技术指标")
            print("  • 估值分析 - 市盈率、市净率等估值水平")
            print("  • 新闻分析 - 新闻情感分析和风险评估")
            print("\n🔹 支持多种自然语言查询方式：")
            print("  • 分析嘉友国际")
            print("  • 帮我看看比亚迪这只股票怎么样")
            print("  • 我想了解一下腾讯的投资价值")
            print("  • 603871 这个股票值得买吗？")
            print("  • 给我分析一下宁德时代的财务状况")
            print("\n🔹 您可以用任何自然语言描述您的分析需求")
            print("🔹 系统会自动识别股票名称和代码，并进行全面分析")
            print("\n💡 提示：建议使用股票代码（如 000001、600036）以获得更准确的分析结果")
            print("\n" + "─" * 78 + "\n")

            # 获取用户输入
            user_query = input("💬 请输入您的分析需求: ")

            # 确保输入不为空
            while not user_query.strip():
                print(f"{ERROR_ICON} 输入不能为空，请重新输入！")
                user_query = input("请输入您的分析需求: ")

        # 记录用户查询到执行日志
        main_start_time = time.time()
        execution_logger.log_agent_start(
            "main",
            {"user_query": user_query, "architecture": args.architecture},
        )
        main_log_started = True

        # ============================================================================
        # 3. 自然语言处理和股票信息提取
        # ============================================================================
        
        # 从查询中提取股票代码和公司名称
        stock_code = None
        company_name = None

        # 定义更精确的提取模式
        def extract_stock_info(query):
            """精确提取股票代码和公司名称"""
            stock_code = None
            company_name = None
            
            # 模式1: 包含"请帮我分析一下"的复杂查询，如"请帮我分析一下嘉友国际(603871)这只股票的投资价值如何"
            pattern1 = r'请帮我分析一下\s*([^（(]+?)\s*[（(](\d{5,6})[)）]'
            match1 = re.search(pattern1, query)
            if match1:
                company_name = match1.group(1).strip()
                stock_code = match1.group(2)
                return company_name, stock_code
            
            # 模式2: 包含"分析一下"的复杂查询，如"分析一下嘉友国际(603871)的财务状况"
            pattern2 = r'分析一下\s*([^（(]+?)\s*[（(](\d{5,6})[)）]'
            match2 = re.search(pattern2, query)
            if match2:
                company_name = match2.group(1).strip()
                stock_code = match2.group(2)
                return company_name, stock_code
            
            # 模式3: 股票代码在括号内，如"分析嘉友国际(603871)"
            pattern3 = r'分析\s*([^（(]+?)\s*[（(](\d{5,6})[)）]'
            match3 = re.search(pattern3, query)
            if match3:
                company_name = match3.group(1).strip()
                stock_code = match3.group(2)
                return company_name, stock_code
            
            # 模式4: 股票代码在括号内，如"分析(603871)嘉友国际"
            pattern4 = r'分析\s*[（(](\d{5,6})[)）]\s*([^）)]+)'
            match4 = re.search(pattern4, query)
            if match4:
                stock_code = match4.group(1)
                company_name = match4.group(2).strip()
                return company_name, stock_code
            
            # 模式5: 包含"帮我看看"的查询，如"帮我看看(000001)平安银行这只股票"
            pattern5 = r'帮我看看\s*[（(](\d{5,6})[)）]\s*([^）)]+?)(?:\s*这只|\s*这个)?\s*股票'
            match5 = re.search(pattern5, query)
            if match5:
                stock_code = match5.group(1)
                company_name = match5.group(2).strip()
                return company_name, stock_code
            
            # 模式6: 包含"我想了解一下"的查询，如"我想了解一下比亚迪(002594)的投资价值"
            pattern6 = r'我想了解一下\s*([^（(]+?)\s*[（(](\d{5,6})[)）]'
            match6 = re.search(pattern6, query)
            if match6:
                company_name = match6.group(1).strip()
                stock_code = match6.group(2)
                return company_name, stock_code
            
            # 模式7: 包含"帮我看看"的复杂查询，如"帮我看看茅台(600519)这只股票值得投资吗"
            pattern7 = r'帮我看看\s*([^（(]+?)\s*[（(](\d{5,6})[)）]'
            match7 = re.search(pattern7, query)
            if match7:
                company_name = match7.group(1).strip()
                stock_code = match7.group(2)
                return company_name, stock_code
            
            # 模式8: 直接公司名+括号格式，如"平安银行(000001)值得买吗"
            pattern8 = r'^([^（(]+?)\s*[（(](\d{5,6})[)）]'
            match8 = re.search(pattern8, query)
            if match8:
                company_name = match8.group(1).strip()
                stock_code = match8.group(2)
                return company_name, stock_code
            
            # 模式9: 包含"分析一下"的查询，如"分析一下宁德时代的财务状况"
            pattern9 = r'分析一下\s*([^0-9（）()\s]+?)(?:\s*的|\s|$)'
            match9 = re.search(pattern9, query)
            if match9:
                company_name = match9.group(1).strip()
            
            # 模式10: 包含"分析"关键词，如"分析嘉友国际"
            pattern10 = r'分析\s*([^0-9（）()\s]+)'
            match10 = re.search(pattern10, query)
            if match10 and not company_name:
                company_name = match10.group(1).strip()
            
            # 模式11: 包含"股票"关键词的查询，如"嘉友国际这只股票怎么样"
            pattern11 = r'([^0-9（）()\s]+)\s*(?:这只|这个|的)?\s*股票'
            match11 = re.search(pattern11, query)
            if match11 and not company_name:
                company_name = match11.group(1).strip()
            
            # 模式12: 包含"投资价值"的查询，如"了解一下腾讯的投资价值"
            pattern12 = r'了解一下\s*([^0-9（）()\s]+?)(?:\s*的|\s|$)'
            match12 = re.search(pattern12, query)
            if match12 and not company_name:
                company_name = match12.group(1).strip()
            
            # 模式13: 包含"给我分析一下"的查询，如"给我分析一下宁德时代的财务状况"
            pattern13 = r'给我分析一下\s*([^0-9（）()\s]+?)(?:\s*的|\s|$)'
            match13 = re.search(pattern13, query)
            if match13 and not company_name:
                company_name = match13.group(1).strip()
            
            # 模式14: 包含"的"字的查询，如"嘉友国际的财务表现如何"
            pattern14 = r'([^0-9（）()\s]+?)\s*的\s*(?:财务表现|盈利能力|现金流状况|资产负债情况|技术面|股价走势|技术指标|技术面表现|估值水平|市盈率|市净率|估值|投资风险|风险因素|风险评估|投资价值|股票|基本面情况|基本面|财务状况)'
            match14 = re.search(pattern14, query)
            if match14 and not company_name:
                company_name = match14.group(1).strip()
            
            # 模式15: 包含"在...中"的查询（无"的"字），如"比亚迪在新能源汽车行业的表现"
            pattern15 = r'([^0-9（）()\s]+?)\s*在\s*[^0-9（）()\s]*\s*中'
            match15 = re.search(pattern15, query)
            if match15 and not company_name:
                company_name = match15.group(1).strip()
            
            # 模式16: 包含"在...中"的查询，如"嘉友国际在行业中的地位"
            pattern16 = r'([^0-9（）()\s]+?)\s*在\s*[^0-9（）()\s]*\s*中\s*的'
            match16 = re.search(pattern16, query)
            if match16 and not company_name:
                company_name = match16.group(1).strip()
            
            # 模式17: 包含"面临"的查询，如"比亚迪面临的主要风险"
            pattern17 = r'([^0-9（）()\s]+?)\s*面临'
            match17 = re.search(pattern17, query)
            if match17 and not company_name:
                company_name = match17.group(1).strip()
            
            # 模式18: 直接包含5-6位数字股票代码
            pattern18 = r'\b(\d{5,6})\b'
            match18 = re.search(pattern18, query)
            if match18:
                stock_code = match18.group(1)
            
            # 模式19: 包含"值得买"的查询，如"603871 这个股票值得买吗"
            pattern19 = r'(\d{5,6})\s*(?:这个|这只)?\s*股票\s*值得买'
            match19 = re.search(pattern19, query)
            if match19 and not stock_code:
                stock_code = match19.group(1)
            
            # 模式20: 包含"这个股票最近表现"的查询，如"603871这个股票最近表现怎么样，值得投资吗"
            pattern20 = r'(\d{5,6})\s*这个\s*股票\s*最近表现'
            match20 = re.search(pattern20, query)
            if match20 and not stock_code:
                stock_code = match20.group(1)
            
            # 清理公司名称（移除常见的无意义词汇）
            if company_name:
                # 移除常见的无意义词汇
                stop_words = ['的', '这个', '这只', '一下', '看看', '了解', '分析', '帮我', '我想', '给我', '财务状况', '投资价值', '基本面情况', '这只股票', '这个股票']
                for word in stop_words:
                    company_name = company_name.replace(word, '').strip()
                
                # 如果公司名称太短（少于2个字符），可能是误匹配
                if len(company_name) < 2:
                    company_name = None
            
            return company_name, stock_code

        # 执行提取
        company_name, stock_code = extract_stock_info(user_query)

        # 使用确定性规划器补充多股票识别和按需Agent选择。
        task_plan = plan_query(user_query)
        planned_stocks = task_plan["stocks"]
        if planned_stocks:
            company_name = planned_stocks[0].get("company_name") or company_name
            stock_code = planned_stocks[0]["stock_code"].split(".")[-1]

        # 记录提取结果
        logger.info(f"从查询中提取 - 公司名称: {company_name}, 股票代码: {stock_code}")

        # ============================================================================
        # 4. 时间信息处理
        # ============================================================================
        
        # 获取当前时间信息
        current_datetime = datetime.now()
        current_date_cn = current_datetime.strftime("%Y年%m月%d日")
        current_date_en = current_datetime.strftime("%Y-%m-%d")
        current_weekday_cn = ["星期一", "星期二", "星期三", "星期四",
                              "星期五", "星期六", "星期日"][current_datetime.weekday()]
        current_time = current_datetime.strftime("%H:%M:%S")

        # 格式化完整的时间信息
        current_time_info = f"{current_date_cn} ({current_date_en}) {current_weekday_cn} {current_time}"

        logger.info(f"当前时间: {current_time_info}")

        # ============================================================================
        # 5. 准备初始状态数据
        # ============================================================================
        
        # 准备初始状态
        initial_data = {
            "query": user_query,
            "current_date": current_date_en,
            "current_date_cn": current_date_cn,
            "current_time": current_time,
            "current_weekday_cn": current_weekday_cn,
            "current_time_info": current_time_info,
            "analysis_timestamp": current_datetime.isoformat(),
            "task_plan": task_plan,
            "task_type": task_plan["task_type"],
            "architecture": args.architecture,
            "stocks": planned_stocks,
        }
        
        # 添加公司名称（如果提取到）
        if company_name:
            initial_data["company_name"] = company_name
            
        # 添加股票代码（如果提取到），并添加交易所前缀
        if stock_code:
            # 根据股票代码规则添加交易所前缀
            if stock_code.startswith('6'):
                initial_data["stock_code"] = f"sh.{stock_code}"  # 上海证券交易所
            elif stock_code.startswith('0') or stock_code.startswith('3'):
                initial_data["stock_code"] = f"sz.{stock_code}"  # 深圳证券交易所
            else:
                initial_data["stock_code"] = stock_code

        # 创建LangGraph工作流的初始状态
        initial_state = AgentState(
            messages=[],  # Langchain约定：消息列表
            data=initial_data,  # 应用特定数据，包含提取的信息
            metadata={},  # 其他运行时特定信息
            evidence=[],
        )

        # 查询解析完成后再构建工作流，避免专项任务无条件运行所有Agent。
        app = build_workflow(task_plan["requested_agents"], args.architecture)
        logger.info(
            "Task plan: type=%s agents=%s stocks=%s",
            task_plan["task_type"],
            select_architecture_agents(task_plan["requested_agents"], args.architecture),
            planned_stocks,
        )

        # ============================================================================
        # 6. 执行工作流
        # ============================================================================
        
        # 显示分析开始信息
        print(f"\n{WAIT_ICON} 正在开始对 '{user_query}' 进行金融分析...")
        if company_name:
            print(f"{WAIT_ICON} 分析公司: {company_name}")
        if stock_code:
            print(f"{WAIT_ICON} 股票代码: {stock_code}")
        logger.info(
            f"Starting financial analysis workflow for query: '{user_query}'")

        # 显示分析阶段提示
        print(f"\n{WAIT_ICON} 正在执行基本面分析...")
        print(f"{WAIT_ICON} 正在执行技术面分析...")
        print(f"{WAIT_ICON} 正在执行估值分析...")
        print(f"{WAIT_ICON} 正在执行新闻分析...")
        print(f"{WAIT_ICON} 这可能需要几分钟时间，请耐心等待...\n")

        # 调用工作流 - 这是阻塞调用，会等待所有智能体完成
        final_state = await app.ainvoke(initial_state)
        print(f"{SUCCESS_ICON} 分析完成！")
        logger.info("Workflow execution completed successfully")

        # ============================================================================
        # 7. 结果处理和报告生成
        # ============================================================================
        
        # 提取并打印最终报告
        if final_state and final_state.get("data") and "final_report" in final_state["data"]:
            print("\n--- 最终分析报告 (Final Analysis Report) ---\n")
            # print(final_state["data"]["final_report"])

            # 显示报告文件路径（如果可用）
            if "report_path" in final_state["data"]:
                print(
                    f"\n{SUCCESS_ICON} 报告已保存到: {final_state['data']['report_path']}")
                logger.info(
                    f"Report saved to: {final_state['data']['report_path']}")

                # 记录最终报告到执行日志
                execution_logger.log_final_report(
                    final_state["data"]["final_report"],
                    final_state["data"]["report_path"]
                )
        else:
            print(f"\n{ERROR_ICON} 错误: 无法从工作流中检索最终报告。")
            logger.error(
                "Could not retrieve the final report from the workflow")
            print("调试信息 - 最终状态内容:", final_state)

        report_generated = bool(
            final_state
            and final_state.get("data")
            and final_state["data"].get("final_report")
        )
        main_error = None if report_generated else "Workflow did not produce a final report"

        execution_logger.log_agent_complete(
            "main",
            {
                "report_generated": report_generated,
                "report_path": (
                    final_state.get("data", {}).get("report_path")
                    if final_state
                    else None
                ),
            },
            time.time() - main_start_time,
            success=report_generated,
            error=main_error,
        )

        # 完成执行日志记录
        finalize_execution_logger(success=report_generated, error=main_error)
        status_icon = SUCCESS_ICON if report_generated else ERROR_ICON
        print(f"{status_icon} 执行日志已保存到: {execution_logger.execution_dir}")

    except Exception as e:
        # ============================================================================
        # 8. 错误处理
        # ============================================================================
        
        print(f"\n{ERROR_ICON} 工作流执行期间发生错误: {e}")
        logger.error(f"Error during workflow execution: {e}", exc_info=True)

        # 记录错误并完成执行日志
        if main_log_started and main_start_time is not None:
            execution_logger.log_agent_complete(
                "main",
                {},
                time.time() - main_start_time,
                success=False,
                error=str(e),
            )
        finalize_execution_logger(success=False, error=str(e))
        print(f"{ERROR_ICON} 错误日志已保存到: {execution_logger.execution_dir}")


# ============================================================================
# 程序入口点
# ============================================================================

if __name__ == "__main__":
    # 使用asyncio运行主函数
    asyncio.run(main())
