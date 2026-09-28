#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
体彩竞彩足球数据抓取器
- 数据源：中国体彩竞彩官网移动端接口（未公开 Web API）
- 覆盖玩法：胜平负(had) / 让球胜平负(hhad) / 比分(crs) / 总进球(ttg) / 半全场(hafu)
- 输出：JSON 文件 + SQLite 数据库
用法：
    python sporttery_client.py fetch              # 拉取今日受注场次并存库
    python sporttery_client.py list               # 列出今日全部场次+赔率
    python sporttery_client.py show 周六007        # 查看某场完整赔率
    python sporttery_client.py compare [0.05]      # 对比最近两次抓取，列赔率异动(默认变动≥5%)
    python sporttery_client.py analyze            # 赔率去水，算每场胜平负机构概率与返还率
    python sporttery_client.py report            # 每日简报：概率+预期进球+格局判断
    python sporttery_client.py picks            # 自动推荐2串1：稳胆+让球不败组合
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

import requests

BASE = "https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://m.sporttery.cn/",
    "Origin": "https://m.sporttery.cn",
}
POOLS = "had,hhad,crs,ttg,hafu"
DB_PATH = Path(__file__).parent / "sporttery.db"

# 半全场字段映射：首字母=半场，次字母=全场 (h=主胜/胜, d=平, a=客胜/负)
HAFU_MAP = {"hh": "胜胜", "hd": "胜平", "ha": "胜负",
            "dh": "平胜", "dd": "平平", "da": "平负",
            "ah": "负胜", "ad": "负平", "aa": "负负"}
# 总进球字段映射
TTG_MAP = {f"s{i}": f"{i}球" if i < 7 else "7+球" for i in range(8)}


def fetch_matches():
    """拉取竞彩受注场次及全部玩法赔率。"""
    params = {"poolCode": POOLS, "channel": "c"}
    r = requests.get(BASE, params=params, headers=HEADERS, timeout=25)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"接口返回失败: {payload.get('errorMessage')}")
    matches = []
    for day in payload.get("value", {}).get("matchInfoList", []) or []:
        for m in day.get("subMatchList", []):
            matches.append(_parse_match(m))
    return matches


def _f(v):
    """安全转 float，失败返回 None。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_match(m):
    """把原始 JSON 解析成干净的结构。"""
    had = m.get("had") or {}
    hhad = m.get("hhad") or {}
    ttg = m.get("ttg") or {}
    crs = m.get("crs") or {}
    hafu = m.get("hafu") or {}

    # 胜平负
    spf = {"主胜": _f(had.get("h")), "平": _f(had.get("d")), "客胜": _f(had.get("a"))}
    # 让球胜平负
    rq = {"让球数": _f(hhad.get("goalLineValue")),
          "让球主胜": _f(hhad.get("h")), "让球平": _f(hhad.get("d")),
          "让球客胜": _f(hhad.get("a"))} if hhad else None
    # 总进球
    goals = {label: _f(ttg.get(k)) for k, label in TTG_MAP.items() if ttg.get(k)}
    # 半全场
    half_full = {HAFU_MAP[k]: _f(hafu.get(k))
                 for k in HAFU_MAP if hafu.get(k)}
    # 比分（只保留有赔率的）
    score = {}
    for k, v in crs.items():
        if k.startswith("s") and k[1:].isdigit() and v not in ("0", "", None):
            home, away = int(k[1:3]), int(k[3:5])
            score[f"{home}:{away}"] = _f(v)

    return {
        "match_id": m.get("matchId"),
        "match_num": m.get("matchNumStr"),        # 周六007
        "league": m.get("leagueAbbName"),          # 亚运男足
        "league_full": m.get("leagueAllName"),
        "home": m.get("homeTeamAllName"),
        "away": m.get("awayTeamAllName"),
        "home_rank": m.get("homeRank"),
        "away_rank": m.get("awayRank"),
        "match_time": f"{m.get('matchDate')} {m.get('matchTime','')}",
        "status": m.get("matchStatus"),            # Selling / 已开赛 / 结束
        "spf": spf,                                # 胜平负
        "rqspf": rq,                               # 让球胜平负
        "ttg": goals,                              # 总进球
        "hafu": half_full,                         # 半全场
        "crs": score,                              # 比分
        "crawl_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS odds_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER, match_num TEXT, league TEXT,
            home TEXT, away TEXT, match_time TEXT, status TEXT,
            data TEXT, crawled_at TEXT
        )""")
    conn.commit()
    return conn


