// app.js
// 全局应用入口 — 管理登录状态和全局配置

const auth = require('./utils/auth');

App({
  globalData: {
    userInfo: null,    // { id, display_name, role }
    accessToken: null,
  },

  onLaunch() {
    // 尝试从本地存储恢复 token；如果有效则无需重新登录
    const token = wx.getStorageSync('access_token');
    const userInfo = wx.getStorageSync('user_info');
    if (token && userInfo) {
      this.globalData.accessToken = token;
      this.globalData.userInfo = userInfo;
    }
  },

  // 供各页面调用：确保当前已登录，否则跳转登录页
  requireLogin() {
    if (!this.globalData.accessToken) {
      wx.reLaunch({ url: '/pages/login/login' });
      return false;
    }
    return true;
  },
});
