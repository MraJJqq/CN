# VEGAS CN — A股独立系统

CN 以空白代码树重建；Media 为通用显示系统基准，A股数据与信号规则独立实现。

## 固定架构
- 数据：腾讯前复权日线（AKShare `stock_zh_a_hist_tx`），固定CN500，单次扫描回溯最多10年；每次完整刷新全部500只，避免前复权历史因公司行动调整后产生旧缓存偏差。任一品种失败即整次中止，不发布部分数据。
- 计算：仅 EMA12过滤线、中锋EMA144/169、红峰EMA576/676；`adjust=False`、`min_periods=span`，只用已完成日线。
- 信号：影线触碰隧道进入观察；观察K线不确认；之后的交易日收盘位于EMA12上方/下方时确认；同一股票、确认日、方向合并隧道并去重。
- 调度：交易日15:35北京时间扫描一次；盘中网页每5分钟只请求当日信号股票的腾讯实时报价更新K线，不扫描、不生成信号。
- 通知：CN独立Bark；优先使用`CN_BARK_KEY`，兼容此前CN仓库专用`A_SHARE_BARK_KEY`；服务地址可用`CN_BARK_SERVER`，默认`https://api.day.app`。交易日去重。
- 展示：Media V6 K线绘制、手势/视窗状态模块移植；EMA覆盖层仅保留A股五条均线并匹配Media颜色。全屏布局与信号卡片按Media规范适配，A股日线数据接口独立。

## 关键目录
- `scripts/cn_core.py`：日线校验、EMA、观察/确认/去重状态机。
- `scripts/daily_scan.py`：腾讯CN500全量日线获取与原子发布。
- `scripts/push_bark.py`：CN独立Bark和去重。
- `scripts/trading_calendar.py`：上交所官方休市日历；无法读取或解析时失败关闭。
- `site/assets/media/`：从Media移植的K线绘制、手势、视窗状态及视觉规范。
- `site/`：静态页面与扫描数据。
- `tests/`：规则、数据校验、发布结构测试。

## 本地验证
```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/trading_calendar.py
```
