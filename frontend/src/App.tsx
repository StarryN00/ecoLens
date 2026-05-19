import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Layout, Dropdown, Space, message } from 'antd';
import { UserOutlined, DownOutlined, LockOutlined, LogoutOutlined, TeamOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import Login from './pages/Login';
import Register from './pages/Register';
import TaskList from './pages/TaskList';
import TaskCreate from './pages/TaskCreate';
import TaskDetail from './pages/TaskDetail';
import UserAdmin from './pages/admin/UserAdmin';
import ChangePasswordModal from './components/ChangePasswordModal';
import { authApi } from './services/api';
import './App.css';

const { Header, Content } = Layout;

const doLogout = () => {
  localStorage.removeItem('token');
  // 完整刷新到 /login：清掉 React 内存里残留的 user 状态
  window.location.href = '/login';
};

// 右上角：当前用户名 + 下拉菜单（修改密码 / 退出登录）
const UserMenu: React.FC = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState<string>('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [pwdModalOpen, setPwdModalOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    authApi
      .getMe()
      .then((data: any) => {
        if (!cancelled && data?.username) {
          setUsername(data.username);
          setIsAdmin(data.is_admin === true);
        }
      })
      .catch(() => {
        // 401 已被 api.ts 拦截器处理；这里静默
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const items: MenuProps['items'] = [
    ...(isAdmin
      ? [
          {
            key: 'admin-users',
            label: '用户管理',
            icon: <TeamOutlined />,
            onClick: () => navigate('/admin/users'),
          },
          { type: 'divider' as const },
        ]
      : []),
    {
      key: 'change-password',
      label: '修改密码',
      icon: <LockOutlined />,
      onClick: () => setPwdModalOpen(true),
    },
    { type: 'divider' },
    {
      key: 'logout',
      label: '退出登录',
      icon: <LogoutOutlined />,
      danger: true,
      onClick: () => {
        message.success('已退出登录');
        doLogout();
      },
    },
  ];

  return (
    <>
      <Dropdown menu={{ items }} trigger={['click']}>
        <a onClick={(e) => e.preventDefault()} style={{ color: 'rgba(0,0,0,0.85)' }}>
          <Space>
            <UserOutlined />
            {username || '用户'}
            <DownOutlined style={{ fontSize: 10 }} />
          </Space>
        </a>
      </Dropdown>
      <ChangePasswordModal
        open={pwdModalOpen}
        onClose={() => setPwdModalOpen(false)}
        onSuccess={doLogout}
      />
    </>
  );
};

// 简单的布局组件
const MainLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <h1 style={{ margin: 0, fontSize: 18 }}>樟巢螟智能检测系统</h1>
        <UserMenu />
      </Header>
      <Content style={{ padding: '24px', background: '#f0f2f5' }}>
        {children}
      </Content>
    </Layout>
  );
};

// 路由守卫
const PrivateRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? <>{children}</> : <Navigate to="/login" />;
};

// 管理员路由守卫：在 PrivateRoute 基础上加 is_admin 检查
const AdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('token');
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    if (!token) {
      setIsAdmin(false);
      return;
    }
    authApi
      .getMe()
      .then((data: any) => setIsAdmin(data?.is_admin === true))
      .catch(() => setIsAdmin(false));
  }, [token]);

  if (!token) return <Navigate to="/login" replace />;
  if (isAdmin === null) return null;
  if (!isAdmin) return <Navigate to="/tasks" replace />;
  return <>{children}</>;
};

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/tasks"
          element={
            <PrivateRoute>
              <MainLayout>
                <TaskList />
              </MainLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/tasks/create"
          element={
            <PrivateRoute>
              <MainLayout>
                <TaskCreate />
              </MainLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/tasks/:id"
          element={
            <PrivateRoute>
              <MainLayout>
                <TaskDetail />
              </MainLayout>
            </PrivateRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <AdminRoute>
              <MainLayout>
                <UserAdmin />
              </MainLayout>
            </AdminRoute>
          }
        />
        <Route path="/" element={<Navigate to="/tasks" />} />
      </Routes>
    </Router>
  );
}

export default App;
