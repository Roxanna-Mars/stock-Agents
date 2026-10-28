import { Card, Empty } from 'antd'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ChartSpec } from '../types'

export function FinancialChart({ chart }: { chart: ChartSpec }) {
  return (
    <Card size="small" className="financial-chart" title={chart.title}>
      {chart.points.length === 0 ? (
        <Empty description="暂无可验证图表数据" />
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chart.points} margin={{ top: 12, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#e8edf3" strokeDasharray="4 4" />
            <XAxis dataKey="label" tick={{ fill: '#6c788a', fontSize: 12 }} />
            <YAxis tick={{ fill: '#6c788a', fontSize: 12 }} width={64} />
            <Tooltip formatter={(value) => [`${value}${chart.unit ?? ''}`, chart.title]} />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#177d72"
              strokeWidth={2.5}
              dot={{ r: 3, fill: '#177d72' }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  )
}
