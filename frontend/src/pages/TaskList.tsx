import React, { useEffect, useState } from 'react';
import { Table, Button, Tag, Space, Card, Cascader, message, Progress } from 'antd';
import {
  CompassOutlined,
  EyeOutlined,
  FileImageOutlined,
  PlusOutlined,
  RadarChartOutlined,
  WarningOutlined,
} from '@ant-design/icons';
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

interface RegionSituation {
  name: string;
  taskCount: number;
  activeCount: number;
  failedCount: number;
  totalImages: number;
  processedImages: number;
  isUnassigned: boolean;
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

const getRegionSituationName = (task: Task) => {
  if (!task.region_path) return '未分配';
  const parts = task.region_path.split('/').filter(Boolean);
  return parts[1] || parts[0] || task.area_name || '未分配';
};

const buildRegionSituations = (tasks: Task[]): RegionSituation[] => {
  const byRegion = new Map<string, RegionSituation>();

  tasks.forEach((task) => {
    const name = getRegionSituationName(task);
    const isUnassigned = !task.region_path;
    const current =
      byRegion.get(name) ||
      ({
        name,
        taskCount: 0,
        activeCount: 0,
        failedCount: 0,
        totalImages: 0,
        processedImages: 0,
        isUnassigned,
      } satisfies RegionSituation);

    current.taskCount += 1;
    current.activeCount += ['uploading', 'processing'].includes(task.status)
      ? 1
      : 0;
    current.failedCount += task.status === 'failed' ? 1 : 0;
    current.totalImages += task.total_images || 0;
    current.processedImages += task.processed_images || 0;
    current.isUnassigned = current.isUnassigned || isUnassigned;
    byRegion.set(name, current);
  });

  return Array.from(byRegion.values()).sort((a, b) => {
    const aFollowUp = a.activeCount + a.failedCount;
    const bFollowUp = b.activeCount + b.failedCount;
    return (
      bFollowUp - aFollowUp ||
      b.totalImages - a.totalImages ||
      b.taskCount - a.taskCount ||
      a.name.localeCompare(b.name, 'zh-CN')
    );
  });
};

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

  const completedTasks = tasks.filter((task) => task.status === 'completed').length;
  const activeTasks = tasks.filter((task) =>
    ['uploading', 'processing'].includes(task.status),
  ).length;
  const totalImages = tasks.reduce((sum, task) => sum + (task.total_images || 0), 0);
  const processedImages = tasks.reduce(
    (sum, task) => sum + (task.processed_images || 0),
    0,
  );
  const processedPercent = totalImages
    ? Math.round((processedImages / totalImages) * 100)
    : 0;
  const regionSituations = buildRegionSituations(tasks);
  const coveredRegionCount = regionSituations.filter(
    (item) => !item.isUnassigned,
  ).length;
  const unassignedTasks = tasks.filter((task) => !task.region_path).length;
  const followUpTasks = tasks.filter((task) =>
    ['uploading', 'processing', 'failed'].includes(task.status),
  ).length;
  const topRegionSituations = regionSituations.slice(0, 5);

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
    <div className="eco-page">
      <div className="eco-page-header">
        <div>
          <div className="eco-eyebrow">Inspection Command</div>
          <h1 className="eco-page-title">巡检任务工作台</h1>
          <div className="eco-page-desc">
            汇总无人机影像巡检进度、行政区域筛选和虫巢识别任务状态，便于快速进入复核与处置。
          </div>
        </div>
        <div className="eco-actions">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/tasks/create')}
          >
            新建任务
          </Button>
        </div>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <div className="metric-label">任务总数</div>
          <div className="metric-value">{tasks.length}</div>
          <div className="metric-hint">已完成 {completedTasks} 个</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">处理中任务</div>
          <div className="metric-value">{activeTasks}</div>
          <div className="metric-hint">上传与推理中的任务</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">影像总量</div>
          <div className="metric-value">{totalImages}</div>
          <div className="metric-hint">已处理 {processedImages} 张</div>
        </div>
        <div className="metric-card risk">
          <div className="metric-label">处理进度</div>
          <div className="metric-value">{processedPercent}%</div>
          <Progress percent={processedPercent} showInfo={false} strokeColor="#1f7a4d" />
        </div>
      </div>

