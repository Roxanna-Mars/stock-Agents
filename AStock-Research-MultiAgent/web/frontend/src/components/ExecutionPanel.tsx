import {
  CheckCircleFilled,
  ClockCircleOutlined,
  CloseCircleFilled,
  LoadingOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import { Collapse, Empty, Space, Tag, Timeline, Typography } from 'antd'
import { useMemo } from 'react'
import type { AgentStatus, ExecutionEvent, TaskRecord } from '../types'

const AGENT_LABELS: Record<string, string> = {
  main: 'Lead / Main',
  fundamental_agent: '基本面 Agent',
  technical_agent: '技术面 Agent',
  value_agent: '估值 Agent',
  news_agent: '新闻 Agent',
  comparison_agent: '比较 Agent',
  single_agent: 'Single Agent',
  summary_agent: '报告汇总 Agent',
  direct_tool: '直接工具查询',
}

const STATUS_META: Record<AgentStatus, { color: string; icon: React.ReactNode; label: string }> = {
  waiting: { color: 'default', icon: <ClockCircleOutlined />, label: '等待' },
  running: { color: 'processing', icon: <LoadingOutlined spin />, label: '运行中' },
  completed: { color: 'success', icon: <CheckCircleFilled />, label: '完成' },
  failed: { color: 'error', icon: <CloseCircleFilled />, label: '失败' },
  cancelled: { color: 'default', icon: <CloseCircleFilled />, label: '已取消' },
}

const TASK_STATUS_META: Record<TaskRecord['status'], { color: string; label: string }> = {
  queued: { color: 'default', label: '等待中' },
  running: { color: 'processing', label: '运行中' },
  cancelling: { color: 'warning', label: '正在终止' },
  cancelled: { color: 'default', label: '已取消' },
  completed: { color: 'success', label: '已完成' },
  failed: { color: 'error', label: '失败' },
}

interface AgentView {
  name: string
  status: AgentStatus
  duration?: number
  error?: string
}

export function ExecutionPanel({
  events,
  task,
}: {
  events: ExecutionEvent[]
  task?: TaskRecord | null
}) {
  const { agents, tools } = useMemo(() => {
    const agentMap = new Map<string, AgentView>()
    const toolEvents: ExecutionEvent[] = []
    for (const event of events) {
      if (event.type === 'workflow.planned') {
        const selected = (event.payload.selected_agents as string[] | undefined) ?? []
        const executionRoute = String(event.payload.execution_route ?? 'legacy_workflow')
        if (executionRoute === 'direct_tool') {
          agentMap.set('direct_tool', { name: 'direct_tool', status: 'waiting' })
        } else {
          agentMap.set('main', { name: 'main', status: 'running' })
          for (const name of selected) {
            const agentName = name.endsWith('_agent') ? name : `${name}_agent`
            agentMap.set(agentName, { name: agentName, status: 'waiting' })
          }
          agentMap.set('summary_agent', { name: 'summary_agent', status: 'waiting' })
        }
      }
      if (event.type.startsWith('agent.')) {
        const name = String(event.payload.agent_name ?? 'unknown_agent')
        const status = event.type === 'agent.started'
          ? 'running'
          : event.type === 'agent.failed' ? 'failed' : 'completed'
        agentMap.set(name, {
          name,
          status,
          duration: Number(event.payload.execution_time_seconds ?? 0) || undefined,
          error: event.payload.error ? String(event.payload.error) : undefined,
        })
      }
      if (event.type.startsWith('tool.')) toolEvents.push(event)
    }
    const cancelled = task?.status === 'cancelled'
      ? Array.from(agentMap.values()).map((agent) => (
        agent.status === 'waiting' || agent.status === 'running'
          ? { ...agent, status: 'cancelled' as const }
          : agent
      ))
      : Array.from(agentMap.values())
    return { agents: cancelled, tools: toolEvents }
  }, [events, task?.status])

  return (
    <section className="execution-panel">
      <div className="panel-title-row">
        <div>
          <Typography.Title level={5}>执行轨迹</Typography.Title>
          <Typography.Text type="secondary">来自运行日志与 MCP 调用</Typography.Text>
        </div>
        {task && (
          <Tag color={TASK_STATUS_META[task.status].color}>
            {TASK_STATUS_META[task.status].label}
          </Tag>
        )}
      </div>

      {agents.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="等待任务执行" />
      ) : (
        <div className="agent-grid">
          {agents.map((agent) => {
            const meta = STATUS_META[agent.status]
            return (
              <div className={`agent-status-card ${agent.status}`} key={agent.name}>
                <span className="agent-status-icon">{meta.icon}</span>
                <div className="agent-status-copy">
                  <strong>{AGENT_LABELS[agent.name] ?? agent.name}</strong>
                  <span>
                    {meta.label}
                    {agent.duration ? ` · ${agent.duration.toFixed(1)}s` : ''}
                  </span>
                  {agent.error && <small>{agent.error}</small>}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <Collapse
        ghost
        defaultActiveKey={['tools']}
        items={[
          {
            key: 'tools',
            label: <span><ToolOutlined /> 工具调用（{tools.length} 个事件）</span>,
            children: tools.length === 0 ? (
              <Typography.Text type="secondary">尚无工具调用</Typography.Text>
            ) : (
              <Timeline
                className="tool-timeline"
                items={tools.slice(-30).map((event) => {
                  const failed = event.type === 'tool.failed'
                  const running = event.type === 'tool.started'
                  return {
                    color: failed ? 'red' : running ? 'blue' : 'green',
                    content: (
                      <div className="tool-event">
                        <Space>
                          <strong>{String(event.payload.tool_name ?? 'unknown_tool')}</strong>
                          <Tag color={failed ? 'error' : running ? 'processing' : 'success'}>
                            {running ? '运行中' : failed ? '失败' : '完成'}
                          </Tag>
                        </Space>
                        <Typography.Text type="secondary">
                          {String(event.payload.agent_name ?? '')}
                          {event.payload.execution_time_seconds
                            ? ` · ${Number(event.payload.execution_time_seconds).toFixed(2)}s`
                            : ''}
                        </Typography.Text>
                        {Boolean(event.payload.output_summary) && (
                          <Typography.Paragraph ellipsis={{ rows: 2 }}>
                            {String(event.payload.output_summary)}
                          </Typography.Paragraph>
                        )}
                      </div>
                    ),
                  }
                })}
              />
            ),
          },
        ]}
      />
    </section>
  )
}
