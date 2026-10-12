"""Firecrawl로 사주 관련 페이지를 스크랩해서 output/ 에 저장한다.

사용법:
    py crawl.py                       # 두 사이트 모두 (unsin은 기본 샘플 생년월일)
    py crawl.py carat
    py crawl.py unsin --name 홍길동 --sex 여 --birth 1995-07-21 --hour 午 --cal 양력
    py crawl.py mbti                  # 16personalities 한국어 16유형 요약
"""
import argparse
import html as htmllib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"

CARAT_URL = "https://carat.im/prompt-gallery/saju-fortune"
UNSIN_FORM_URL = "https://www.unsin.co.kr/unse/saju/total/form"
MBTI_URL = "https://www.16personalities.com/ko/%EC%84%B1%EA%B2%A9-%EC%9C%A0%ED%98%95"

# unsin 사주명식 이미지 코드 → 글자 (a1~a10 천간, b1~b12 지지는 寅부터 시작)
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "寅卯辰巳午未申酉戌亥子丑"
# 생시 select 값 (시지 기준). "0" = 모름
HOUR_CODES = {"모름": "0", "子": "01", "丑": "02", "寅": "04", "卯": "06", "辰": "08", "巳": "10",
              "午": "12", "未": "14", "申": "16", "酉": "18", "戌": "20", "亥": "22"}
CAL_CODES = {"양력": "S_C", "음력": "L_C", "윤달": "L_L"}


