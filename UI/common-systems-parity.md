# CN 通用系统移植核对

基准：Media main，commit `601754a7b5033c3380956e2eae7f3efb433ca7d9`，以 `V6/` 运行源码及其七大系统说明为准。

## 七大系统逐项映射

| 系统 | Media 通用基准 | CN 实际文件 | A股适配边界 / 验收重点 |
|---|---|---|---|
| 1. K线 | `V6/kline/v6-kline-view.js`、`v6-vegas-ema.js`、`gate-kline-controller.js` | `site/assets/kline/v6-kline-view.js`、`v6-vegas-ema.js`、`tencent-kline-controller.js` | Canvas、DPR、ResizeObserver、手势、EMA叠加和销毁流程沿用；仅替换为腾讯前复权1D。EMA仅12/144/169/576/676。 |
| 2. 视窗与手势 | `V6/kline/v6-viewport-state.js`、`V6/modules/kline-rotation-pause.js`、共享生命周期 | `site/assets/kline/v6-viewport-state.js`、`rotation-pause.js`、`site/assets/shared/*` | 保留时间锚点、拖动、双指缩放、惯性、双击暂停、页面隐藏恢复；持久化键使用CN独立命名空间。 |
| 3. 滚动卡片 | `V6/cards/rolling-cards.js`、`rolling-cards.css` | `site/assets/rolling-cards.js`、`rolling-cards.css` | 环形布局、拖动、惯性、点选、双击暂停、动态尺寸和变化时刷新文本沿用；数据来自CN500，DOM只挂载当前信号集。A股没有完整500只股票Logo资产，因此卡片显示名称/代码，不伪造Logo。 |
| 4. Logo与倒计时 | `V6/modules/logo/logo.{html,css,js}` | `site/assets/modules/logo/logo.{html,css,js}` | 保留品牌块、名称/代码、淡入淡出和父子消息；倒计时改用A股交易日历。切换时先与K线同步淡出，数据就绪后再同步显示。 |
| 5. 周期选择 | `V6/modules/timeframe-switch/index.html`、`host.css` | `site/assets/modules/timeframe-switch/index.html`、`responsive.css`、`host.css` | 保留独立iframe、父子消息、可视状态和响应式容器；选项固定为1D，不引入其他周期。 |
| 6. 信号栏 | `V6/modules/signal-ticker/{ticker.js,v12-feed.js}` | `site/assets/modules/signal-ticker/ticker.js` | 保留连续滚动、ResizeObserver、动画时间线不因普通布局变化重启、销毁清理；信号内容由A股日线信号快照提供，不接入V12市场池。 |
| 7. 全屏动态 | `V6/assets/css/full-screen-dynamic.css`、`v6-modules.css` | `site/assets/css/full-screen-dynamic.css`、`v6-modules.css`、`app.css` | 保留动态视口、安全区、横竖屏、单一外层几何控制；CN的1D控件、底部留白和#101010容器为A股布局适配。 |

## 已确认的共享文件一致性

以下文件与Media对应文件逐字节一致：
- `site/assets/shared/lifecycle.js`
- `site/assets/shared/page-lifecycle-v6.js`
- `site/assets/kline/rotation-pause.js`
- `site/assets/rolling-cards.css`

卡片脚本、K线数据控制器、Logo、周期控件、信号栏和全屏布局不是逐字节复制；它们包含A股数据模型、1D固定周期、500只股票和交易日历适配，必须按行为契约核对，不以文件相同作为验收条件。

## A股专属模块（不从Media照搬）

- 腾讯AKShare前复权日线、十年可用历史、14日重叠增量缓存。
- 500只股票池、交易日历、每日扫描和A股信号确认。
- EMA仅过滤线EMA12、中锋EMA144/169、红峰EMA576/676。
- A股Logo信息与交易日倒计时。
- CN专属Bark通知和Pages数据快照。

## 明确排除

不移植Gate合约/行情/WebSocket、Gate品种目录、加密资产周期、Media的24品种池、V12加密/美股信号源及其专属分组。共享系统以Media为行为基准，市场数据和业务规则仍由CN独立实现。

## 本次补齐与自动验收

- K线与Logo切换改为两阶段协同：开始时同时淡出；新日K加载完成后同时显示；加载失败或中断时恢复旧Logo状态。页面从后台恢复时也等待目标日K加载，再同步显示对应Logo。
- CN卡片环形轮播速度恢复Media基准：约120秒完成一圈。
- 新增Media共享文件一致性测试和A股适配边界测试。
- 页面隐藏时中止正在进行的A股信号请求，恢复时重新核对信号；共享生命周期负责释放监听器，并保留全局错误/未处理Promise诊断。
- 历史预热与网页展示上限分开核对：后台请求最多十年并在完整历史上计算EMA；网页只展示最新1200根日K，1200不是EMA预热上限。

