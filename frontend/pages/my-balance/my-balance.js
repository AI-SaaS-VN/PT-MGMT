// pages/my-balance/my-balance.js
// 客户课时余额查询页面
// API: GET /api/v1/packages?customer_id={userId}&page=1&page_size=50

const { request, buildUrl } = require('../../utils/request');
const { getCurrentUserId, logout } = require('../../utils/auth');

// 课程种类中文名映射（course_id → 名称在列表中不直接可用，用 course_type 代替）
const STATUS_LABEL = {
  paid: '已付清',
  pending: '待付款',
  partial: '部分付',
  partial_refunded: '部分退款',
  refunded: '已退款',
};

Page({
  data: {
    packages: [],      // PackageListItem[]（附加 sessions_remaining 计算字段）
    totalRemaining: 0, // 所有 paid 课包的剩余课时总和
    loading: true,
    errorMsg: '',
    userInfo: null,
  },

  onLoad() {
    const app = getApp();
    if (!app.requireLogin()) return;
    this.setData({ userInfo: app.globalData.userInfo });
    this._loadPackages();
  },

  onPullDownRefresh() {
    this._loadPackages().then(() => {
      wx.stopPullDownRefresh();
    });
  },

  async _loadPackages() {
    this.setData({ loading: true, errorMsg: '' });
    const userId = getCurrentUserId();
    if (!userId) {
      this.setData({ loading: false, errorMsg: '无法获取用户信息，请重新登录' });
      return;
    }

    try {
      const url = buildUrl('/packages', { customer_id: userId, page_size: 50 });
      const result = await request('GET', url);

      // result = PaginatedResponse: { items: [...], total, page, page_size }
      const items = (result.items || []).map((pkg) => ({
        ...pkg,
        sessions_remaining: pkg.sessions_total + pkg.sessions_gifted - pkg.sessions_used,
        status_label: STATUS_LABEL[pkg.payment_status] || pkg.payment_status,
        purchase_date_str: this._formatDate(pkg.created_at),
        expiry_str: pkg.expiry_date ? pkg.expiry_date : '不限期',
      }));

      const totalRemaining = items
        .filter((p) => p.payment_status === 'paid')
        .reduce((sum, p) => sum + p.sessions_remaining, 0);

      this.setData({ packages: items, totalRemaining, loading: false });
    } catch (err) {
      console.error('加载课包失败', err);
      this.setData({ errorMsg: err.message || '加载失败', loading: false });
    }
  },

  _formatDate(isoStr) {
    if (!isoStr) return '';
    return isoStr.slice(0, 10); // 'YYYY-MM-DD'
  },

  onLogoutTap() {
    wx.showModal({
      title: '确认退出',
      content: '退出登录后需要重新授权',
      success(res) {
        if (res.confirm) logout();
      },
    });
  },
});