def save(matches):
    # 存 JSON
    out = Path(__file__).parent / "matches.json"
    out.write_text(json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8")
    # 存 SQLite
    conn = init_db()
    for m in matches:
        conn.execute(
            "INSERT INTO odds_snapshot(match_id,match_num,league,home,away,match_time,status,data,crawled_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (m["match_id"], m["match_num"], m["league"], m["home"], m["away"],
             m["match_time"], m["status"], json.dumps(m, ensure_ascii=False), m["crawl_time"]))
    conn.commit()
    conn.close()
    print(f"已保存 {len(matches)} 场 -> {out} 与 {DB_PATH}")


def devig(odds_dict):
    """把一组赔率去水归一化，返回 {选项: 公平概率%} 和返还率。"""
    inv = {k: 1 / v for k, v in odds_dict.items() if v}
    total = sum(inv.values())
    probs = {k: v / total * 100 for k, v in inv.items()}
    return probs, 1 / total * 100  # 返还率%


def cmd_analyze(matches, top=None):
    """对每场胜平负赔率去水，算出机构真实概率和返还率。"""
    rows = []
    for m in matches:
        s = m["spf"]
        if not s.get("主胜"):
            continue
        probs, ret = devig({"主胜": s["主胜"], "平": s["平"], "客胜": s["客胜"]})
        rows.append((m, s, probs, ret))
    # 按返还率排序（返还率越高=水钱越少，越"划算"）
    rows.sort(key=lambda x: -x[3])
    if top:
        rows = rows[:top]
    print(f"{'场次':<8}{'对阵':<20}{'主胜%':>7}{'平%':>7}{'客胜%':>7}{'返还率':>8}")
    print("-" * 65)
    for m, s, p, ret in rows:
        vs = f'{m["home"]}vs{m["away"]}'
        print(f'{m["match_num"]:<8}{vs:<20}{p["主胜"]:>6.1f}%{p["平"]:>6.1f}%'
              f'{p["客胜"]:>6.1f}%{ret:>7.1f}%')
    print("\n解读：返还率=体彩把多少钱返回来（越高越好）；三项概率之和=100%。")
    print("概率最高项即机构最看好的结果；概率差距小=势均力敌，差距大=强弱分明。")


def expected_goals(ttg):
    """从总进球赔率去水，算出机构预期的全场总进球数。"""
    if not ttg:
        return None
    inv = {k: 1 / v for k, v in ttg.items() if v}
    total = sum(inv.values())
    eg = 0.0
    for k, iv in inv.items():
        p = iv / total
        n = 7.5 if k.startswith("7") else float(k.replace("球", ""))
        eg += n * p
    return eg


def verdict(p):
    """根据三项概率给出一句话判断。"""
    items = sorted(p.items(), key=lambda x: -x[1])
    top_name, top_v = items[0]
    gap = top_v - items[1][1]
    if top_v >= 60:
        return f"强弱分明·{top_name}{top_v:.0f}%"
    if gap < 6:
        return f"势均力敌·冷门温床"
    return f"略偏{top_name}{top_v:.0f}%"