def load_api_key() -> str:
    key = os.environ.get("FIRECRAWL_API_KEY")
    if key:
        return key
    for line in (BASE_DIR / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("FIRECRAWL_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("FIRECRAWL_API_KEY not found in .env")


def firecrawl_scrape(body: dict, api_key: str) -> dict:
    req = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"success": False, "status": e.code, "error": e.read().decode("utf-8", "replace")}


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = htmllib.unescape(s)
    return "\n".join(line.strip() for line in s.splitlines() if line.strip())


def save(name: str, result: dict, parsed: dict | None) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"{name}.raw.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    data = result.get("data", {})
    if data.get("markdown"):
        (OUT_DIR / f"{name}.md").write_text(data["markdown"], encoding="utf-8")
    if data.get("html"):
        (OUT_DIR / f"{name}.html").write_text(data["html"], encoding="utf-8")
    if parsed is not None:
        (OUT_DIR / f"{name}.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- carat.im

def parse_carat(md: str) -> dict:
    title = re.search(r"^# (.+)$", md, re.M)
    prompts = []
    # 각 프롬프트 카드: ### [제목](링크) / 모델·타입 / 프롬프트 본문
    for m in re.finditer(r"^### \[(.+?)\]\((.+?)\)\n+(.+?)\n+(.+?)\n+Create", md, re.M | re.S):
        prompts.append({
            "title": m.group(1),
            "url": m.group(2),
            "model": m.group(3).strip(),
            "prompt": m.group(4).strip(),
        })
    sections = {}
    for m in re.finditer(r"^## (.+?)\n+(.+?)(?=\n## |\Z)", md, re.M | re.S):
        sections[m.group(1).strip()] = m.group(2).strip()
    related = re.findall(r"^- \[(.+?)\]\((https://carat\.im/prompt-gallery/[^)]+)\)", md, re.M)
    return {
        "source": CARAT_URL,
        "title": title.group(1) if title else None,
        "prompts": prompts,
        "sections": {k: v for k, v in sections.items() if k != "Related Prompts"},
        "related": [{"title": t, "url": u} for t, u in related],
    }


def crawl_carat(api_key: str) -> None:
    print(f"[carat] {CARAT_URL}")
    result = firecrawl_scrape({"url": CARAT_URL, "formats": ["markdown", "html"], "waitFor": 3000}, api_key)
    if not result.get("success"):
        save("carat_saju_fortune", result, None)
        print(f"  FAILED: {str(result.get('error'))[:300]}")
        return
    parsed = parse_carat(result["data"].get("markdown", ""))
    save("carat_saju_fortune", result, parsed)
    print(f"  OK: prompts={len(parsed['prompts'])} sections={len(parsed['sections'])} related={len(parsed['related'])}")


# ---------------------------------------------------------------- unsin.co.kr

def parse_unsin(page: str) -> dict:
    out: dict = {"source": UNSIN_FORM_URL}
    info = re.search(r'<span class="name">(.*?)</span>.*?<span class="txt-info">(.*?)</span>', page, re.S)
    if info:
        out["name"] = strip_tags(info.group(1))
        out["birth_info"] = strip_tags(info.group(2))

    # 사주명식: 천간/지지 행 × (생시, 생일, 생월, 생년)
    table = re.search(r'<div class="saju-table.*?</table>', page, re.S)
    if table:
        pillars = {k: {} for k in ("생시", "생일", "생월", "생년")}
        rows = [r for r in re.findall(r"<tr>(.*?)</tr>", table.group(0), re.S) if "images/star/" in r]
        for row, key in zip(rows, ("천간", "지지")):
            for m in re.finditer(r'images/star/([ab])(\d+)\.gif" alt="(.+?)">.*?<span>(.*?)</span>', row, re.S):
                kind, idx, col, ten_god = m.group(1), int(m.group(2)), m.group(3), strip_tags(m.group(4))
                chars = STEMS if kind == "a" else BRANCHES
                pillars[col][key] = chars[idx - 1] if 1 <= idx <= len(chars) else None
                pillars[col][f"{key}_십성"] = ten_god
        for p in pillars.values():
            if p.get("천간") and p.get("지지"):
                p["간지"] = p["천간"] + p["지지"]
        out["사주명식"] = pillars

    elements = re.findall(r'<div class="tit">(.)</div>\s*<div class="progress">\s*<div[^>]*width:\s*([\d.]+)%', page)
    if elements:
        out["오행분석"] = {e: float(v) for e, v in elements}

    # 풀이 섹션: <div class="sub-txt">제목</div><p>본문</p>  또는  <h2>제목</h2></div><div class="bg-box"><p>본문</p>
    readings = {}
    for m in re.finditer(
        r'<div class="sub-txt">([^<]*)</div>\s*<p>(.*?)</p>'
        r'|<h2>([^<]*)</h2>\s*</div>\s*<div class="bg-box">\s*<p>(.*?)</p>',
        page, re.S,
    ):
        title = strip_tags(m.group(1) or m.group(3))
        body = strip_tags(m.group(2) or m.group(4))
        if title and body:
            readings[title] = body
    out["풀이"] = readings
    return out


def crawl_unsin(api_key: str, name: str, sex: str, birth: str, hour: str, cal: str) -> None:
    yyyy, mm, dd = birth.split("-")
    fields = {
        "user_name": name, "sex": sex, "birth_yyyy": yyyy, "birth_mm": mm.zfill(2),
        "birth_dd": dd.zfill(2), "birth_hh": HOUR_CODES[hour], "birth_solunar": CAL_CODES[cal],
    }
    fill_js = (
        "const v=" + json.dumps(fields, ensure_ascii=False) + ";"
        "for (const [k,val] of Object.entries(v)) { const el=document.getElementById(k); if (el) el.value=val; }"
        "document.getElementById('frm').submit();"
    )
    body = {
        "url": UNSIN_FORM_URL,
        "formats": ["markdown", "html"],
        "onlyMainContent": False,
        "timeout": 90000,
        "actions": [
            {"type": "wait", "milliseconds": 2000},
            {"type": "executeJavascript", "script": fill_js},
            {"type": "wait", "milliseconds": 4000},
        ],
    }
    print(f"[unsin] {UNSIN_FORM_URL} -> {fields}")
    result = firecrawl_scrape(body, api_key)
    out_name = f"unsin_saju_total_{yyyy}{mm.zfill(2)}{dd.zfill(2)}"
    if not result.get("success"):
        save(out_name, result, None)
        print(f"  FAILED: {str(result.get('error'))[:300]}")
        return
    parsed = parse_unsin(result["data"].get("html", ""))
    parsed["input"] = {"name": name, "sex": sex, "birth": birth, "hour": hour, "calendar": cal}
    save(out_name, result, parsed)
    print(f"  OK: url={result['data'].get('metadata', {}).get('url')} 풀이 섹션={len(parsed['풀이'])}")


# ---------------------------------------------------------------- 16personalities (MBTI)

def parse_mbti(md: str) -> dict:
    types = []
    for group in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", md, re.M | re.S):
        for m in re.finditer(
            r"\*\*(.+?)\*\*\s+\*\*([EI][NS][TF][JP])-A / \2-T\*\*[\s\\]*\n(.+?)\]\((https://[^)]+)\)",
            group.group(2), re.S,
        ):
            types.append({
                "type": m.group(2),
                "variants": [f"{m.group(2)}-A", f"{m.group(2)}-T"],
                "nickname": m.group(1).strip(),
                "group": group.group(1).strip(),
                "summary": m.group(3).strip(),
                "url": m.group(4),
            })
    return {
        "source": MBTI_URL,
        "identity": {"A": "자기주장형(Assertive)", "T": "신중형(Turbulent)"},
        "types": types,
    }


def crawl_mbti(api_key: str) -> None:
    print(f"[mbti] {MBTI_URL}")
    result = firecrawl_scrape({"url": MBTI_URL, "formats": ["markdown"], "onlyMainContent": True}, api_key)
    if not result.get("success"):
        save("mbti_types", result, None)
        print(f"  FAILED: {str(result.get('error'))[:300]}")
        return
    parsed = parse_mbti(result["data"].get("markdown", ""))
    save("mbti_types", result, parsed)
    print(f"  OK: types={len(parsed['types'])}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="*", default=["carat", "unsin", "mbti"], choices=["carat", "unsin", "mbti"])
    ap.add_argument("--name", default="홍길동")
    ap.add_argument("--sex", default="남", choices=["남", "여"])
    ap.add_argument("--birth", default="1990-01-01", help="YYYY-MM-DD")
    ap.add_argument("--hour", default="모름", choices=list(HOUR_CODES))
    ap.add_argument("--cal", default="양력", choices=list(CAL_CODES))
    args = ap.parse_args()

    api_key = load_api_key()
    if "carat" in args.targets:
        crawl_carat(api_key)
    if "unsin" in args.targets:
        crawl_unsin(api_key, args.name, args.sex, args.birth, args.hour, args.cal)
    if "mbti" in args.targets:
        crawl_mbti(api_key)


if __name__ == "__main__":
    main()
