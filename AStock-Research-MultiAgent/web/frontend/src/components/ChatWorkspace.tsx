import {
  ArrowUpOutlined,
  DatabaseOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Alert, Avatar, Button, Input, Space, Spin, Tag, Typography } from 'antd'
import { useEffect, useRef, useState } from 'react'
import type { IntentAnalysis, MessageRecord, TaskRecord } from '../types'
import { MarkdownReport } from './MarkdownReport'
import { SuggestedQuestions } from './SuggestedQuestions'

interface Props {
  messages: MessageRecord[]
  task?: TaskRecord | null
  intent?: IntentAnalysis | null
  submitting?: boolean
  onSubmit: (query: string) => Promise<void>
  onCancel: () => Promise<void>
}

export function ChatWorkspace({ messages, task, intent, submitting, onSubmit, onCancel }: Props) {
  const [query, setQuery] = useState('')
  const messageScrollRef = useRef<HTMLDivElement>(null)
  const running = task?.status === 'queued' || task?.status === 'running'
  const cancelling = task?.status === 'cancelling'
  const active = running || cancelling
  const latestMessageId = messages.at(-1)?.id

  useEffect(() => {
    const container = messageScrollRef.current
    if (!container) return

    if (typeof container.scrollTo === 'function') {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' })
    } else {
      container.scrollTop = container.scrollHeight
    }
  }, [latestMessageId, task?.status])

  const send = async (value = query) => {
    const cleaned = value.trim()
    if (!cleaned || active || submitting) return
    setQuery('')
    await onSubmit(cleaned)
  }

  return (
    <main className="chat-workspace">
      <header className="workspace-header">
        <div className="workspace-heading">
          <div className="workspace-title-row">
            <span className="live-indicator" />
            <Typography.Title level={4}>智能投研工作台</Typography.Title>
            <Tag color="cyan">可追溯研究</Tag>
          </div>
          <Typography.Text type="secondary">
            多 Agent 协作 · MCP 真实数据 · 结构化意图路由
          </Typography.Text>
        </div>
        {task?.duration_seconds != null && (
          <Tag>{task.duration_seconds.toFixed(1)} 秒</Tag>
        )}
      </header>

      <div className="message-scroll" ref={messageScrollRef}>
        {messages.length === 0 ? (
          <div className="welcome-state">
            <div className="welcome-kicker"><ThunderboltOutlined /> RESEARCH COPILOT</div>
            <Typography.Title>从一个问题开始，完成一份可验证的投资研究</Typography.Title>
            <Typography.Paragraph>
              系统会识别研究意图、拆解任务并按需调度专业 Agent，数字来自工具计算，结论保留完整证据链。
            </Typography.Paragraph>
            <div className="capability-strip">
              <span><DatabaseOutlined /> 真实金融数据</span>
              <span><SafetyCertificateOutlined /> 结果可审计</span>
              <span><RobotOutlined /> 多角色协作</span>
            </div>
            <SuggestedQuestions
              intent={intent}
              disabled={active || submitting}
              onSelect={(question) => void send(question)}
            />
          </div>
        ) : (
          messages.map((message) => (
            <div className={`message-row ${message.role}`} key={message.id}>
              <Avatar
                className="message-avatar"
                icon={message.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
              />
              <div className="message-content">
                <div className="message-meta">
                  {message.role === 'user' ? '你' : 'StockScope Research'}
                </div>
                {message.role === 'assistant' ? (
                  <MarkdownReport
                    content={message.content}
                    charts={message.metadata.charts}
                    warnings={message.metadata.warnings}
                  />
                ) : (
                  <div className="user-bubble">{message.content}</div>
                )}
              </div>
            </div>
          ))
        )}

        {active && (
          <div className="running-card">
            <Spin size="small" />
            <div>
              <strong>{cancelling ? '正在终止研究任务' : '研究任务执行中'}</strong>
              <span>
                {cancelling
                  ? '正在停止 Agent 与工具调用，请稍候。'
                  : 'Agent 正在获取数据并生成分析，详情见执行轨迹。'}
              </span>
            </div>
          </div>
        )}
        {task?.status === 'failed' && (
          <Alert
            type="error"
            showIcon
            message="研究任务失败"
            description={task.error ?? '未知错误'}
          />
        )}
      </div>

      <div className="composer-wrap">
        {messages.length > 0 && (
          <SuggestedQuestions
            compact
            intent={intent}
            disabled={active || submitting}
            onSelect={(question) => void send(question)}
          />
        )}
        <div className="composer">
          <Input.TextArea
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault()
                void send()
              }
            }}
            autoSize={{ minRows: 2, maxRows: 6 }}
            placeholder="例如：比较贵州茅台(600519)与五粮液(000858)的盈利能力和估值"
            disabled={active}
          />
          {active ? (
            <Button
              className="cancel-task-button"
              danger
              shape="circle"
              size="large"
              icon={<span className="stop-square" aria-hidden="true" />}
              loading={cancelling}
              disabled={cancelling}
              aria-label={cancelling ? '正在终止任务' : '终止任务'}
              title={cancelling ? '正在终止任务' : '终止任务'}
              onClick={() => void onCancel()}
            />
          ) : (
            <Button
              type="primary"
              shape="circle"
              size="large"
              icon={<ArrowUpOutlined />}
              loading={submitting}
              disabled={!query.trim()}
              aria-label="发送消息"
              title="发送消息"
              onClick={() => void send()}
            />
          )}
        </div>
        <Typography.Text type="secondary">
          Agent 可能出错；重要投资决策请核对原始数据。
        </Typography.Text>
      </div>
    </main>
  )
}
