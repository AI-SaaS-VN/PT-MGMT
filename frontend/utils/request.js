// utils/request.js
// 封装 wx.request，统一处理 Authorization header 和错误响应

const BASE_URL = 'http://localhost:8000/api/v1'; // 开发环境；生产环境替换为真实域名

/**
 * 发起 HTTP 请求
 * @param {string} method   HTTP 方法 (GET | POST | PATCH | DELETE)
 * @param {string} path     API 路径，如 '/packages'
 * @param {object} [data]   请求体（POST/PATCH）或查询参数（GET）
 * @returns {Promise<any>}  解析后的响应 data 字段
 */
function request(method, path, data) {
  return new Promise((resolve, reject) => {
    const app = getApp();
    const token = app.globalData.accessToken || wx.getStorageSync('access_token');

    const header = {
      'Content-Type': 'application/json',
    };
    if (token) {
      header['Authorization'] = `Bearer ${token}`;
    }

    // GET 请求将 data 作为 query string，POST/PATCH 作为 body
    const isGetLike = method === 'GET' || method === 'DELETE';

    wx.request({
      url: BASE_URL + path,
      method,
      header,
      data: isGetLike ? undefined : data,
      // wx.request 的 GET query params 通过 url 拼接
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          // 后端统一格式：{ success: true, data: ... }
          resolve(res.data.data ?? res.data);
        } else if (res.statusCode === 401) {
          // Token 失效 → 清除并跳转登录
          wx.removeStorageSync('access_token');
          wx.removeStorageSync('user_info');
          getApp().globalData.accessToken = null;
          wx.reLaunch({ url: '/pages/login/login' });
          reject(new Error('未登录或 token 已过期'));
        } else {
          const msg = res.data?.detail || res.data?.message || `请求失败 (${res.statusCode})`;
          reject(new Error(msg));
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误'));
      },
    });
  });
}

/**
 * 构造带查询参数的 URL
 * @param {string} path
 * @param {object} params
 * @returns {string}
 */
function buildUrl(path, params = {}) {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  return qs ? `${path}?${qs}` : path;
}

module.exports = { request, buildUrl };
