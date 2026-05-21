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

type DataApi = {
  get<T = any>(url: string, config?: any): Promise<T>;
  post<T = any>(url: string, data?: any, config?: any): Promise<T>;
  put<T = any>(url: string, data?: any, config?: any): Promise<T>;
  delete<T = any>(url: string, config?: any): Promise<T>;
};

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

const request = api as unknown as DataApi;

// 认证相关 API
export const authApi = {
  // 登录使用 application/x-www-form-urlencoded（OAuth2PasswordRequestForm 要求）
  login: (username: string, password: string) => {
    const body = new URLSearchParams();
    body.append('username', username);
    body.append('password', password);
    return request.post('/api/v1/auth/login', body, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
  },
  register: (data: { username: string; password: string; email?: string }) =>
    request.post('/api/v1/auth/register', data),
  getMe: () => request.get('/api/v1/auth/me'),
  changePassword: (data: { old_password: string; new_password: string }) =>
    request.post('/api/v1/auth/change-password', data),
};

// 任务相关API
export const taskApi = {
  // params 支持 { skip, limit, status, region_id } —— region_id 过滤在后端 WHERE
  getTasks: (params?: Record<string, unknown>) =>
    request.get('/api/v1/tasks', { params }),
  getTask: (id: string) => request.get(`/api/v1/tasks/${id}`),
  createTask: (data: any) => request.post('/api/v1/tasks', data),
  deleteTask: (id: string) => request.delete(`/api/v1/tasks/${id}`),
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
  getTaskResults: (id: string) => request.get(`/api/v1/tasks/${id}/results`),
  getTaskNests: (id: string) => request.get(`/api/v1/tasks/${id}/nests`),
  getTaskImages: (id: string) => request.get(`/api/v1/tasks/${id}/images`),
  getTaskStatus: (id: string) => request.get(`/api/v1/tasks/${id}/status`),
  getTaskStatistics: (id: string) => request.get(`/api/v1/tasks/${id}/statistics`),
  getNestDetail: (id: string) => request.get(`/api/v1/nests/${id}`),
};

/**
 * 获取需要鉴权的二进制资源（图片等），返回浏览器内的 blob URL。
 *
 * 后端 /api/v1/images/* 接口在 Team A 的安全加固后强制要求 Bearer token，
 * 但浏览器原生的 <img src> 不会自动带上 Authorization 头，因此直接把
 * `/api/v1/images/{id}` 拼到 src 上会得到 401。本函数用 fetch 显式带 token
 * 取回 blob，再通过 URL.createObjectURL 把它包成一个临时 URL 给 <img> 用。
 *
 * 调用方必须负责在组件卸载/URL 更新时调用 URL.revokeObjectURL 释放内存。
 */
export async function fetchAuthedImageUrl(path: string): Promise<string> {
  const token = localStorage.getItem('token');
  const headers: Record<string, string> = {};
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (res.status === 401) {
    localStorage.removeItem('token');
    const p = window.location.pathname;
    if (p !== '/login' && p !== '/register') {
      window.location.href = '/login';
    }
    throw new Error('未授权');
  }
  if (!res.ok) {
    throw new Error(`Image fetch failed: ${res.status}`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// 图片相关API
export const imageApi = {
  /**
   * @deprecated 返回的是裸 URL，<img src> 不会自动带 Bearer token，会 401。
   * 请改用 `imageApi.fetchImage(id)` 拿到 blob URL 再交给 <img>。
   */
  getImage: (id: string) => api.get(`/api/v1/images/${id}`),
  /**
   * @deprecated 返回的是裸 URL，<img src> 不会自动带 Bearer token，会 401。
   * 请改用 `imageApi.fetchThumbnail(id)` 拿到 blob URL 再交给 <img>。
   */
  getThumbnail: (id: string) => `${API_BASE_URL}/api/v1/images/${id}/thumbnail`,
  /**
   * @deprecated 返回的是裸 URL，<img src> 不会自动带 Bearer token，会 401。
   * 请改用 `imageApi.fetchAnnotated(id)` 拿到 blob URL 再交给 <img>。
   */
  getAnnotated: (id: string) => `${API_BASE_URL}/api/v1/images/${id}/annotated`,

  // 推荐用法：返回 blob URL，调用方负责 URL.revokeObjectURL 清理
  fetchImage: (id: string) => fetchAuthedImageUrl(`/api/v1/images/${id}`),
  fetchThumbnail: (id: string) =>
    fetchAuthedImageUrl(`/api/v1/images/${id}/thumbnail`),
  fetchAnnotated: (id: string) =>
    fetchAuthedImageUrl(`/api/v1/images/${id}/annotated`),
};

// 管理员用户管理 API (T8)
export const adminApi = {
  listUsers: (skip = 0, limit = 50) =>
    request.get('/api/v1/admin/users', { params: { skip, limit } }),
  createUser: (data: {
    username: string;
    password: string;
    email?: string;
    is_admin?: boolean;
  }) => request.post('/api/v1/admin/users', data),
  updateUser: (
    id: string,
    data: { is_active?: boolean; is_admin?: boolean; new_password?: string },
  ) => request.put(`/api/v1/admin/users/${id}`, data),
  deleteUser: (id: string) => request.delete(`/api/v1/admin/users/${id}`),
};

// 行政区域 API (T1 多级目录架构：市/区/街镇 三级树)
export const regionApi = {
  // 完整三级树：[{...city, children:[{...district, children:[town]}]}]
  getTree: () => api.get('/api/v1/regions/tree'),
  // 分层查询
  list: (params?: { level?: string; parent_id?: string }) =>
    request.get('/api/v1/regions/', { params }),
  create: (data: { name: string; level: string; parent_id?: string }) =>
    request.post('/api/v1/regions/', data),
  update: (id: string, data: { name: string }) =>
    request.put(`/api/v1/regions/${id}`, data),
  remove: (id: string) => request.delete(`/api/v1/regions/${id}`),
};

export default api;
