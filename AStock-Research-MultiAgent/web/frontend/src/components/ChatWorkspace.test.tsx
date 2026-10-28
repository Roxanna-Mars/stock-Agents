import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ChatWorkspace } from './ChatWorkspace'

describe('ChatWorkspace task controls', () => {
  it('replaces the send arrow with a stop control while a task is running', () => {
    const onCancel = vi.fn(async () => undefined)

    render(
      <ChatWorkspace
        messages={[]}
        task={{
          id: 'task-1',
          session_id: 'session-1',
          query: '分析贵州茅台',
          status: 'running',
          architecture: 'react_multi_agent',
          warnings: [],
          created_at: '2026-10-28T00:00:00Z',
        }}
        submitting={false}
        onSubmit={vi.fn(async () => undefined)}
        onCancel={onCancel}
      />,
    )

    expect(screen.queryByLabelText('发送消息')).not.toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('终止任务'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
