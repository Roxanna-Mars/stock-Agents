import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ExecutionPanel } from './ExecutionPanel'
import type { ExecutionEvent } from '../types'

describe('ExecutionPanel', () => {
  it('derives agent and tool status from runtime events', () => {
    const events: ExecutionEvent[] = [
      {
        id: 1,
        type: 'workflow.planned',
        created_at: '2026-10-26T00:00:00Z',
        payload: { selected_agents: ['fundamental'] },
      },
      {
        id: 2,
        type: 'agent.completed',
        created_at: '2026-10-26T00:00:02Z',
        payload: { agent_name: 'fundamental_agent', execution_time_seconds: 2 },
      },
      {
        id: 3,
        type: 'tool.completed',
        created_at: '2026-10-26T00:00:01Z',
        payload: {
          agent_name: 'fundamental_agent',
          tool_name: 'get_profit_data',
          output_summary: 'net profit: 100',
        },
      },
    ]

    render(<ExecutionPanel events={events} />)

    expect(screen.getByText('基本面 Agent')).toBeInTheDocument()
    expect(screen.getByText('get_profit_data')).toBeInTheDocument()
    expect(screen.getByText('net profit: 100')).toBeInTheDocument()
  })

  it('shows a direct tool without phantom research or summary agents', () => {
    const events: ExecutionEvent[] = [
      {
        id: 1,
        type: 'workflow.planned',
        created_at: '2026-10-27T00:00:00Z',
        payload: {
          execution_route: 'direct_tool',
          selected_agents: [],
          selected_tool: 'get_stock_basic_info',
        },
      },
      {
        id: 2,
        type: 'agent.completed',
        created_at: '2026-10-27T00:00:01Z',
        payload: { agent_name: 'direct_tool', execution_time_seconds: 1 },
      },
      {
        id: 3,
        type: 'tool.completed',
        created_at: '2026-10-27T00:00:01Z',
        payload: { agent_name: 'direct_tool', tool_name: 'get_stock_basic_info' },
      },
    ]

    render(<ExecutionPanel events={events} />)

    expect(screen.getByText('直接工具查询')).toBeInTheDocument()
    expect(screen.queryByText('Lead / Main')).not.toBeInTheDocument()
    expect(screen.queryByText('报告汇总 Agent')).not.toBeInTheDocument()
  })
})
