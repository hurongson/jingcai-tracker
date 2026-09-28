#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成竞彩分析看板 HTML（自包含，数据内嵌，无需联网）。"""
import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "sporttery.db"


def load_data():
    conn = sqlite3.connect(DB)
    # 最新一场快照作为当前
    latest = conn.execute(
        "SELECT crawled_at FROM odds_snapshot ORDER BY crawled_at DESC LIMIT 1").fetchone()[0]
    matches = {}
    for row in conn.execute(
            "SELECT match_num, home, away, league, match_time, data, crawled_at FROM odds_snapshot ORDER BY crawled_at"):
        num, home, away, league, mtime, data, ts = row
        d = json.loads(data)
        matches.setdefault(num, {
            "num": num, "home": home, "away": away, "league": league,
            "time": mtime, "series": []})
        spf = d.get("spf", {})
        matches[num]["series"].append({
            "t": ts[-8:-3],  # HH:MM
            "h": spf.get("主胜"), "d": spf.get("平"), "a": spf.get("客胜")})
        matches[num]["latest"] = d
    conn.close()
    return list(matches.values())


def main():
    data = load_data()
    payload = json.dumps(data, ensure_ascii=False)
    html = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>竞彩分析看板</title>
<style>
body{font-family:-apple-system,"PingFang SC",sans-serif;background:#0f1419;color:#e6e6e6;margin:0;padding:16px}
h1{font-size:18px;margin:0 0 4px}
.sub{color:#888;font-size:12px;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px 6px;text-align:right;border-bottom:1px solid #222}
th{color:#888;font-weight:500;position:sticky;top:0;background:#0f1419}
td.l,th.l{text-align:left}
.badge{padding:2px 8px;border-radius:10px;font-size:11px}
.hot{background:#1e3a2e;color:#4ade80}
.even{background:#3a2e1e;color:#fbbf24}
.fav{background:#1e2a3a;color:#60a5fa}
.spark{stroke:#60a5fa;stroke-width:1.5;fill:none}
.up{color:#f87171}.down{color:#4ade80}
</style></head><body>
<h1>⚽ 竞彩分析看板</h1>
<div class="sub" id="sub">数据加载中…</div>
<table><thead><tr>
<th class="l">场次</th><th class="l">对阵</th><th class="l">联赛</th>
<th>主胜%</th><th>平%</th><th>客胜%</th><th>预期球</th><th class="l">格局</th><th class="l">主胜走势</th>
</tr></thead><tbody id="tb"></tbody></table>
<script>
const DATA = __PAYLOAD__;
function devig(o){const inv={};for(const k in o)inv[k]=1/o[k];const t=Object.values(inv).reduce((a,b)=>a+b,0);
const r={};for(const k in inv)r[k]=inv[k]/t*100;return r;}
function expGoal(ttg){if(!ttg)return null;const inv={};for(const k in ttg)inv[k]=1/ttg[k];
const t=Object.values(inv).reduce((a,b)=>a+b,0);let e=0;for(const k in inv){const p=inv[k]/t;
const n=k.startsWith('7')?7.5:parseFloat(k);e+=n*p;}return e;}
function spark(series){const hs=series.map(s=>s.h).filter(x=>x);if(hs.length<2)return '-';
const w=60,h=24,mn=Math.min(...hs),mx=Math.max(...hs);
const pts=series.map((s,i)=>{const x=i/(series.length-1)*w;
const y=h-(s.h-mn)/(mx-mn||1)*(h-4)-2;return x+','+y;}).join(' ');
const chg=hs[hs.length-1]-hs[0];const cls=chg<0?'down':'up';const arrow=chg<0?'↓':'↑';
return `<svg width="${w}" height="${h}"><polyline class="spark" points="${pts}"/></svg>
<span class="${cls}">${arrow}${Math.abs(chg).toFixed(2)}</span>`;}
const tb=document.getElementById('tb');
document.getElementById('sub').textContent='共 '+DATA.length+' 场，自动采集于本地SQLite';
DATA.forEach(m=>{
  const d=m.latest;const p=devig({主胜:d.spf['主胜'],平:d.spf['平'],客胜:d.spf['客胜']});
  const eg=expGoal(d.ttg);
  const items=Object.entries(p).sort((a,b)=>b[1]-a[1]);
  const gap=items[0][1]-items[1][1];
  let badge,cls;
  if(items[0][1]>=60){badge='热门·'+items[0][0];cls='hot';}
  else if(gap<6){badge='势均力敌';cls='even';}
  else{badge='略偏'+items[0][0];cls='fav';}
  tb.innerHTML+=`<tr>
<td class="l">${m.num}</td>
<td class="l">${m.home} vs ${m.away}</td>
<td class="l">${m.league}</td>
<td>${p['主胜'].toFixed(0)}%</td><td>${p['平'].toFixed(0)}%</td><td>${p['客胜'].toFixed(0)}%</td>
<td>${eg?eg.toFixed(2):'-'}</td>
<td class="l"><span class="badge ${cls}">${badge}</span></td>
<td class="l">${spark(m.series)}</td></tr>`;
});
</script></body></html>"""
    html = html.replace("__PAYLOAD__", payload)
    out = BASE / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"已生成 {out}（{len(data)} 场）")


if __name__ == "__main__":
    main()
