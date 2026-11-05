#!/usr/bin/env python3
"""계속 새로 쓰는 장치.

input/의 기록을 읽어 숫자 칸과 능력별 문단 후보를 다시 만들고,
content/approved.json에서 승인한 문장만 넣어 docs/index.html을 만든다.
AI를 부르지 않고 시계도 읽지 않으므로 같은 입력에는 같은 결과가 나온다.

    python run.py            한 번 만든다
    python run.py --verify   임시 폴더에서 두 번 만들어 결과를 비교한다
"""
import csv
import datetime as dt
import hashlib
import html
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HARDSHIP_DATE = "2026-08-21"
SOURCE_FIELDS = ("강점이 드러난 일화", "그 결과·알게 된 점", "강점을 위해 노력하고 생각한 것", "나에게 남기는 말",
                 "동료 1가 말해 준 내 장점", "동료 2가 말해 준 내 장점", "동료 3가 말해 준 내 장점")
ABILITIES = {
    "자기조절력": ("당황", "침착", "스트레스", "복구", "우선순위", "쉬는 시간", "휴식", "무리"),
    "대인관계력": ("고민", "경청", "갈등", "조율", "공유", "설명", "도와", "먼저"),
    "자기동기력": ("끝까지", "스스로", "포기", "책을", "남아서", "완성", "집념", "해결하려"),
}
ACTIONS = {"실천했다": ("on", "실천"), "일부 실천했다": ("part", "일부 실천"), "못 했다": ("none", "못 함")}
TOP_N = 10
OUTPUTS = ("output/numbers.json", "output/candidates.md", "docs/index.html", "docs/story.html")


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def field(entries, name):
    for entry in entries:
        if entry.startswith(name + ":"):
            return entry[len(name) + 1:].strip()
    return ""


def load(base):
    days = sorted(json.loads(read(base / "input/ritual.json"))["days"], key=lambda d: d["date"])
    with open(base / "input/attendance.csv", encoding="utf-8", newline="") as f:
        attendance = sorted(csv.DictReader(f), key=lambda r: r["date"])
    with open(base / "input/assignments.csv", encoding="utf-8", newline="") as f:
        tasks = sorted(csv.DictReader(f), key=lambda r: (r["submitted"], r["id"]))
    return days, attendance, tasks


def numbers(days, attendance, tasks):
    acts = {d["date"]: field(d["close"], "강점 행동") for d in days}
    unknown = sorted(set(acts.values()) - set(ACTIONS))
    if unknown:
        sys.exit("모르는 강점 행동 값: " + ", ".join(unknown))
    order = sorted(acts)
    first = dt.date.fromisoformat(order[0])
    last = dt.date.fromisoformat(order[-1])
    monday = first - dt.timedelta(days=first.weekday())
    weeks = (last - monday).days // 7 + 1
    pair = None
    if HARDSHIP_DATE in acts and order.index(HARDSHIP_DATE) + 1 < len(order):
        nxt = order[order.index(HARDSHIP_DATE) + 1]
        pair = {"date": HARDSHIP_DATE, "action": acts[HARDSHIP_DATE], "next_date": nxt, "next_action": acts[nxt]}
    attended = [r for r in attendance if r["status"] in ("출석", "지각") and r["confirmed"] == "확정"]
    total = len(attendance)
    return {
        "as_of": max(order[-1], attendance[-1]["date"]),
        "weeks": weeks,
        "ritual": {"source": "리추얼 기록", "first": order[0], "last": order[-1], "days": len(days),
                   "morning": sum(1 for d in days if d["open"]), "closing": sum(1 for d in days if d["close"]),
                   "full": sum(1 for a in acts.values() if a == "실천했다"),
                   "partial": sum(1 for a in acts.values() if a == "일부 실천했다"),
                   "none": sum(1 for a in acts.values() if a == "못 했다")},
        "attendance": {"source": "내 출석 기록", "days": total, "attended": len(attended),
                       "absent": sum(1 for r in attendance if r["status"] == "결석"),
                       "late": sum(1 for r in attendance if r["status"] == "지각"),
                       "pending": sum(1 for r in attendance if r["confirmed"] != "확정"),
                       "rate": round(len(attended) / total * 100, 1) if total else 0},
        "assignments": {"source": "내 제출 현황", "total": len(tasks),
                        "confirmed": sum(1 for t in tasks if t["status"] == "최종 확인 완료")},
        "hardship_pair": pair,
    }


def candidates(days, approved_ids):
    pool = []
    for day in days:
        for name in SOURCE_FIELDS:
            text = field(day["open"] + day["close"], name)
            if text and "이름 가림" not in text:
                key = f'{day["date"]}|{name}|{text}'
                pool.append({"id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:10],
                             "date": day["date"], "field": name, "text": text})
    lines = ["# 능력별 문단 후보", "", "쓰고 싶은 문장의 id를 content/approved.json에 넣고 다시 실행합니다.", ""]
    for ability, words in ABILITIES.items():
        scored = [(sum(w in c["text"] for w in words), c["date"], c["id"], c) for c in pool]
        scored = [s for s in scored if s[0]]
        picked = [s[3] for s in sorted(scored, key=lambda s: s[:3], reverse=True)][:TOP_N]
        lines += [f"## {ability}", ""]
        for c in picked:
            mark = "승인됨" if c["id"] in approved_ids else "후보"
            lines.append(f'- [{mark}] `{c["id"]}` {c["date"]} ({c["field"]}): {c["text"]}')
        lines.append("")
    return pool, "\n".join(lines)


