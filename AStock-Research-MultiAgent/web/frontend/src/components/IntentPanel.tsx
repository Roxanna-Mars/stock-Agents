import { AimOutlined, BranchesOutlined } from '@ant-design/icons'
import { Collapse, Descriptions, Progress, Space, Tag, Typography } from 'antd'
import type { IntentAnalysis } from '../types'

const TASK_LABELS: Record<string, string> = {
  fact_query: '事实查询',
  financial_calculation: '财务计算',
  single_stock_analysis: '单股分析',
  multi_stock_comparison: '多股比较',
  comprehensive_research: '综合投研',
}

const ROUTE_LABELS: Record<string, string> = {
  direct_tool: '直接工具',
  specialist_agent: '专业 Agent',
  multi_agent: '多 Agent 工作流',
}

const CHANGE_LABELS: Record<string, string> = {
  new: '新任务',
  continue: '继续',
  refine: '细化',
  switch: '切换',
  cancel: '取消',
  resume: '恢复',
}

export function IntentPanel({ intent }: { intent?: IntentAnalysis | null }) {
  return (
    <Collapse
      ghost
      defaultActiveKey={['intent']}
      items={[
        {
          key: 'intent',
          label: <span><AimOutlined /> 意图识别</span>,
          children: intent ? (
            <div className="intent-content">
              <Descriptions column={1} size="small" colon={false}>
                <Descriptions.Item label="任务类型">
                  <Tag color="geekblue">{TASK_LABELS[intent.task_type] ?? intent.task_type}</Tag>
                </Descriptions.Item>
                {intent.intent_change && (
                  <Descriptions.Item label="意图变化">
                    <Tag color="purple">
                      {CHANGE_LABELS[intent.intent_change] ?? intent.intent_change}
                    </Tag>
                    {intent.dialogue_state_version !== undefined && (
                      <Typography.Text type="secondary">
                        状态 v{intent.dialogue_state_version}
                      </Typography.Text>
                    )}
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="建议路由">
                  <Space size={4}>
                    <BranchesOutlined />
                    {ROUTE_LABELS[intent.suggested_route] ?? intent.suggested_route}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="实际执行">
                  {intent.execution_route === 'direct_tool'
                    ? '单 MCP 工具（跳过 Agent）'
                    : intent.execution_route === 'none'
                      ? '无需执行（澄清/取消）'
                      : '原 LangGraph 工作流'}
                </Descriptions.Item>
                <Descriptions.Item label="股票">
                  <Space wrap size={4}>
                    {intent.stocks.length === 0 ? (
                      <Typography.Text type="secondary">未识别</Typography.Text>
                    ) : intent.stocks.map((stock, index) => (
                      <Tag key={`${stock.code}-${index}`}>
                        {stock.name ?? '股票'} {stock.code ?? ''}
                      </Tag>
                    ))}
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="研究维度">
                  <Space wrap size={4}>
                    {intent.dimensions.map((dimension) => (
                      <Tag color="cyan" key={dimension}>{dimension}</Tag>
                    ))}
                  </Space>
                </Descriptions.Item>
                {intent.selected_agents && intent.selected_agents.length > 0 && (
                  <Descriptions.Item label="实际 Agent">
                    <Space wrap size={4}>
                      {intent.selected_agents.map((agent) => (
                        <Tag color="green" key={agent}>{agent}</Tag>
                      ))}
                    </Space>
                  </Descriptions.Item>
                )}
                {intent.requires_clarification && intent.clarification_question && (
                  <Descriptions.Item label="需要澄清">
                    <Typography.Text type="warning">
                      {intent.clarification_question}
                    </Typography.Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
              <div className="confidence-row">
                <Typography.Text type="secondary">置信度</Typography.Text>
                <Progress
                  percent={Math.round(intent.confidence * 100)}
                  size="small"
                  strokeColor="#177d72"
                />
              </div>
              <Typography.Paragraph className="intent-summary" type="secondary">
                {intent.summary}
              </Typography.Paragraph>
              {intent.fallback_reason && (
                <Typography.Text type="warning">{intent.fallback_reason}</Typography.Text>
              )}
            </div>
          ) : (
            <Typography.Text type="secondary">提交任务后显示结构化识别结果</Typography.Text>
          ),
        },
      ]}
    />
  )
}
