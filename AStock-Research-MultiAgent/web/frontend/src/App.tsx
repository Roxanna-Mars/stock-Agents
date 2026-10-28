import {
  HistoryOutlined,
  MenuFoldOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons'
import { Button, ConfigProvider, Drawer, Grid, message, Spin } from 'antd'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { ChatWorkspace } from './components/ChatWorkspace'
import { ExecutionPanel } from './components/ExecutionPanel'
import { IntentPanel } from './components/IntentPanel'
import { SessionSidebar } from './components/SessionSidebar'
import type {
  ExecutionEvent,
  IntentAnalysis,
  SessionDetail,
  SessionSummary,
  TaskRecord,
} from './types'

const EVENT_TYPES = [
  'task.started',
  'task.cancellation_requested',
  'task.cancelled',
  'dialogue.state.updated',
  'dialogue.result.recorded',
  'intent.completed',
  'workflow.started',
  'workflow.planned',
  'agent.started',
  'agent.completed',
  'agent.failed',
  'tool.started',
  'tool.completed',
  'tool.failed',
  'llm.completed',
  'report.completed',
  'workflow.completed',
  'workflow.failed',
  'workflow.cancelled',
  'task.completed',
  'task.failed',
]

function App() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [session, setSession] = useState<SessionDetail | null>(null)
  const [task, setTask] = useState<TaskRecord | null>(null)
  const [events, setEvents] = useState<ExecutionEvent[]>([])
  const [intent, setIntent] = useState<IntentAnalysis | null>(null)
  const [loadingSessions, setLoadingSessions] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [leftOpen, setLeftOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const screens = Grid.useBreakpoint()
  const isCompact = !screens.lg

  const refreshSessions = useCallback(async () => {
    const rows = await api.listSessions()
    setSessions(rows)
    return rows
  }, [])

  const refreshTaskAndSession = useCallback(async (taskId: string, sessionId: string) => {
    const [nextTask, nextSession] = await Promise.all([
      api.getTask(taskId),
      api.getSession(sessionId),
    ])
    setTask(nextTask)
    setIntent(nextTask.intent ?? null)
    setSession(nextSession)
    await refreshSessions()
  }, [refreshSessions])

  const connectEvents = useCallback((taskId: string, sessionId: string, eventsPath?: string) => {
    eventSourceRef.current?.close()
    setEvents([])
    const source = new EventSource(
      api.eventUrl(eventsPath ?? `/api/chat/${taskId}/events`),
    )
    eventSourceRef.current = source

    const handle = (raw: MessageEvent<string>) => {
      const event = JSON.parse(raw.data) as ExecutionEvent
      setEvents((current) => current.some((item) => item.id === event.id)
        ? current
        : [...current, event])
      if (event.type === 'intent.completed') {
        setIntent(event.payload as unknown as IntentAnalysis)
      }
      if (
        event.type === 'task.completed'
        || event.type === 'task.failed'
        || event.type === 'task.cancelled'
      ) {
        source.close()
        void refreshTaskAndSession(taskId, sessionId)
      } else if (
        event.type.startsWith('agent.')
        || event.type === 'task.started'
        || event.type === 'task.cancellation_requested'
      ) {
        void api.getTask(taskId).then(setTask)
      }
    }
    EVENT_TYPES.forEach((eventType) => source.addEventListener(eventType, handle as EventListener))
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) source.close()
    }
  }, [refreshTaskAndSession])

  const selectSession = useCallback(async (sessionId: string) => {
    eventSourceRef.current?.close()
    setLeftOpen(false)
    const detail = await api.getSession(sessionId)
    setSession(detail)
    const latestTask = detail.tasks.at(-1) ?? null
    setTask(latestTask)
    setIntent(latestTask?.intent ?? null)
    setEvents([])
    if (latestTask) connectEvents(latestTask.id, sessionId)
  }, [connectEvents])

  useEffect(() => {
    void refreshSessions()
      .then((rows) => rows[0] && selectSession(rows[0].id))
      .catch((error: Error) => message.error(error.message))
      .finally(() => setLoadingSessions(false))
    return () => eventSourceRef.current?.close()
  }, [refreshSessions, selectSession])

  const createSession = async () => {
    try {
      const created = await api.createSession()
      await refreshSessions()
      await selectSession(created.id)
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const deleteSession = async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId)
      if (session?.id === sessionId) {
        eventSourceRef.current?.close()
        setSession(null)
        setTask(null)
        setEvents([])
        setIntent(null)
      }
      const rows = await refreshSessions()
      if (!session || session.id === sessionId) {
        if (rows[0]) await selectSession(rows[0].id)
      }
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  const submit = async (query: string) => {
    setSubmitting(true)
    try {
      const accepted = await api.submitChat(query, session?.id)
      const [nextTask, nextSession] = await Promise.all([
        api.getTask(accepted.task_id),
        api.getSession(accepted.session_id),
      ])
      setTask(nextTask)
      setSession(nextSession)
      setIntent(null)
      connectEvents(accepted.task_id, accepted.session_id, accepted.events_url)
      await refreshSessions()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const cancelCurrentTask = async () => {
    if (!task || !['queued', 'running'].includes(task.status)) return
    const taskId = task.id
    setTask((current) => current?.id === taskId
      ? { ...current, status: 'cancelling' }
      : current)
    try {
      const nextTask = await api.cancelTask(taskId)
      setTask(nextTask)
    } catch (error) {
      message.error((error as Error).message)
      void api.getTask(taskId).then(setTask)
    }
  }

  const sidebar = (
    <SessionSidebar
      sessions={sessions}
      selectedId={session?.id}
      loading={loadingSessions}
      onSelect={(id) => void selectSession(id)}
      onCreate={() => void createSession()}
      onDelete={(id) => void deleteSession(id)}
    />
  )

  const insights = (
    <aside className="insight-sidebar">
      <IntentPanel intent={intent} />
      <ExecutionPanel events={events} task={task} />
    </aside>
  )

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#177d72',
          borderRadius: 10,
          colorText: '#172234',
          fontFamily: "Inter, 'PingFang SC', 'Microsoft YaHei', sans-serif",
        },
      }}
    >
      <div className="app-shell">
        {!isCompact && sidebar}
        <div className="mobile-actions">
          <Button icon={<HistoryOutlined />} onClick={() => setLeftOpen(true)}>会话</Button>
          <Button icon={<NodeIndexOutlined />} onClick={() => setRightOpen(true)}>执行</Button>
        </div>
        {loadingSessions && !session ? (
          <div className="initial-loader"><Spin size="large" /></div>
        ) : (
          <ChatWorkspace
            messages={session?.messages ?? []}
            task={task}
            intent={intent}
            submitting={submitting}
            onSubmit={submit}
            onCancel={cancelCurrentTask}
          />
        )}
        {!isCompact && insights}
      </div>
      <Drawer
        className="mobile-sidebar-drawer"
        placement="left"
        width={290}
        open={leftOpen}
        closeIcon={<MenuFoldOutlined />}
        onClose={() => setLeftOpen(false)}
      >
        {sidebar}
      </Drawer>
      <Drawer
        title="研究执行详情"
        placement="right"
        width={380}
        open={rightOpen}
        onClose={() => setRightOpen(false)}
      >
        {insights}
      </Drawer>
    </ConfigProvider>
  )
}

export default App
