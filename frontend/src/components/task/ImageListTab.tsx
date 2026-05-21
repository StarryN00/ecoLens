import React, { useState } from 'react';
import { Card, Table, Tag, Row, Col, Button, message } from 'antd';
import { DownloadOutlined, FileImageOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TaskImage, Task } from '../../types/task';
import { getSeverityTag } from './taskUtils';
import AuthedImage from '../AuthedImage';

interface Props {
  images: TaskImage[];
  task: Task;
  loading: boolean;
}

const ImageListTab: React.FC<Props> = ({ images, task, loading }) => {
  const [imageFilter, setImageFilter] = useState<'all' | 'with_nest' | 'without_nest'>('all');

  const exportImagesJson = () => {
    const exportData = images.map((img) => ({
      filename: img.filename,
      gps: img.has_gps ? { latitude: img.latitude, longitude: img.longitude } : null,
      altitude: img.altitude,
      has_nest: img.detection?.has_nest || false,
    }));
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `task_${task.id}_images.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    message.success('导出成功');
  };

  const imageColumns: ColumnsType<TaskImage> = [
    {
      title: '图片',
      key: 'thumbnail',
      width: 120,
      render: (_: any, record: TaskImage) => (
        <AuthedImage
          path={`/api/v1/images/${record.id}/thumbnail`}
          previewPath={`/api/v1/images/${record.id}`}
          originalPath={`/api/v1/images/${record.id}?max_width=0`}
          alt={record.filename}
          style={{
            width: 100,
            height: 75,
            objectFit: 'cover',
            cursor: 'pointer',
            border: record.detection?.has_nest ? '2px solid #ff4d4f' : 'none',
          }}
        />
      ),
    },
    { title: '文件名', dataIndex: 'filename', key: 'filename', width: 200 },
    {
      title: 'GPS',
      dataIndex: 'has_gps',
      key: 'has_gps',
      width: 180,
      render: (has: boolean, record: TaskImage) =>
        has ? (
          <span style={{ fontSize: '12px' }}>
            {record.latitude?.toFixed(6)}, {record.longitude?.toFixed(6)}
          </span>
        ) : (
          <Tag color="warning">无GPS</Tag>
        ),
    },
    {
      title: '高度',
      dataIndex: 'altitude',
      key: 'altitude',
      width: 80,
      render: (v: number) => (v ? `${v.toFixed(1)}m` : '-'),
    },
    {
      title: '虫巢',
      key: 'nest',
      width: 80,
      render: (_: any, record: TaskImage) => {
        if (!record.detection) return <Tag color="default">未检测</Tag>;
        return record.detection.has_nest ? <Tag color="red">有</Tag> : <Tag color="default">无</Tag>;
      },
    },
    {
      title: '严重程度',
      key: 'severity',
      width: 80,
      render: (_: any, record: TaskImage) => {
        if (!record.detection?.has_nest) return '-';
        return getSeverityTag(record.detection.max_severity || 'light');
      },
    },
    {
      title: '检测结果',
      key: 'annotated',
      width: 100,
      render: (_: any, record: TaskImage) => {
        if (!record.detection?.has_nest) return '-';
        return (
          <AuthedImage
            path={`/api/v1/images/${record.id}/annotated`}
            originalPath={`/api/v1/images/${record.id}/annotated?max_width=0`}
            alt="检测结果"
            style={{ width: 80, height: 60, objectFit: 'cover', cursor: 'pointer' }}
          />
        );
      },
    },
  ];

  const totalImages = images.length;
  const imagesWithNest = images.filter((img) => img.detection?.has_nest).length;
  const imagesWithoutNest = totalImages - imagesWithNest;
  const nestRatio = totalImages > 0 ? ((imagesWithNest / totalImages) * 100).toFixed(1) : '0.0';

  const filteredImages = images.filter((img) => {
    if (imageFilter === 'with_nest') return img.detection?.has_nest;
    if (imageFilter === 'without_nest') return !img.detection?.has_nest;
    return true;
  });

  return (
    <Card
      className="eco-panel"
      title="图片列表"
      loading={loading}
      extra={
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          onClick={exportImagesJson}
          disabled={images.length === 0}
        >
          导出JSON
        </Button>
      }
    >
      <div style={{ marginBottom: 16, padding: 16, background: '#f5f8f4', borderRadius: 8, border: '1px solid #dce8de' }}>
        <Row gutter={16} align="middle">
          <Col>
            <span style={{ fontWeight: 'bold' }}>
              <FileImageOutlined style={{ color: '#1f7a4d', marginRight: 6 }} />
              虫巢检测统计
            </span>
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
        scroll={{ x: 820 }}
      />
    </Card>
  );
};

export default ImageListTab;
