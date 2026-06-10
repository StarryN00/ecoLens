import React, { useState } from 'react';
import { Card, Table, Tag, Row, Col, Button, message } from 'antd';
import { DownloadOutlined, FileImageOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TaskImage, Task } from '../../types/task';
import { getSeverityTag } from './taskUtils';
import AuthedImage from '../AuthedImage';
import { taskApi } from '../../services/api';

interface Props {
  images: TaskImage[];
  task: Task;
  loading: boolean;
}

const ImageListTab: React.FC<Props> = ({ images, task, loading }) => {
  const [imageFilter, setImageFilter] = useState<'all' | 'with_nest' | 'without_nest'>('all');
  const [exportingCsv, setExportingCsv] = useState(false);

  const exportImagesCsv = async () => {
    setExportingCsv(true);
    try {
      const allImages = await fetchAllTaskImages(task.id, task.total_images, images);
      const csv = buildImagesCsv(allImages);
      const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const date = new Date().toISOString().split('T')[0];
      link.href = url;
      link.download = `任务图片数据_${sanitizeDownloadName(task.task_name)}_${date}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      message.success(`已导出 ${allImages.length} 条图片数据`);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'CSV导出失败';
      message.error(errorMessage);
    } finally {
      setExportingCsv(false);
    }
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
          onClick={exportImagesCsv}
          loading={exportingCsv}
          disabled={loading || (images.length === 0 && task.total_images === 0)}
        >
          导出CSV
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

const CSV_PAGE_SIZE = 500;

async function fetchAllTaskImages(
  taskId: string,
  totalImages: number,
  fallbackImages: TaskImage[],
): Promise<TaskImage[]> {
  const allImages: TaskImage[] = [];
  let skip = 0;

  while (totalImages === 0 || allImages.length < totalImages) {
    const page = await taskApi.getTaskImages(taskId, {
      skip,
      limit: CSV_PAGE_SIZE,
    }) as { items?: TaskImage[] };
    const items = page.items || [];
    allImages.push(...items);
    if (items.length < CSV_PAGE_SIZE) break;
    skip += CSV_PAGE_SIZE;
  }

  return allImages.length > 0 ? allImages : fallbackImages;
}

function buildImagesCsv(images: TaskImage[]): string {
  const rows = images.map((img, index) => [
    index + 1,
    img.filename,
    formatDate(img.capture_time),
    formatDate(img.created_at),
    img.has_gps ? formatNumber(img.latitude, 6) : '',
    img.has_gps ? formatNumber(img.longitude, 6) : '',
    formatNumber(img.altitude, 1),
    img.has_gps ? '是' : '否',
    img.detection ? (img.detection.has_nest ? '是' : '否') : '未检测',
    formatSeverity(img.detection?.max_severity),
  ]);

  return [
    ['序号', '照片名称', '拍摄日期', '入库日期', '纬度', '经度', '海拔高度(m)', '是否有GPS', '是否有虫害', '最高严重程度'],
    ...rows,
  ].map((row) => row.map(formatCsvCell).join(',')).join('\n');
}

function formatCsvCell(value: unknown): string {
  let text = value == null ? '' : String(value);
  if (/^[=+\-@]/.test(text)) {
    text = `'${text}`;
  }
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function formatDate(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

function formatNumber(value?: number | null, digits = 6): string {
  return typeof value === 'number' ? value.toFixed(digits) : '';
}

function formatSeverity(value?: string | null): string {
  if (!value) return '';
  const severityMap: Record<string, string> = {
    severe: '重度',
    medium: '中度',
    light: '轻度',
  };
  return severityMap[value] || value;
}

function sanitizeDownloadName(name: string): string {
  return name
    .replace(/[\\/:*?"<>|\r\n\t]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80) || '未命名任务';
}

export default ImageListTab;
