import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Tabs, Button, message } from 'antd';
import { ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons';
import { useTaskDetail } from '../hooks/useTaskDetail';
import TaskOverview from '../components/task/TaskOverview';
import NestMap from '../components/task/NestMap';
import NestListTab from '../components/task/NestListTab';
import ImageListTab from '../components/task/ImageListTab';
import UploadMoreTab from '../components/task/UploadMoreTab';

const TaskDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { task, results, nests, images, loading, error } = useTaskDetail(id!);

  useEffect(() => {
    if (error) message.error(error.message);
  }, [error]);

  if (!task) {
    return <Card loading={loading}>加载中...</Card>;
  }

  const tabItems = [
    { key: 'overview', label: '概览', children: <TaskOverview task={task} results={results} loading={loading} /> },
    { key: 'map', label: '地图', children: <NestMap nests={nests} images={images} loading={loading} /> },
    { key: 'nests', label: '虫巢列表', children: <NestListTab nests={nests} loading={loading} /> },
    { key: 'images', label: '图片', children: <ImageListTab images={images} task={task} loading={loading} /> },
    { key: 'upload', label: '追加上传', children: <UploadMoreTab /> },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          返回任务列表
        </Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/tasks/create')}>
          新建任务
        </Button>
      </div>
      <Tabs defaultActiveKey="overview" items={tabItems} />
    </div>
  );
};

export default TaskDetail;
