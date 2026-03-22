import React, { useEffect, useState } from 'react';
import { Table, Button, Tag, Space, Card, message } from 'antd';
import { PlusOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { taskApi } from '../services/api';

interface Task {
  id: string;
  task_name: string;
  area_name: string;
  operator: string;
  status: string;
  total_images: number;
  processed_images: number;
  created_at: string;
}

const TaskList: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const data = await taskApi.getTasks();
      setTasks(data.items || []);
    } catch (error) {
      message.error('获取任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      uploading: { color: 'blue', text: '上传中' },
      processing: { color: 'orange', text: '处理中' },
      completed: { color: 'green', text: '已完成' },
      failed: { color: 'red', text: '失败' }
    };
    const { color, text } = statusMap[status] || { color: 'default', text: status };
    return <Tag color={color}>{text}</Tag>;
  };

  const columns = [
    { title: '任务名称', dataIndex: 'task_name', key: 'task_name' },
    { title: '巡检区域', dataIndex: 'area_name', key: 'area_name' },
    { title: '操作员', dataIndex: 'operator', key: 'operator' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status)
    },
    {
      title: '图片数量',
      key: 'images',
      render: (record: Task) => `${record.processed_images}/${record.total_images}`
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString()
    },
    {
      title: '操作',
      key: 'action',
      render: (record: Task) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/tasks/${record.id}`)}
          >
            查看
          </Button>
        </Space>
      )
    }
  ];

  return (
    <Card
      title="巡检任务列表"
      extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/tasks/create')}
        >
          新建任务
        </Button>
      }
    >
      <Table
        columns={columns}
        dataSource={tasks}
        loading={loading}
        rowKey="id"
      />
    </Card>
  );
};

export default TaskList;
