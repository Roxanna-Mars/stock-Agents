import {
  BarChartOutlined,
  CalculatorOutlined,
  FileSearchOutlined,
  LineChartOutlined,
  ReadOutlined,
  SafetyCertificateOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'
import type { IntentAnalysis } from '../types'

interface SuggestedQuestion {
  category: string
  title: string
  prompt: string
  icon: ReactNode
}

const STARTER_QUESTIONS: SuggestedQuestion[] = [
  {
    category: '综合研究',
    title: '判断一家公司是否值得长期关注',
    prompt: '分析贵州茅台(600519)的投资价值，覆盖基本面、估值、技术面和近期新闻',
    icon: <FileSearchOutlined />,
  },
  {
    category: '公司对比',
    title: '横向比较两家行业龙头',
    prompt: '比较贵州茅台(600519)和五粮液(000858)的盈利能力、成长性和估值',
    icon: <SwapOutlined />,
  },
  {
    category: '估值分析',
    title: '当前估值是否处于合理区间',
    prompt: '分析宁德时代(300750)当前的PE、PB和历史估值水平',
    icon: <CalculatorOutlined />,
  },
  {
    category: '基本面',
    title: '拆解盈利质量与现金流',
    prompt: '分析招商银行(600036)的营收、利润、ROE、资产质量和现金流',
    icon: <BarChartOutlined />,
  },
  {
    category: '技术面',
    title: '观察趋势与关键价格位置',
    prompt: '分析比亚迪(002594)近期走势、均线、MACD、RSI和支撑压力位',
    icon: <LineChartOutlined />,
  },
  {
    category: '风险追踪',
    title: '梳理近期事件与潜在风险',
    prompt: '分析中国平安(601318)近期新闻、公告和需要关注的风险因素',
    icon: <SafetyCertificateOutlined />,
  },
]

function stockLabel(intent?: IntentAnalysis | null): string {
  const stock = intent?.stocks?.[0]
  if (!stock) return '这只股票'
  const code = stock.code?.split('.').at(-1)
  if (stock.name && code) return `${stock.name}(${code})`
  return stock.name ?? code ?? '这只股票'
}

function followUpQuestions(intent?: IntentAnalysis | null): SuggestedQuestion[] {
  const stock = stockLabel(intent)
  return [
    {
      category: '继续深挖',
      title: '只深入分析估值',
      prompt: `基于刚才的结论，只深入分析${stock}的估值水平和安全边际`,
      icon: <CalculatorOutlined />,
    },
    {
      category: '风险检查',
      title: '有哪些风险需要跟踪',
      prompt: `${stock}未来需要持续跟踪哪些经营、估值和事件风险？`,
      icon: <SafetyCertificateOutlined />,
    },
    {
      category: '事实查询',
      title: '查看最新价格与估值指标',
      prompt: `查询${stock}的最新价格、市盈率和市净率`,
      icon: <LineChartOutlined />,
    },
    {
      category: '形成结论',
      title: '整理成简明研究摘要',
      prompt: `将${stock}刚才的分析整理成一份包含结论、依据和观察清单的简明报告`,
      icon: <ReadOutlined />,
    },
  ]
}

export function SuggestedQuestions({
  intent,
  compact = false,
  disabled = false,
  onSelect,
}: {
  intent?: IntentAnalysis | null
  compact?: boolean
  disabled?: boolean
  onSelect: (question: string) => void
}) {
  const questions = compact ? followUpQuestions(intent) : STARTER_QUESTIONS

  if (compact) {
    return (
      <section className="follow-up-suggestions" aria-label="推荐追问">
        <div className="follow-up-label">
          <ReadOutlined /> 推荐追问
        </div>
        <div className="follow-up-list">
          {questions.map((question) => (
            <button
              type="button"
              key={question.prompt}
              disabled={disabled}
              onClick={() => onSelect(question.prompt)}
              title={question.prompt}
            >
              {question.icon}
              <span>{question.title}</span>
            </button>
          ))}
        </div>
      </section>
    )
  }

  return (
    <section className="suggestion-grid" aria-label="推荐问题">
      {questions.map((question) => (
        <button
          type="button"
          key={question.prompt}
          disabled={disabled}
          onClick={() => onSelect(question.prompt)}
        >
          <span className="suggestion-icon">{question.icon}</span>
          <span className="suggestion-copy">
            <small>{question.category}</small>
            <strong>{question.title}</strong>
            <span>{question.prompt}</span>
          </span>
        </button>
      ))}
    </section>
  )
}