def cmd_report(matches):
    """每日分析简报：概率 + 预期进球 + 格局判断。"""
    rows = []
    for m in matches:
        s = m["spf"]
        if not s.get("主胜"):
            continue
        p, ret = devig({"主胜": s["主胜"], "平": s["平"], "客胜": s["客胜"]})
        eg = expected_goals(m.get("ttg"))
        rows.append((m, p, eg))
    # 按最高概率排序（强弱分明的在前）
    rows.sort(key=lambda x: -max(x[1].values()))
    print(f"{'场次':<8}{'对阵':<20}{'主%':>6}{'平%':>6}{'客%':>6}{'预期球':>7}  格局")
    print("-" * 78)
    for m, p, eg in rows:
        vs = f'{m["home"]}vs{m["away"]}'
        eg_s = f"{eg:.2f}" if eg else "-"
        print(f'{m["match_num"]:<8}{vs:<20}{p["主胜"]:>5.0f}%{p["平"]:>5.0f}%'
              f'{p["客胜"]:>5.0f}%{eg_s:>7}  {verdict(p)}')
    print("\n预期球=由总进球赔率反推的全场预期进球数（>2.8偏对攻，<2.2偏小球）。")
    print("格局=基于胜平负概率：≥60%热门、前两名差<6%视为势均力敌易出冷。")


def cmd_picks(matches):
    """自动推荐2串1：稳胆(热门≥55%) + 让球不败(赔率1.4-1.8)。"""
    bankers, handicap_safe = [], []
    for m in matches:
        s = m["spf"]
        if not s.get("主胜"):
            continue
        p, _ = devig({"主胜": s["主胜"], "平": s["平"], "客胜": s["客胜"]})
        # 稳胆：胜平负热门方概率≥55%，赔率1.25-1.70
        for name, key in (("主胜", "主胜"), ("客胜", "客胜")):
            if p[key] >= 55 and 1.25 <= s[key] <= 1.70:
                side = m["home"] if key == "主胜" else m["away"]
                bankers.append((m, key, s[key], p[key], side))
        # 让球不败：让球盘中赔率最低的一边（1.4-1.8），即受让方+1不败
        r = m.get("rqspf") or {}
        if r and r.get("让球数") is not None:
            opts = [("让球主胜", r["让球主胜"], m["home"]),
                    ("让球客胜", r["让球客胜"], m["away"])]
            for label, odd, side in opts:
                if odd and 1.40 <= odd <= 1.80:
                    handicap_safe.append((m, label, odd, side, r["让球数"]))

    print("=" * 60)
    print("【稳胆候选】胜平负热门方（概率≥55%，赔率1.25-1.70）")
    print("-" * 60)
    if not bankers:
        print("  今日无合格稳胆")
    for m, k, odd, prob, side in bankers:
        print(f"  {m['match_num']} {m['home']}vs{m['away']}  "
              f"买{k}({side}) @{odd:.2f}  概率{prob:.0f}%")

    print("\n【让球不败候选】赔率1.40-1.80（受让方+1不败）")
    print("-" * 60)
    if not handicap_safe:
        print("  今日无合格让球选项")
    for m, label, odd, side, line in handicap_safe:
        print(f"  {m['match_num']} {m['home']}vs{m['away']}  "
              f"买{label}({side} 让{line:g}球) @{odd:.2f}")

    # 自动组合
    print("\n" + "=" * 60)
    print("【推荐2串1组合】稳胆 + 让球不败")
    print("-" * 60)
    if bankers and handicap_safe:
        b = bankers[0]
        # 找和稳胆不是同一场的让球
        h = next((x for x in handicap_safe if x[0]["match_num"] != b[0]["match_num"]), None)
        if h:
            odds = b[2] * h[2]
            print(f"  第1场: {b[0]['match_num']} {b[0]['home']}vs{b[0]['away']} "
                  f"→ {b[1]}({b[4]}) @{b[2]:.2f}")
            print(f"  第2场: {h[0]['match_num']} {h[0]['home']}vs{h[0]['away']} "
                  f"→ {h[1]}({h[3]}) @{h[2]:.2f}")
            print(f"  合计赔率: {odds:.2f}  | 100元理论奖金: {100*odds:.0f}元")
        else:
            print("  稳胆与让球候选同场，无法组合")
    else:
        print("  候选不足，暂不推荐")
    print("\n⚠️ 以上为赔率数据筛选，不保证中奖，理性购彩。")


