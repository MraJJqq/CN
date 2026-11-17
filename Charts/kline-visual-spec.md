# K 线视觉规范

当前 CN 实现：`site/assets/kline/v6-kline-view.js` 与 `site/assets/kline/v6-vegas-ema.js`。

- 图表背景透明，承接页面底层背景。
- 网格线、十字光标及价格/时间刻度轴不绘制。
- EMA 仅使用 EMA12、EMA144、EMA169、EMA576、EMA676；颜色以同目录 `ema-colors.json` 为准。
- EMA12 为过滤线；EMA144/169 为中锋；EMA576/676 为红峰。
- 上涨蜡烛使用 `#22b07d`；下跌蜡烛使用 `#e5484d`。
- EMA 绘制由独立覆盖层完成，不改变 K 线数据或视窗状态。
