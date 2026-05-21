import React, { useEffect, useState } from 'react';
import { Table, Button, Tag, Space, Card, Cascader, message } from 'antd';
import { PlusOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { regionApi, taskApi } from '../services/api';

interface Task {
  id: string;
  task_name: string;
  area_name: string;
  operator: string;
  region_path?: string | null;
  status: string;
  total_images: number;
  processed_images: number;
  created_at: string;
}

interface RegionNode {
  id: string;
  name: string;
  children?: RegionNode[];
}

interface CascaderOption {
  value: string;
  label: string;
  children?: CascaderOption[];
}

const toCascaderOptions = (nodes: RegionNode[]): CascaderOption[] =>
  nodes.map((n) => ({
    value: n.id,
    label: n.name,
    children:
      n.children && n.children.length > 0
        ? toCascaderOptions(n.children)
        : undefined,
  }));

const TaskList: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [regionOptions, setRegionOptions] = useState<CascaderOption[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    fetchTasks();
    regionApi
      .getTree()
      .then((data: any) => setRegionOptions(toCascaderOptions(data?.items || [])))
      .catch(() => {});
  }, []);

  /**
   * region_id 过滤透传给后端（TaskService.list_tasks 在 SQL WHERE 处理），
   * 不是前端对当前页结果再筛——否则会漏掉不在当前页的匹配任务。
   */
  const fetchTasks = async (regionId?: string) => {
    setLoading(true);
    try {
      const params = regionId ? { region_id: regionId } : undefined;
      const data = await taskApi.getTasks(params);
      setTasks(data.items || []);
    } catch (error) {
      message.error('获取任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  // Cascader 选到街镇(town,叶子)即按该 town 过滤；清空则取消过滤
  const handleRegionFilter = (value: unknown) => {
    const path = (value as string[]) || [];
    const townId = path.length === 3 ? path[2] : undefined;
    fetchTasks(townId);
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      uploading: { color: 'blue', text: '上传中' },
      processing: { color: 'orange', text: '处理中' },
      completed: { color: 'green', text: '已完成' },
      failed: { color: 'red', text: '失败' },
    };
    const { color, text } = statusMap[status] || {
      color: 'default',
      text: status,
    };
    return <Tag color={color}>{text}</Tag>;
  };

  const columns = [
    { title: '任务名称', dataIndex: 'task_name', key: 'task_name' },
    {
      title: '所属区域',
      dataIndex: 'region_path',
      key: 'region_path',
      render: (p: string | null) =>
        p ? <span style={{ fontSize: 12 }}>{p}</span> : <Tag>未分配</Tag>,
    },
    { title: '巡检区域说明', dataIndex: 'area_name', key: 'area_name' },
    { title: '操作员', dataIndex: 'operator', key: 'operator' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '图片数量',
      key: 'images',
      render: (record: Task) =>
        `${record.processed_images}/${record.total_images}`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => new Date(date).toLocaleString(),
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
      ),
    },
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
      <Space style={{ marginBottom: 16 }}>
        <span>按区域筛选：</span>
        <Cascader
          options={regionOptions}
          onChange={handleRegionFilter}
          placeholder="选择 市/区/街镇 过滤（选到街镇生效）"
          changeOnSelect
          allowClear
          style={{ width: 320 }}
        />
      </Space>
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
