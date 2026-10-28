import {
  DeleteOutlined,
  LineChartOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import { Button, Empty, List, Popconfirm, Tooltip, Typography } from 'antd'
import dayjs from 'dayjs'
import type { SessionSummary } from '../types'

interface Props {
  sessions: SessionSummary[]
  selectedId?: string
  loading?: boolean
  onSelect: (id: string) => void
  onCreate: () => void
  onDelete: (id: string) => void
}

export function SessionSidebar({
  sessions,
  selectedId,
  loading,
  onSelect,
  onCreate,
  onDelete,
}: Props) {
  return (
    <aside className="session-sidebar">
      <div className="brand-block">
        <div className="brand-mark"><LineChartOutlined /></div>
        <div>
          <Typography.Title level={4}>StockScope</Typography.Title>
          <Typography.Text>AI 投研工作台</Typography.Text>
        </div>
      </div>
      <Button
        className="new-session-button"
        type="primary"
        icon={<PlusOutlined />}
        block
        onClick={onCreate}
      >
        新建研究
      </Button>
      <div className="sidebar-section-label">历史会话</div>
      <div className="session-list-scroll">
        {sessions.length === 0 && !loading ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无会话" />
        ) : (
          <List
            loading={loading}
            dataSource={sessions}
            renderItem={(session) => (
              <List.Item
                className={`session-item ${selectedId === session.id ? 'selected' : ''}`}
                onClick={() => onSelect(session.id)}
                actions={[
                  <Popconfirm
                    key="delete"
                    title="删除此会话？"
                    description="消息和执行记录将一并删除。"
                    onConfirm={(event) => {
                      event?.stopPropagation()
                      onDelete(session.id)
                    }}
                    onCancel={(event) => event?.stopPropagation()}
                  >
                    <Tooltip title="删除">
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </Tooltip>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={<span>{session.title}</span>}
                  description={
                    <span>
                      {dayjs(session.updated_at).format('MM-DD HH:mm')}
                      {session.last_message ? ` · ${session.last_message.slice(0, 22)}` : ''}
                    </span>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>
      <div className="sidebar-footnote">研究结果不构成投资建议</div>
    </aside>
  )
}
