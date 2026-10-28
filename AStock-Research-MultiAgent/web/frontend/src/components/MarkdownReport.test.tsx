import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MarkdownReport } from './MarkdownReport'

describe('MarkdownReport', () => {
  it('renders headings, GFM tables and warnings', () => {
    render(
      <MarkdownReport
        content={'# 贵州茅台研究\n\n| 指标 | 数值 |\n|---|---|\n| ROE | 30% |'}
        warnings={['新闻数据缺失']}
      />,
    )

    expect(screen.getByRole('heading', { name: '贵州茅台研究' })).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('新闻数据缺失')).toBeInTheDocument()
  })
})