      <div className="workspace-grid">
        <Card className="eco-panel" title="任务队列">
          <div className="eco-toolbar">
            <div className="eco-filter">
              <CompassOutlined style={{ color: '#1f7a4d' }} />
              <span>行政区划</span>
              <Cascader
                options={regionOptions}
                onChange={handleRegionFilter}
                placeholder="选择 市 / 区 / 街镇"
                changeOnSelect
                allowClear
                style={{ width: 320 }}
              />
            </div>
            <Space size={8} wrap>
              <Tag icon={<RadarChartOutlined />} color="green">
                已完成 {completedTasks}
              </Tag>
              <Tag icon={<FileImageOutlined />} color="blue">
                影像 {totalImages}
              </Tag>
            </Space>
          </div>
          <Table
            columns={columns}
            dataSource={tasks}
            loading={loading}
            rowKey="id"
            scroll={{ x: 980 }}
            pagination={{ pageSize: 10 }}
          />
        </Card>

        <Card className="eco-panel" title="区域态势">
          <div className="region-situation">
            <div className="situation-summary">
              <div className="situation-stat">
                <span>覆盖区域</span>
                <strong>{coveredRegionCount}</strong>
              </div>
              <div className="situation-stat">
                <span>待跟进</span>
                <strong>{followUpTasks}</strong>
              </div>
              <div className="situation-stat warning">
                <span>未分配</span>
                <strong>{unassignedTasks}</strong>
              </div>
            </div>

            <div className="situation-section-title">区域待跟进排行</div>
            <div className="region-rank-list">
              {topRegionSituations.length === 0 ? (
                <div className="region-rank-empty">暂无巡检任务数据</div>
              ) : (
                topRegionSituations.map((item, index) => {
                  const completion = item.totalImages
                    ? Math.round((item.processedImages / item.totalImages) * 100)
                    : 0;
                  const followUpCount = item.activeCount + item.failedCount;

                  return (
                    <div className="region-rank-item" key={item.name}>
                      <div className="rank-index">{index + 1}</div>
                      <div className="rank-main">
                        <div className="rank-heading">
                          <span>{item.name}</span>
                          <Tag
                            color={
                              item.isUnassigned
                                ? 'default'
                                : followUpCount > 0
                                  ? 'orange'
                                  : 'green'
                            }
                          >
                            {item.isUnassigned
                              ? '待归档'
                              : followUpCount > 0
                                ? '需跟进'
                                : '稳定'}
                          </Tag>
                        </div>
                        <div className="rank-meta">
                          <span>{item.taskCount} 个任务</span>
                          <span>影像 {item.totalImages}</span>
                          <span>待跟进 {followUpCount}</span>
                        </div>
                        <Progress
                          percent={completion}
                          showInfo={false}
                          size="small"
                          strokeColor={followUpCount > 0 ? '#d97706' : '#1f7a4d'}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
          <Space direction="vertical" size={10} style={{ marginTop: 16, width: '100%' }}>
            <Tag color="green">三级目录筛选：市 / 区 / 街镇</Tag>
            <Tag color={followUpTasks > 0 ? 'orange' : 'green'} icon={<WarningOutlined />}>
              {followUpTasks > 0
                ? `待跟进 ${followUpTasks} 个任务`
                : '当前任务均已完成或无待处理项'}
            </Tag>
            {unassignedTasks > 0 && <Tag>未分配 {unassignedTasks}</Tag>}
            <div style={{ color: '#607065', fontSize: 13 }}>
              这里按任务状态、行政区划和影像处理进度汇总；虫巢点位和检测框在任务详情页复核。
            </div>
          </Space>
        </Card>
      </div>
    </div>
  );
};

export default TaskList;
