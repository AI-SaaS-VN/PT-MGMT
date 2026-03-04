// utils/auth.js
// 微信登录流程：wx.login → code → 后端 /auth/wx-login → 存储 token

const { request } = require('./request');

/**
 * 完整登录流程：
 * 1. wx.login() 获取临时 code
 * 2. POST /auth/wx-login 换取 access_token + refresh_token
 * 3. 将 token 和用户信息写入 globalData 和本地存储
 *
 * @returns {Promise<{ access_token, user }>}
 */
function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(loginRes) {
        if (!loginRes.code) {
          reject(new Error('wx.login 失败：' + loginRes.errMsg));
          return;
        }

        request('POST', '/auth/wx-login', { code: loginRes.code })
          .then((data) => {
            // data = { access_token, refresh_token, user: { id, display_name, role, ... } }
            const app = getApp();
            app.globalData.accessToken = data.access_token;
            app.globalData.userInfo = data.user;

            wx.setStorageSync('access_token', data.access_token);
            wx.setStorageSync('refresh_token', data.refresh_token);
            wx.setStorageSync('user_info', data.user);

            resolve(data);
          })
          .catch(reject);
      },
      fail(err) {
        reject(new Error('wx.login 调用失败：' + err.errMsg));
      },
    });
  });
}

/**
 * 登出：清除本地 token 和 globalData
 */
function logout() {
  const app = getApp();
  app.globalData.accessToken = null;
  app.globalData.userInfo = null;
  wx.removeStorageSync('access_token');
  wx.removeStorageSync('refresh_token');
  wx.removeStorageSync('user_info');
  wx.reLaunch({ url: '/pages/login/login' });
}

/**
 * 获取当前用户 ID（UUID 字符串）
 * @returns {string|null}
 */
function getCurrentUserId() {
  const userInfo = getApp().globalData.userInfo || wx.getStorageSync('user_info');
  return userInfo ? userInfo.id : null;
}

module.exports = { login, logout, getCurrentUserId };
