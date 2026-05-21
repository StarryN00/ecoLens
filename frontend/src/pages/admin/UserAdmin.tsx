import React, { useEffect, useState } from 'react';
import {
  Table,
  Button,
  Tag,
  Space,
  Card,
  Modal,
  Form,
  Input,
  Switch,
  Popconfirm,
  message,
} from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { adminApi } from '../../services/api';

interface UserRecord {
  id: string;
  username: string;
  email: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string | null;
}

const UserAdmin: React.FC = () => {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data: any = await adminApi.listUsers();
      setUsers(data.items || []);
    } catch {
      message.error('获取用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields();
      setSubmitting(true);
      await adminApi.createUser(values);
      message.success('用户创建成功');
      setCreateOpen(false);
      createForm.resetFields();
      fetchUsers();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = async () => {
    try {
      const values = await editForm.validateFields();
      setSubmitting(true);
      const payload: Record<string, unknown> = {};
      if (values.is_active !== undefined) payload.is_active = values.is_active;
      if (values.is_admin !== undefined) payload.is_admin = values.is_admin;
      if (values.new_password) payload.new_password = values.new_password;
      await adminApi.updateUser(editingUser!.id, payload);
      message.success('用户更新成功');
      setEditOpen(false);
      fetchUsers();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async (user: UserRecord) => {
    try {
      await adminApi.updateUser(user.id, { is_active: !user.is_active });
      message.success(user.is_active ? '已禁用用户' : '已启用用户');
      fetchUsers();
    } catch {
      message.error('操作失败');
    }
  };

  const openEdit = (record: UserRecord) => {
    setEditingUser(record);
    editForm.setFieldsValue({
      is_active: record.is_active,
      is_admin: record.is_admin,
      new_password: '',
    });
    setEditOpen(true);
  };

  const columns = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      render: (v: string | null) => v || '—',
    },
    {
      title: '角色',
      key: 'is_admin',
      render: (_: unknown, r: UserRecord) => (
        <Tag color={r.is_admin ? 'gold' : 'blue'}>
          {r.is_admin ? '管理员' : '普通用户'}
        </Tag>
      ),
    },
    {
      title: '状态',
      key: 'is_active',
      render: (_: unknown, r: UserRecord) => (
        <Tag color={r.is_active ? 'green' : 'red'}>
          {r.is_active ? '正常' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string | null) => (v ? v.slice(0, 10) : '—'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: UserRecord) => (
        <Space>
          <Button size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title={record.is_active ? '确认禁用该用户？' : '确认启用该用户？'}
            onConfirm={() => handleToggleActive(record)}
            okText="确认"
            cancelText="取消"
          >
            <Button size="small" danger={record.is_active}>
              {record.is_active ? '禁用' : '启用'}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="eco-page">
      <div className="eco-page-header">
        <div>
          <div className="eco-eyebrow">Access Control</div>
          <h1 className="eco-page-title">用户管理</h1>
          <div className="eco-page-desc">
            管理系统账号、管理员权限和账号启用状态，保障巡检数据访问边界清晰。
          </div>
        </div>
        <div className="eco-actions">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateOpen(true)}
          >
            创建用户
          </Button>
        </div>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <div className="metric-label">账号总数</div>
          <div className="metric-value">{users.length}</div>
          <div className="metric-hint">系统内已创建账号</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">管理员</div>
          <div className="metric-value">{users.filter((u) => u.is_admin).length}</div>
          <div className="metric-hint">拥有后台管理权限</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">正常账号</div>
          <div className="metric-value">{users.filter((u) => u.is_active).length}</div>
          <div className="metric-hint">可登录使用</div>
        </div>
        <div className="metric-card risk">
          <div className="metric-label">禁用账号</div>
          <div className="metric-value">{users.filter((u) => !u.is_active).length}</div>
          <div className="metric-hint">已暂停访问</div>
        </div>
      </div>

      <Card className="eco-panel" title="账号列表">
        <Table
          dataSource={users}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20 }}
          scroll={{ x: 760 }}
        />

      <Modal
        title="创建用户"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => {
          setCreateOpen(false);
          createForm.resetFields();
        }}
        confirmLoading={submitting}
        destroyOnHidden
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, min: 3, message: '用户名至少3个字符' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, min: 6, message: '密码至少6个字符' }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input />
          </Form.Item>
          <Form.Item name="is_admin" label="角色" valuePropName="checked">
            <Switch checkedChildren="管理员" unCheckedChildren="普通用户" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑用户：${editingUser?.username || ''}`}
        open={editOpen}
        onOk={handleEdit}
        onCancel={() => setEditOpen(false)}
        confirmLoading={submitting}
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="is_active" label="账号状态" valuePropName="checked">
            <Switch checkedChildren="正常" unCheckedChildren="禁用" />
          </Form.Item>
          <Form.Item name="is_admin" label="角色" valuePropName="checked">
            <Switch checkedChildren="管理员" unCheckedChildren="普通用户" />
          </Form.Item>
          <Form.Item name="new_password" label="重置密码">
            <Input.Password placeholder="留空则不修改密码" />
          </Form.Item>
        </Form>
      </Modal>
      </Card>
    </div>
  );
};

export default UserAdmin;
