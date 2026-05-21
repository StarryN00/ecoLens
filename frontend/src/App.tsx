import React, { useEffect, useState } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useLocation,
  useNavigate,
} from 'react-router-dom';
import {
  Avatar,
  ConfigProvider,
  Dropdown,
  Layout,
  Menu,
  Space,
  Typography,
  message,
} from 'antd';
import {
  AppstoreOutlined,
  DownOutlined,
  EnvironmentOutlined,
  LockOutlined,
  LogoutOutlined,
  PlusCircleOutlined,
  RadarChartOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import Login from './pages/Login';
import Register from './pages/Register';
import TaskList from './pages/TaskList';
import TaskCreate from './pages/TaskCreate';
import TaskDetail from './pages/TaskDetail';
import UserAdmin from './pages/admin/UserAdmin';
import RegionAdmin from './pages/admin/RegionAdmin';
import ChangePasswordModal from './components/ChangePasswordModal';
import { authApi } from './services/api';
import './App.css';

const { Header, Content } = Layout;
const { Text } = Typography;

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
          {
            key: 'admin-regions',
            label: '区域管理',
            icon: <EnvironmentOutlined />,
            onClick: () => navigate('/admin/regions'),
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
        <a onClick={(e) => e.preventDefault()} className="user-menu-trigger">
          <Space>
            <Avatar size={30} icon={<UserOutlined />} className="user-menu-avatar" />
            <span>{username || '用户'}</span>
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

const navItems = [
  {
    key: '/tasks',
    icon: <RadarChartOutlined />,
    label: '巡检任务',
  },
  {
    key: '/tasks/create',
    icon: <PlusCircleOutlined />,
    label: '新建任务',
  },
  {
    key: '/admin/regions',
    icon: <EnvironmentOutlined />,
    label: '区域管理',
  },
  {
    key: '/admin/users',
    icon: <TeamOutlined />,
    label: '用户管理',
  },
];

const getSelectedNavKey = (pathname: string) => {
  if (pathname.startsWith('/tasks/create')) return '/tasks/create';
  if (pathname.startsWith('/admin/regions')) return '/admin/regions';
  if (pathname.startsWith('/admin/users')) return '/admin/users';
  return '/tasks';
};

// 工作台布局组件
const MainLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-mark">
          <div className="brand-icon">
            <AppstoreOutlined />
          </div>
          <div>
            <div className="brand-title">樟巢螟智能检测系统</div>
            <div className="brand-subtitle">Forestry AI Console</div>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[getSelectedNavKey(location.pathname)]}
          items={navItems}
          onClick={({ key }) => navigate(key)}
          className="side-nav"
        />
      </aside>
      <Layout className="app-main">
        <Header className="app-header">
          <div>
            <Text className="app-kicker">上海林业巡检 · 遥感识别工作台</Text>
            <div className="app-header-title">虫巢风险监测与任务调度</div>
          </div>
          <UserMenu />
        </Header>
        <Content className="app-content">{children}</Content>
      </Layout>
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
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1f7a4d',
          colorInfo: '#1f7a4d',
          colorSuccess: '#2f8f5b',
          colorWarning: '#d97706',
          colorError: '#c2413b',
          colorText: '#16251d',
          colorTextSecondary: '#607065',
          colorBgLayout: '#eef4ef',
          borderRadius: 8,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
        components: {
          Card: {
            borderRadiusLG: 8,
            headerBg: '#ffffff',
          },
          Button: {
            borderRadius: 8,
            controlHeight: 36,
          },
          Table: {
            headerBg: '#f5f8f4',
            headerColor: '#294236',
            rowHoverBg: '#f4f8f4',
          },
          Tabs: {
            itemSelectedColor: '#1f7a4d',
            inkBarColor: '#1f7a4d',
          },
        },
      }}
    >
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
          <Route
            path="/admin/regions"
            element={
              <AdminRoute>
                <MainLayout>
                  <RegionAdmin />
                </MainLayout>
              </AdminRoute>
            }
          />
          <Route path="/" element={<Navigate to="/tasks" />} />
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
