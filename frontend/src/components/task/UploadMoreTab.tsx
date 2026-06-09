import React, { useState } from 'react';
import { Alert, Button, Card, Space, Tag, Upload, message } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import { taskApi } from '../../services/api';
import type { Task } from '../../types/task';

interface Props {
  task: Task;
  onUploaded: () => Promise<void>;
}

const ACTIVE_STATUSES = new Set(['uploading', 'processing']);

const UploadMoreTab: React.FC<Props> = ({ task, onUploaded }) => {
  const [fileList, setFileList] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const isTaskBusy = ACTIVE_STATUSES.has(task.status);

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请选择要追加上传的图片');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      fileList.forEach((file) => {
        formData.append('files', file.originFileObj || file);
      });

      const result = await taskApi.uploadImages(task.id, formData);
      const uploaded = (result as any)?.uploaded ?? fileList.length;
      message.success(`已追加上传 ${uploaded} 张图片，系统开始处理新增图片`);
      setFileList([]);
      await onUploaded();
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message;
      message.error(typeof detail === 'string' ? detail : '追加上传失败');
    } finally {
      setUploading(false);
    }
  };

  const uploadProps = {
    multiple: true,
    accept: '.jpg,.jpeg,.png',
    fileList,
    disabled: isTaskBusy || uploading,
    beforeUpload: (file: any) => {
      setFileList((prev) => [...prev, file]);
      return false;
    },
    onRemove: (file: any) => {
      setFileList((prev) => prev.filter((item) => item.uid !== file.uid));
    },
  };

  return (
    <Card title="追加上传">
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Alert
          type={isTaskBusy ? 'warning' : 'info'}
          showIcon
          message={
            isTaskBusy
              ? '当前任务正在处理图片，暂不能追加上传'
              : '只处理本次新增图片'
          }
          description={
            isTaskBusy
              ? '请等待当前批次处理完成后再上传，避免多批图片同时处理导致进度和去重结果不一致。'
              : '旧图片和旧检测结果会保留；新增图片处理完成后，系统会重新汇总去重虫巢结果。'
          }
        />

        <Space size={8} wrap>
          <Tag color="green">当前图片 {task.total_images || 0}</Tag>
          <Tag color={task.status === 'completed' ? 'green' : 'orange'}>
            {task.status}
          </Tag>
          <Tag>已选择 {fileList.length}</Tag>
        </Space>

        <Upload {...uploadProps}>
          <Button icon={<UploadOutlined />} disabled={isTaskBusy || uploading}>
            选择图片
          </Button>
        </Upload>

        <Button
          type="primary"
          onClick={handleUpload}
          loading={uploading}
          disabled={isTaskBusy || fileList.length === 0}
        >
          开始追加上传
        </Button>
      </Space>
    </Card>
  );
};

export default UploadMoreTab;
