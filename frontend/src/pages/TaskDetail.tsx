import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Tabs, Button, message, Progress, Tag } from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  EnvironmentOutlined,
  FileImageOutlined,
  PlusOutlined,
  RadarChartOutlined,
} from '@ant-design/icons';
import { useTaskDetail } from '../hooks/useTaskDetail';
import TaskOverview from '../components/task/TaskOverview';
import NestMap from '../components/task/NestMap';
import NestListTab from '../components/task/NestListTab';
import ImageListTab from '../components/task/ImageListTab';
import UploadMoreTab from '../components/task/UploadMoreTab';
import { downloadTaskReportDocx } from '../services/api';

const TaskDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { task, results, nests, images, loading, error, refetch } = useTaskDetail(id!);
  const [exportingReport, setExportingReport] = useState(false);

  useEffect(() => {
    if (error) message.error(error.message);
  }, [error]);

  if (!task) {
    return <Card loading={loading}>加载中...</Card>;
  }

  const processedPercent = task.total_images
    ? Math.round((task.processed_images / task.total_images) * 100)
    : 0;

  const handleExportReport = async () => {
    setExportingReport(true);
    try {
      await downloadTaskReportDocx(task.id, task.task_name);
      message.success('报告已开始下载');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '报告导出失败';
      message.error(errorMessage);
    } finally {
      setExportingReport(false);
    }
  };

  const tabItems = [
    { key: 'overview', label: '概览', children: <TaskOverview task={task} results={results} nests={nests} loading={loading} /> },
    { key: 'map', label: '地图', children: <NestMap nests={nests} images={images} loading={loading} /> },
    { key: 'nests', label: '虫巢列表', children: <NestListTab nests={nests} loading={loading} /> },
    { key: 'images', label: '图片', children: <ImageListTab images={images} task={task} loading={loading} /> },
    { key: 'upload', label: '追加上传', children: <UploadMoreTab task={task} onUploaded={refetch} /> },
  ];

  return (
    <div className="eco-page">
      <div className="eco-page-header">
        <div>
          <div className="eco-eyebrow">Task Review</div>
          <h1 className="eco-page-title">{task.task_name}</h1>
          <div className="eco-page-desc">
            {task.region_path || '未分配区域'} · {task.area_name || '暂无巡检区域说明'}
          </div>
        </div>
        <div className="eco-actions">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
            返回
          </Button>
          <Button icon={<DownloadOutlined />} loading={exportingReport} onClick={handleExportReport}>
            导出Word报告
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/tasks/create')}>
            新建任务
          </Button>
        </div>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <div className="metric-label">图片总数</div>
          <div className="metric-value">{task.total_images || 0}</div>
          <div className="metric-hint">
            <FileImageOutlined /> 已处理 {task.processed_images || 0} 张
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">推理进度</div>
          <div className="metric-value">{processedPercent}%</div>
          <Progress percent={processedPercent} showInfo={false} strokeColor="#1f7a4d" />
        </div>
        <div className="metric-card">
          <div className="metric-label">去重后虫巢</div>
          <div className="metric-value">{results?.nest_stats.total_unique ?? nests.length}</div>
          <div className="metric-hint">
            <RadarChartOutlined /> 已聚合检测结果
          </div>
        </div>
        <div className="metric-card risk">
          <div className="metric-label">重度风险</div>
          <div className="metric-value">{results?.nest_stats.severe ?? 0}</div>
          <div className="metric-hint">
            <Tag color="red">需优先复核</Tag>
          </div>
        </div>
      </div>

      <Card className="eco-panel">
        <div className="eco-toolbar">
          <Tag icon={<EnvironmentOutlined />} color="green">
            {task.region_path || '未分配'}
          </Tag>
          <Tag color={task.status === 'completed' ? 'green' : 'orange'}>
            {task.status}
          </Tag>
        </div>
        <Tabs defaultActiveKey="overview" items={tabItems} />
      </Card>
    </div>
  );
};

export default TaskDetail;
