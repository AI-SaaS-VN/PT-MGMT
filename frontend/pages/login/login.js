// pages/login/login.js
const auth = require('../../utils/auth');

Page({
  data: {
    loading: false,
    errorMsg: '',
  },

  onLoad() {
    // 如果已有有效 token，直接跳过登录页
    const app = getApp();
    if (app.globalData.accessToken) {
      this._goMain();
    }
  },

  // 点击"微信一键登录"按钮
  async onLoginTap() {
    if (this.data.loading) return;
    this.setData({ loading: true, errorMsg: '' });

    try {
      await auth.login();
      this._goMain();
    } catch (err) {
      console.error('登录失败', err);
      this.setData({ errorMsg: err.message || '登录失败，请重试' });
    } finally {
      this.setData({ loading: false });
    }
  },

  _goMain() {
    wx.switchTab({ url: '/pages/my-balance/my-balance' });
  },
});
