import { FileTextOutlined } from '@ant-design/icons'
import { Alert, Tag } from 'antd'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChartSpec } from '../types'
import { FinancialChart } from './FinancialChart'

interface Props {
  content: string
  charts?: ChartSpec[]
  warnings?: string[]
}

export function MarkdownReport({ content, charts = [], warnings = [] }: Props) {
  return (
    <article className="report-card">
      <div className="report-heading">
        <span><FileTextOutlined /> 投资研究报告</span>
        <Tag color="cyan">Markdown</Tag>
      </div>
      {warnings.length > 0 && (
        <Alert
          className="report-warning"
          type="warning"
          showIcon
          message="报告包含不完整分析"
          description={warnings.join('；')}
        />
      )}
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
      {charts.length > 0 && (
        <div className="chart-grid">
          {charts.map((chart) => <FinancialChart key={chart.id} chart={chart} />)}
        </div>
      )}
    </article>
  )
}
