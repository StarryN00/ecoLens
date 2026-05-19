import React from 'react';
import { Card, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { Nest } from '../../types/task';
import { getSeverityTag } from './taskUtils';

interface Props {
  nests: Nest[];
  loading: boolean;
}

const nestColumns: ColumnsType<Nest> = [
  { title: '编号', dataIndex: 'nest_code', key: 'nest_code' },
  { title: '经度', dataIndex: 'longitude', key: 'longitude', render: (v: number) => v?.toFixed(6) },
  { title: '纬度', dataIndex: 'latitude', key: 'latitude', render: (v: number) => v?.toFixed(6) },
  { title: '严重程度', dataIndex: 'severity', key: 'severity', render: getSeverityTag },
  { title: '置信度', dataIndex: 'confidence', key: 'confidence', render: (v: number) => `${(v * 100).toFixed(1)}%` },
  { title: '检测次数', dataIndex: 'detection_count', key: 'detection_count' },
];

const NestListTab: React.FC<Props> = ({ nests, loading }) => (
  <Card title="虫巢列表" loading={loading}>
    <Table columns={nestColumns} dataSource={nests} rowKey="id" pagination={{ pageSize: 10 }} />
  </Card>
);

export default NestListTab;
