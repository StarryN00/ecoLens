import React from 'react';
import { Card, Descriptions, Row, Col, Statistic, Progress, Typography } from 'antd';
import type { Task, TaskResults, Nest } from '../../types/task';
import { getStatusTag } from './taskUtils';
import ReportGenerator from '../ReportGenerator';

interface Props {
  task: Task;
  results: TaskResults | null;
  nests: Nest[];
  loading: boolean;
}

const { Text } = Typography;

const TaskOverview: React.FC<Props> = ({ task, results, nests, loading }) => {
  const isActive = task.status === 'processing' || task.status === 'uploading';

  return (
    <div className="eco-page">
      <Card className="eco-panel" title="任务档案" loading={loading}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="任务名称">{task.task_name}</Descriptions.Item>
          <Descriptions.Item label="任务ID">{task.id}</Descriptions.Item>
          <Descriptions.Item label="所属区域" span={2}>
            {task.region_path || '未分配'}
          </Descriptions.Item>
          <Descriptions.Item label="巡检区域说明">{task.area_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="操作员">{task.operator || '-'}</Descriptions.Item>
          <Descriptions.Item label="地块面积">
            {task.plot_area_mu != null ? `${task.plot_area_mu} 亩` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="林业局小班号">
            {task.forestry_sub_compartment || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="状态">{getStatusTag(task.status)}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(task.created_at).toLocaleString()}
          </Descriptions.Item>
          {task.completed_at && (
            <Descriptions.Item label="完成时间">
              {new Date(task.completed_at).toLocaleString()}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Card className="eco-panel" title="检测统计" loading={loading}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="图片总数" value={task.total_images || 0} />
          </Col>
          <Col span={6}>
            <Statistic title="已处理" value={task.processed_images || 0} />
          </Col>
          <Col span={6}>
            <Progress
              percent={task.total_images ? Math.round((task.processed_images / task.total_images) * 100) : 0}
              status={task.status === 'completed' ? 'success' : 'active'}
              format={(percent) => `${percent}%`}
            />
            {isActive && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                推理进行中，每 4 秒自动刷新
              </Text>
            )}
          </Col>
          <Col span={6}>
            <Statistic title="状态" value={task.status === 'completed' ? '完成' : '处理中'} />
          </Col>
        </Row>

        {results && (
          <Row gutter={16} style={{ marginTop: 24 }}>
            <Col span={8}>
              <Statistic title="含虫巢图片" value={results.image_stats.with_nests} />
            </Col>
            <Col span={8}>
              <Statistic title="虫巢检测总数" value={results.image_stats.total_nest_detections} />
            </Col>
            <Col span={8}>
              <Statistic
                title="去重后虫巢"
                value={results.nest_stats.total_unique}
                valueStyle={{ color: results.nest_stats.severe > 0 ? '#cf1322' : undefined }}
              />
            </Col>
          </Row>
        )}

        {results?.nest_stats && (
          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={8}>
              <Card size="small" style={{ background: '#fff1f0', borderColor: '#ffa39e' }}>
                <Statistic title="重度" value={results.nest_stats.severe} valueStyle={{ color: '#cf1322' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" style={{ background: '#fff7e6', borderColor: '#ffd591' }}>
                <Statistic title="中度" value={results.nest_stats.medium} valueStyle={{ color: '#fa8c16' }} />
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small" style={{ background: '#f6ffed', borderColor: '#b7eb8f' }}>
                <Statistic title="轻度" value={results.nest_stats.light} valueStyle={{ color: '#52c41a' }} />
              </Card>
            </Col>
          </Row>
        )}
      </Card>

      <div style={{ marginTop: 16, textAlign: 'right' }}>
        <ReportGenerator data={{
          task_name: task.task_name,
          area_name: task.area_name,
          operator: task.operator,
          region_path: task.region_path ?? undefined,
          plot_area_mu: task.plot_area_mu,
          forestry_sub_compartment: task.forestry_sub_compartment,
          created_at: task.created_at,
          completed_at: task.completed_at ?? undefined,
          total_images: task.total_images,
          processed_images: task.processed_images,
          nests,
        }} />
      </div>
    </div>
  );
};

export default TaskOverview;