def calendar(days, weeks):
    acts = {d["date"]: field(d["close"], "강점 행동") for d in days}
    first = dt.date.fromisoformat(min(acts))
    monday = first - dt.timedelta(days=first.weekday())
    marks = set()
    order = sorted(acts)
    if HARDSHIP_DATE in acts:
        marks.add(HARDSHIP_DATE)
        i = order.index(HARDSHIP_DATE)
        if i + 1 < len(order):
            marks.add(order[i + 1])
    heads, cells, last_month = [], [], None
    for w in range(weeks):
        start = monday + dt.timedelta(days=7 * w)
        heads.append(f"<span>{start.month}월</span>" if start.month != last_month else "<span></span>")
        last_month = start.month
        for d in range(5):
            key = (start + dt.timedelta(days=d)).isoformat()
            if key in acts:
                cls, label = ACTIONS[acts[key]]
                extra = " mark" if key in marks else ""
                cells.append(f'<i class="c {cls}{extra}" data-tip="{key} · {label}"></i>')
            else:
                cells.append(f'<i class="c off" data-tip="{key} · 수업 없음"></i>')
    return "".join(heads), "".join(cells)


def build(base):
    days, attendance, tasks = load(base)
    nums = numbers(days, attendance, tasks)
    approved = json.loads(read(base / "content/approved.json"))
    pool, cand_md = candidates(days, {a["id"] for a in approved})
    by_id = {c["id"]: c for c in pool}
    missing = [a["id"] for a in approved if a["id"] not in by_id]
    if missing:
        sys.exit("승인한 id를 기록에서 찾지 못했습니다: " + ", ".join(missing))
    heads, cells = calendar(days, nums["weeks"])
    rows = []
    for t in tasks:
        no = t["id"][1:] if t["id"].startswith("T") else "+"
        rows.append(f'<li><time>{t["submitted"][5:].replace("-", ".")}</time><b>{no}</b>'
                    f'<span>{html.escape(t["title"], quote=False)}</span></li>')
    r, a, s, p = nums["ritual"], nums["attendance"], nums["assignments"], nums["hardship_pair"] or {}
    quotes = "".join(f'<p>"{html.escape(by_id[x["id"]]["text"], quote=False)}"</p>' for x in approved)
    fills = {"weeks": nums["weeks"], "as_of": nums["as_of"], "att_days": a["days"], "att_ok": a["attended"],
             "att_abs": a["absent"], "att_rate": a["rate"], "att_late": a["late"], "att_pending": a["pending"],
             "r_first": r["first"], "r_last": r["last"], "r_days": r["days"], "r_morning": r["morning"],
             "r_closing": r["closing"], "r_full": r["full"], "r_part": r["partial"], "r_none": r["none"],
             "cal_heads": heads, "cal_cells": cells, "a_total": s["total"], "a_ok": s["confirmed"],
             "task_rows": "".join(rows), "task_rows_n": (len(rows) + 1) // 2,
             "pair_date": p.get("date", ""), "pair_action": p.get("action", ""),
             "pair_next": p.get("next_date", ""), "pair_next_action": p.get("next_action", ""),
             "approved_quotes": quotes}
    page = read(base / "content/template.html")
    for key, value in fills.items():
        page = page.replace("{{" + key + "}}", str(value))
    if "{{" in page:
        sys.exit("채우지 못한 자리가 있습니다")
    write(base / "output/numbers.json", json.dumps(nums, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    write(base / "output/candidates.md", cand_md)
    write(base / "docs/index.html", page)
    write(base / "docs/story.html", read(base / "content/story.template.html"))
    return nums


def digests(base):
    return {n: hashlib.sha256((base / n).read_bytes()).hexdigest() for n in OUTPUTS}


def verify():
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for n in ("first", "second"):
            work = Path(tmp) / n
            for sub in ("input", "content"):
                shutil.copytree(ROOT / sub, work / sub)
            build(work)
            results.append(digests(work))
    lines = ["# 두 번 실행한 결과 비교 (SHA-256)", ""]
    same = True
    for name in OUTPUTS:
        ok = results[0][name] == results[1][name]
        same = same and ok
        lines += [name, f"  1회차 {results[0][name]}", f"  2회차 {results[1][name]}", f'  판정 {"같음" if ok else "다름"}', ""]
    lines.append("결과: 모두 같음" if same else "결과: 다른 파일 있음")
    write(ROOT / "output/compare_two_runs.txt", "\n".join(lines) + "\n")
    print(lines[-1])
    return 0 if same else 1


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "--verify" in sys.argv:
        return verify()
    n = build(ROOT)
    print(f'기록 {n["ritual"]["days"]}일, 출석 {n["attendance"]["attended"]}/{n["attendance"]["days"]}일, '
          f'과제 {n["assignments"]["confirmed"]}건 (기준일 {n["as_of"]})')
    print("만든 파일: " + ", ".join(OUTPUTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
