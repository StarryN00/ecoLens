import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 请求拦截器
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
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// 任务相关API
export const taskApi = {
  getTasks: () => api.get('/api/v1/tasks'),
  getTask: (id: string) => api.get(`/api/v1/tasks/${id}`),
  createTask: (data: any) => api.post('/api/v1/tasks', data),
  deleteTask: (id: string) => api.delete(`/api/v1/tasks/${id}`),
  uploadImages: (taskId: string, formData: FormData) => {
    // 使用 fetch 代替 axios，避免默认 headers 干扰 multipart 上传
    return fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}/images`, {
      method: 'POST',
      body: formData,
    }).then(res => {
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
