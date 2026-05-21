import React, { useState } from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import { authApi } from '../services/api';

interface RegisterValues {
  username: string;
  password: string;
  email?: string;
}

const Register: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: RegisterValues) => {
    setLoading(true);
    try {
      await authApi.register({
        username: values.username,
        password: values.password,
        email: values.email || undefined,
      });
      message.success('注册成功，正在自动登录…');
      // 自动登录
      const loginResp = await authApi.login(values.username, values.password);
      const token = (loginResp as any)?.access_token;
      if (token) {
        localStorage.setItem('token', token);
        navigate('/tasks');
      } else {
        navigate('/login');
      }
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail || error?.message || '注册失败';
      message.error(typeof detail === 'string' ? detail : '注册失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <section className="auth-visual">
        <div className="auth-title">建立巡检协作账号</div>
        <div className="auth-copy">
          注册后可进入任务工作台，上传巡检影像并跟踪虫巢检测结果。管理员权限由后台脚本或管理员统一分配。
        </div>
      </section>
      <section className="auth-form-wrap">
        <Card className="auth-card" title="注册账号">
        <Form name="register" onFinish={onFinish} autoComplete="off">
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, max: 64, message: '用户名长度 3-64' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>

          <Form.Item
            name="email"
            rules={[{ type: 'email', message: '邮箱格式不正确' }]}
          >
            <Input prefix={<MailOutlined />} placeholder="邮箱（可选）" size="large" />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少 6 位' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              loading={loading}
            >
              注册
            </Button>
          </Form.Item>
          <div style={{ textAlign: 'center' }}>
            已有账号? <Link to="/login">去登录</Link>
          </div>
        </Form>
        </Card>
      </section>
    </div>
  );
};

export default Register;
