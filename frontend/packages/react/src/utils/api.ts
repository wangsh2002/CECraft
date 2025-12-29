import axios from "axios";

// 动态获取 API 地址：使用当前访问的主机名，端口固定为 8000
// 这样无论是本地开发(localhost)还是云服务器访问(IP/域名)，都能正确指向后端
const API_URL = `${window.location.protocol}//${window.location.hostname}:8000/api`;

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem("token");
      // Optionally redirect to login or dispatch an event
    }
    return Promise.reject(error);
  }
);