def cmd_list(matches):
    print(f"{'场次':<8}{'联赛':<10}{'对阵':<22}{'时间':<18}{'胜/平/负':<16}状态")
    print("-" * 90)
    for m in matches:
        s = m["spf"]
        odd = f'{s["主胜"]}/{s["平"]}/{s["客胜"]}'
        vs = f'{m["home"]} vs {m["away"]}'
        print(f'{m["match_num"]:<8}{m["league"]:<10}{vs:<22}{m["match_time"]:<18}{odd:<16}{m["status"]}')


def cmd_show(matches, num):
    for m in matches:
        if m["match_num"] == num:
            print(json.dumps(m, ensure_ascii=False, indent=2))
            return
    print(f"未找到 {num}")


def _snapshot_batches(conn):
    rows = conn.execute(
        "SELECT DISTINCT crawled_at FROM odds_snapshot ORDER BY crawled_at").fetchall()
    return [r[0] for r in rows]


def _load_batch(conn, ts):
    rows = conn.execute(
        "SELECT match_id, data FROM odds_snapshot WHERE crawled_at=?", (ts,)).fetchall()
    return {mid: json.loads(d) for mid, d in rows}


def cmd_compare(threshold=0.05):
    """对比最近两次抓取，列出赔率变动超过 threshold 的项。"""
    conn = init_db()
    batches = _snapshot_batches(conn)
    if len(batches) < 2:
        print("快照不足两次，无法对比。请稍后再跑一次 fetch 积累第二个快照。")
        return
    old_ts, new_ts = batches[-2], batches[-1]
    old, new = _load_batch(conn, old_ts), _load_batch(conn, new_ts)
    print(f"对比 {old_ts}  →  {new_ts}\n")
    moves = []
    for mid, nm in new.items():
        if mid not in old:
            continue
        om = old[mid]
        for market in ("spf", "rqspf", "ttg", "hafu"):
            o, n = om.get(market) or {}, nm.get(market) or {}
            for k, nv in n.items():
                ov = o.get(k)
                if ov and nv and ov > 0:
                    pct = (nv - ov) / ov
                    if abs(pct) >= threshold:
                        moves.append((abs(pct), nm["match_num"], nm["home"], nm["away"],
                                      market, k, ov, nv, pct))
    moves.sort(reverse=True)
    if not moves:
        print(f"没有变动幅度 ≥ {threshold:.0%} 的项。")
        return
    print(f"{'场次':<8}{'对阵':<20}{'玩法':<8}{'选项':<6}{'旧赔':>7}{'新赔':>7}{'变动':>9}")
    print("-" * 78)
    for _, num, home, away, market, k, ov, nv, pct in moves:
        arrow = "↓降" if pct < 0 else "↑升"
        print(f"{num:<8}{(home+'vs'+away):<20}{market:<8}{k:<6}{ov:>7.2f}{nv:>7.2f}{pct:>+8.1%}{arrow}")


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == "fetch":
        ms = fetch_matches()
        save(ms)
    elif cmd == "compare":
        thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
        cmd_compare(thr)
    elif cmd in ("list", "show", "analyze", "report", "picks"):
        # 优先读本地缓存，没有则现拉
        f = Path(__file__).parent / "matches.json"
        if not f.exists():
            ms = fetch_matches(); save(ms)
        else:
            ms = json.loads(f.read_text(encoding="utf-8"))
        if cmd == "list":
            cmd_list(ms)
        elif cmd == "analyze":
            cmd_analyze(ms)
        elif cmd == "report":
            cmd_report(ms)
        elif cmd == "picks":
            cmd_picks(ms)
        else:
            cmd_show(ms, sys.argv[2] if len(sys.argv) > 2 else "")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
