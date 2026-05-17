import axios from 'axios';

// 使用相对路径，让 nginx 代理处理 API 请求
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 请求拦截器：自动附加 Bearer token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      // 避免在已经位于 /login 或 /register 时还跳一次
      const path = window.location.pathname;
      if (path !== '/login' && path !== '/register') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// 认证相关 API
export const authApi = {
  // 登录使用 application/x-www-form-urlencoded（OAuth2PasswordRequestForm 要求）
  login: (username: string, password: string) => {
    const body = new URLSearchParams();
    body.append('username', username);
    body.append('password', password);
    return api.post('/api/v1/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
  },
  register: (data: { username: string; password: string; email?: string }) =>
    api.post('/api/v1/auth/register', data),
  getMe: () => api.get('/api/v1/auth/me'),
};

// 任务相关API
export const taskApi = {
  getTasks: () => api.get('/api/v1/tasks'),
  getTask: (id: string) => api.get(`/api/v1/tasks/${id}`),
  createTask: (data: any) => api.post('/api/v1/tasks', data),
  deleteTask: (id: string) => api.delete(`/api/v1/tasks/${id}`),
  uploadImages: (taskId: string, formData: FormData) => {
    // 使用 fetch 代替 axios，避免默认 headers 干扰 multipart 上传
    // 手动附加 Authorization
    const token = localStorage.getItem('token');
    const headers: Record<string, string> = {};
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}/images`, {
      method: 'POST',
      body: formData,
      headers,
    }).then(res => {
      if (res.status === 401) {
        localStorage.removeItem('token');
        window.location.href = '/login';
        throw new Error('未授权');
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });
  },
  // 新增API
  getTaskResults: (id: string) => api.get(`/api/v1/tasks/${id}/results`),
  getTaskNests: (id: string) => api.get(`/api/v1/tasks/${id}/nests`),
  getTaskImages: (id: string) => api.get(`/api/v1/tasks/${id}/images`),
  getTaskStatistics: (id: string) => api.get(`/api/v1/tasks/${id}/statistics`),
  getNestDetail: (id: string) => api.get(`/api/v1/nests/${id}`),
};

// 图片相关API
export const imageApi = {
  getImage: (id: string) => api.get(`/api/v1/images/${id}`),
  getThumbnail: (id: string) => `${API_BASE_URL}/api/v1/images/${id}/thumbnail`,
  getAnnotated: (id: string) => `${API_BASE_URL}/api/v1/images/${id}/annotated`,
};

export default api;
