import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SuggestedQuestions } from './SuggestedQuestions'

describe('SuggestedQuestions', () => {
  it('submits a starter research prompt', () => {
    const onSelect = vi.fn()
    render(<SuggestedQuestions onSelect={onSelect} />)

    fireEvent.click(screen.getByText('横向比较两家行业龙头'))

    expect(onSelect).toHaveBeenCalledWith(
      expect.stringContaining('贵州茅台(600519)和五粮液(000858)'),
    )
  })

  it('builds follow-up prompts from the active stock', () => {
    const onSelect = vi.fn()
    render(
      <SuggestedQuestions
        compact
        intent={{
          task_type: 'single_stock_analysis',
          stocks: [{ name: '贵州茅台', code: 'sh.600519' }],
          dimensions: ['fundamental'],
          parameters: {},
          suggested_route: 'specialist_agent',
          execution_route: 'legacy_workflow',
          confidence: 1,
          summary: '',
          source: 'deterministic_fallback',
        }}
        onSelect={onSelect}
      />,
    )

    fireEvent.click(screen.getByText('只深入分析估值'))

    expect(onSelect).toHaveBeenCalledWith(expect.stringContaining('贵州茅台(600519)'))
  })
})
