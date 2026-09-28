# 竞彩赔率分析工具

自动采集中国体彩竞彩足球赔率，做概率分析、赔率异动监控和2串1推荐。

## 功能

| 命令 | 作用 |
|---|---|
| `python3 sporttery_client.py fetch` | 拉取今日全部场次赔率，存 SQLite |
| `python3 sporttery_client.py list` | 列表查看所有场次 |
| `python3 sporttery_client.py show 周六007` | 查看单场五种玩法明细 |
| `python3 sporttery_client.py compare` | 对比最近两次快照，列赔率异动 |
| `python3 sporttery_client.py analyze` | 胜平负赔率去水，算机构概率 |
| `python3 sporttery_client.py report` | 每日简报：概率+预期进球+格局 |
| `python3 sporttery_client.py picks` | 自动推荐2串1：稳胆+让球不败 |

## 安装

```bash
pip install -r requirements.txt
python3 sporttery_client.py fetch
python3 sporttery_client.py report
```

## 数据来源

体彩竞彩官网移动端接口 `webapi.sporttery.cn`（公开未公开API），覆盖胜平负/让球/比分/总进球/半全场。

## 自动运行

GitHub Actions 每小时跑一次 `fetch`，自动提交快照到本仓库。
在仓库 Settings → Actions → General 里允许 "Read and write permissions"。

## 免责

仅供个人学习研究，不构成投注建议。竞彩返还率约88.5%，长期购彩数学上负收益，请理性娱乐。
