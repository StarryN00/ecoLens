import React, { useState } from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import { authApi } from '../services/api';

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const data = await authApi.login(values.username, values.password);
      const token = (data as any)?.access_token;
      if (!token) {
        throw new Error('登录响应缺少 access_token');
      }
      localStorage.setItem('token', token);
      message.success('登录成功');
      navigate('/tasks');
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail || error?.message || '登录失败';
      message.error(typeof detail === 'string' ? detail : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      background: '#f0f2f5'
    }}>
      <Card title="樟巢螟智能检测系统" style={{ width: 400 }}>
        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
              size="large"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              size="large"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              loading={loading}
            >
              登录
            </Button>
          </Form.Item>
          <div style={{ textAlign: 'center' }}>
            还没有账号? <Link to="/register">立即注册</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
};

export default Login;
