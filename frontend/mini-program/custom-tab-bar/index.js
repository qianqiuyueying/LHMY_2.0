const TAB_LIST = [
  { 
    pagePath: "pages/index/index", 
    text: "首页",
    iconPath: "/tabbar/home.png",
    selectedIconPath: "/tabbar/home-active.png"
  },
  { 
    pagePath: "pages/mall/mall", 
    text: "商城",
    iconPath: "/tabbar/mall.png",
    selectedIconPath: "/tabbar/mall-active.png"
  },
  { 
    pagePath: "pages/entitlement/entitlement", 
    text: "权益",
    iconPath: "/tabbar/ticket.png",
    selectedIconPath: "/tabbar/ticket-active.png"
  },
  { 
    pagePath: "pages/order/order", 
    text: "订单",
    iconPath: "/tabbar/list.png",
    selectedIconPath: "/tabbar/list-active.png"
  },
  { 
    pagePath: "pages/profile/profile", 
    text: "我的",
    iconPath: "/tabbar/profile.png",
    selectedIconPath: "/tabbar/profile-active.png"
  }
];

Component({
  data: {
    selected: 0,
    list: TAB_LIST
  },

  methods: {
    onTap(e) {
      const { path, index } = e.currentTarget.dataset || {};
      if (!path) return;

      const targetIndex = Number(index) || 0;
      if (targetIndex === this.data.selected) return;

      const prevSelected = this.data.selected;
      this.setData({ selected: targetIndex });

      wx.switchTab({
        url: `/${path}`,
        fail: (err) => {
          // 切换失败时回滚选中态，避免 UI 假成功
          this.setData({ selected: prevSelected });
          console.error('切换Tab失败:', err);
        },
      });
    }
  }
});
