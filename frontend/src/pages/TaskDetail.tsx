import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Tag, Statistic, Row, Col, Table, Button, message, Tabs, Image as AntImage, Progress } from 'antd';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { taskApi } from '../services/api';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { DownloadOutlined, EyeOutlined, ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

// 修复Leaflet默认图标问题
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface Task {
  id: string;
  task_name: string;
  area_name: string;
  operator: string;
  status: string;
  total_images: number;
  processed_images: number;
  created_at: string;
  completed_at: string | null;
}

interface Nest {
  id: string;
  nest_code: string;
  latitude: number;
  longitude: number;
  severity: string;
  confidence: number;
  detection_count: number;
  source_images: string[];
  created_at: string;
}

interface TaskResults {
  task_id: string;
  image_stats: {
    total_processed: number;
    with_camphor_tree: number;
    with_nests: number;
    total_nest_detections: number;
  };
  nest_stats: {
    total_unique: number;
    severe: number;
    medium: number;
    light: number;
  };
}

interface TaskImage {
  id: string;
  filename: string;
  has_gps: boolean;
  latitude?: number;
  longitude?: number;
  altitude?: number;
  detection?: {
    has_nest: boolean;
    max_severity: string | null;
  } | null;
}

const TaskDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [results, setResults] = useState<TaskResults | null>(null);
  const [nests, setNests] = useState<Nest[]>([]);
  const [images, setImages] = useState<TaskImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [imageFilter, setImageFilter] = useState<'all' | 'with_nest' | 'without_nest'>('all');

  useEffect(() => {
    if (id) {
      fetchTaskDetail();
    }
  }, [id]);

  const fetchTaskDetail = async () => {
    setLoading(true);
    try {
      const [taskData, resultsData, nestsData, imagesData] = await Promise.all([
        taskApi.getTask(id!),
        taskApi.getTaskResults(id!).catch(() => null),
        taskApi.getTaskNests(id!).catch(() => ({ items: [] })),
        taskApi.getTaskImages(id!).catch(() => ({ items: [] })),
      ]);
      
      setTask(taskData);
      setResults(resultsData);
      setNests(nestsData.items || []);
      setImages(imagesData.items || []);
    } catch (error) {
      message.error('获取任务详情失败');
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

  const getSeverityTag = (severity: string) => {
    const severityMap: Record<string, { color: string; text: string }> = {
      severe: { color: 'red', text: '重度' },
      medium: { color: 'orange', text: '中度' },
      light: { color: 'green', text: '轻度' }
    };
    const { color, text } = severityMap[severity] || { color: 'default', text: severity };
    return <Tag color={color}>{text}</Tag>;
  };

  const exportReport = () => {
    message.info('报告导出功能开发中...');
  };

  const nestColumns: ColumnsType<Nest> = [
    { title: '编号', dataIndex: 'nest_code', key: 'nest_code' },
    { title: '经度', dataIndex: 'longitude', key: 'longitude', render: (v: number) => v?.toFixed(6) },
    { title: '纬度', dataIndex: 'latitude', key: 'latitude', render: (v: number) => v?.toFixed(6) },
    { title: '严重程度', dataIndex: 'severity', key: 'severity', render: getSeverityTag },
    { title: '置信度', dataIndex: 'confidence', key: 'confidence', render: (v: number) => `${(v * 100).toFixed(1)}%` },
    { title: '检测次数', dataIndex: 'detection_count', key: 'detection_count' },
  ];

  const imageColumns: ColumnsType<TaskImage> = [
    {
      title: '图片',
      key: 'thumbnail',
      width: 120,
      render: (_: any, record: TaskImage) => {
        const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
        // 尝试缩略图，如果不存在则使用原图
        const thumbUrl = `${baseUrl}/api/v1/images/${record.id}/thumbnail`;
        const originalUrl = `${baseUrl}/api/v1/images/${record.id}`;
        return (
          <AntImage
            src={thumbUrl}
            alt={record.filename}
            style={{ width: 100, height: 75, objectFit: 'cover', cursor: 'pointer', border: record.detection?.has_nest ? '2px solid #ff4d4f' : 'none' }}
            preview={{ src: originalUrl }}
            fallback={originalUrl}
          />
        );
      }
    },
    { title: '文件名', dataIndex: 'filename', key: 'filename', width: 200 },
    {
      title: 'GPS',
      dataIndex: 'has_gps',
      key: 'has_gps',
      width: 180,
      render: (has: boolean, record: TaskImage) => (
        has ? (
          <span style={{ fontSize: '12px' }}>
            {record.latitude?.toFixed(6)}, {record.longitude?.toFixed(6)}
          </span>
        ) : <Tag color="warning">无GPS</Tag>
      )
    },
    {
      title: '高度',
      dataIndex: 'altitude',
      key: 'altitude',
      width: 80,
      render: (v: number) => v ? `${v.toFixed(1)}m` : '-'
    },
    // 香樟树识别暂时关闭（模型不存在）
    // {
    //   title: '香樟树',
    //   key: 'camphor',
    //   width: 80,
    //   render: (_: any, record: TaskImage) => {
    //     if (!record.detection) return <Tag color="default">未检测</Tag>;
    //     return record.detection.has_camphor_tree ?
    //       <Tag color="green">有</Tag> :
    //       <Tag color="default">无</Tag>;
    //   }
    // },
    {
      title: '虫巢',
      key: 'nest',
      width: 80,
      render: (_: any, record: TaskImage) => {
        if (!record.detection) return <Tag color="default">未检测</Tag>;
        return record.detection.has_nest ?
          <Tag color="red">有</Tag> :
          <Tag color="default">无</Tag>;
      }
    },
    {
      title: '严重程度',
      key: 'severity',
      width: 80,
      render: (_: any, record: TaskImage) => {
        if (!record.detection?.has_nest) return '-';
        return getSeverityTag(record.detection.max_severity || 'light');
      }
    },
    {
      title: '检测结果',
      key: 'annotated',
      width: 100,
      render: (_: any, record: TaskImage) => {
        if (!record.detection?.has_nest) return '-';
        const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
        const annotatedUrl = `${baseUrl}/api/v1/images/${record.id}/annotated`;
        return (
          <AntImage
            src={annotatedUrl}
            alt="检测结果"
            style={{ width: 80, height: 60, objectFit: 'cover', cursor: 'pointer' }}
            preview={{ src: annotatedUrl }}
            fallback="检测结果加载失败"
          />
        );
      }
    },
  ];

  // 计算地图中心点
  const mapCenter = nests.length > 0 
    ? [nests[0].latitude, nests[0].longitude] 
    : images.length > 0 && images[0].latitude
      ? [images[0].latitude, images[0].longitude]
      : [30.25, 120.15]; // 默认杭州位置

  const renderOverview = () => (
    <>
      <Card title="任务详情" loading={loading}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="任务名称">{task?.task_name}</Descriptions.Item>
          <Descriptions.Item label="任务ID">{task?.id}</Descriptions.Item>
          <Descriptions.Item label="巡检区域">{task?.area_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="操作员">{task?.operator || '-'}</Descriptions.Item>
          <Descriptions.Item label="状态">{getStatusTag(task?.status || '')}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {task?.created_at ? new Date(task.created_at).toLocaleString() : '-'}
          </Descriptions.Item>
          {task?.completed_at && (
            <Descriptions.Item label="完成时间">
              {new Date(task.completed_at).toLocaleString()}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Card title="统计概览" style={{ marginTop: 16 }} loading={loading}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="图片总数" value={task?.total_images || 0} />
          </Col>
          <Col span={6}>
            <Statistic title="已处理" value={task?.processed_images || 0} />
          </Col>
          <Col span={6}>
            <Progress 
              percent={task?.total_images ? Math.round((task.processed_images / task.total_images) * 100) : 0}
              status={task?.status === 'completed' ? 'success' : 'active'}
              format={(percent) => `${percent}%`}
            />
          </Col>
          <Col span={6}>
            <Statistic title="状态" value={task?.status === 'completed' ? '完成' : '处理中'} />
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
        <Button type="primary" icon={<DownloadOutlined />} onClick={exportReport}>
          导出报告
        </Button>
      </div>
    </>
  );

  const renderMap = () => (
    <Card title="虫巢分布地图" loading={loading}>
      {nests.length > 0 ? (
        <div style={{ height: 500 }}>
          <MapContainer 
            center={mapCenter as [number, number]} 
            zoom={16} 
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {nests.map((nest) => (
              <Marker 
                key={nest.id} 
                position={[nest.latitude, nest.longitude]}
              >
                <Popup>
                  <div>
                    <strong>{nest.nest_code}</strong><br/>
                    严重程度: {nest.severity}<br/>
                    置信度: {(nest.confidence * 100).toFixed(1)}%<br/>
                    检测次数: {nest.detection_count}
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <p>暂无虫巢位置数据</p>
        </div>
      )}
    </Card>
  );

  const renderNests = () => (
    <Card title="虫巢列表" loading={loading}>
      <Table 
        columns={nestColumns} 
        dataSource={nests}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />
    </Card>
  );

  const exportImagesJson = () => {
    const exportData = images.map(img => ({
      filename: img.filename,
      gps: img.has_gps ? { latitude: img.latitude, longitude: img.longitude } : null,
      altitude: img.altitude,
      has_nest: img.detection?.has_nest || false,
    }));

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `task_${task?.id}_images.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    message.success('导出成功');
  };

  const renderImages = () => {
    // 计算虫巢比例统计
    const totalImages = images.length;
    const imagesWithNest = images.filter(img => img.detection?.has_nest).length;
    const imagesWithoutNest = totalImages - imagesWithNest;
    const nestRatio = totalImages > 0 ? (imagesWithNest / totalImages * 100).toFixed(1) : '0.0';

    // 根据筛选条件过滤图片
    const filteredImages = images.filter(img => {
      if (imageFilter === 'all') return true;
      if (imageFilter === 'with_nest') return img.detection?.has_nest;
      if (imageFilter === 'without_nest') return !img.detection?.has_nest;
      return true;
    });

    return (
      <Card
        title="图片列表"
        loading={loading}
        extra={
          <Button type="primary" onClick={exportImagesJson} disabled={images.length === 0}>
            导出JSON
          </Button>
        }
      >
        {/* 统计信息 */}
        <div style={{ marginBottom: 16, padding: 16, background: '#f5f5f5', borderRadius: 8 }}>
          <Row gutter={16} align="middle">
            <Col>
              <span style={{ fontWeight: 'bold' }}>虫巢检测统计：</span>
            </Col>
            <Col>
              <Tag color="blue">总图片: {totalImages}</Tag>
            </Col>
            <Col>
              <Tag color="red">有虫巢: {imagesWithNest} ({nestRatio}%)</Tag>
            </Col>
            <Col>
              <Tag color="green">无虫巢: {imagesWithoutNest}</Tag>
            </Col>
            <Col flex="auto" style={{ textAlign: 'right' }}>
              <span style={{ marginRight: 8 }}>筛选：</span>
              <Button.Group>
                <Button 
                  type={imageFilter === 'all' ? 'primary' : 'default'}
                  size="small"
                  onClick={() => setImageFilter('all')}
                >
                  全部
                </Button>
                <Button 
                  type={imageFilter === 'with_nest' ? 'primary' : 'default'}
                  size="small"
                  onClick={() => setImageFilter('with_nest')}
                >
                  有虫巢
                </Button>
                <Button 
                  type={imageFilter === 'without_nest' ? 'primary' : 'default'}
                  size="small"
                  onClick={() => setImageFilter('without_nest')}
                >
                  无虫巢
                </Button>
              </Button.Group>
            </Col>
          </Row>
        </div>

        <Table
          columns={imageColumns}
          dataSource={filteredImages}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>
    );
  };

  const tabItems = [
    { key: 'overview', label: '概览', children: renderOverview() },
    { key: 'map', label: '地图', children: renderMap() },
    { key: 'nests', label: '虫巢列表', children: renderNests() },
    { key: 'images', label: '图片', children: renderImages() },
  ];

  if (!task) {
    return <Card loading={loading}>加载中...</Card>;
  }

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
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </div>
  );
};

export default TaskDetail;
