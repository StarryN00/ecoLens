import React from 'react';
import { Tag } from 'antd';

export const getStatusTag = (status: string) => {
  const statusMap: Record<string, { color: string; text: string }> = {
    uploading: { color: 'blue', text: '上传中' },
    processing: { color: 'orange', text: '处理中' },
    completed: { color: 'green', text: '已完成' },
    failed: { color: 'red', text: '失败' },
  };
  const { color, text } = statusMap[status] || { color: 'default', text: status };
  return <Tag color={color}>{text}</Tag>;
};

export const getSeverityTag = (severity: string) => {
  const severityMap: Record<string, { color: string; text: string }> = {
    severe: { color: 'red', text: '重度' },
    medium: { color: 'orange', text: '中度' },
    light: { color: 'green', text: '轻度' },
  };
  const { color, text } = severityMap[severity] || { color: 'default', text: severity };
  return <Tag color={color}>{text}</Tag>;
};
