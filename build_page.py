"""입력 폼이 있는 사주 × MBTI 페이지를 만든다.

사주명식·오행·대운·MBTI 추정은 페이지 안에서 입력값으로 바로 계산한다.
crawl.py로 수집한 운세의신 평생사주 결과(output/unsin_saju_total_*.json)는 전부 페이지에 넣어,
같은 생년월일·성별·시·달력으로 입력하면 원문 풀이를 함께 보여준다.

사용법:
    py build_page.py            # output/saju_mbti.html (운세의신 원문 포함, 개인 확인용)
    py build_page.py --public   # docs/index.html (원문 제외, GitHub Pages 배포용)
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"
TEMPLATE = BASE_DIR / "saju_mbti_template.html"
PRIVATE_OUT = OUT_DIR / "saju_mbti.html"
PUBLIC_OUT = BASE_DIR / "docs" / "index.html"


def load_unsin() -> tuple[list, float | None]:
    paths = sorted(p for p in OUT_DIR.glob("unsin_saju_total_*.json") if not p.name.endswith(".raw.json"))
    unsin = []
    for p in paths:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("input") and d.get("풀이"):
            unsin.append({"input": d["input"], "풀이": d["풀이"]})
    return unsin, max((p.stat().st_mtime for p in paths), default=None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", action="store_true", help="운세의신 원문을 빼고 docs/index.html 로 빌드")
    args = ap.parse_args()

    mbti_path = OUT_DIR / "mbti_types.json"
    if not mbti_path.exists():
        sys.exit("MBTI 데이터가 없습니다. 먼저 `py crawl.py mbti` 를 실행하세요.")

    unsin, latest = ([], None) if args.public else load_unsin()
    latest = latest or mbti_path.stat().st_mtime
    data = {
        "mbti": json.loads(mbti_path.read_text(encoding="utf-8")),
        "unsin": unsin,
        "public": args.public,
        "crawled_at": datetime.fromtimestamp(latest).strftime("%Y-%m-%d"),
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)

    out = PUBLIC_OUT if args.public else PRIVATE_OUT
    if args.public:
        # Artifact 게시 때는 플랫폼이 문서 골격을 씌우지만, 일반 호스팅에서는 직접 넣는다.
        html = '<!doctype html>\n<html lang="ko">\n' + html + "\n</html>\n"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  (unsin 원문 {len(unsin)}건, mbti {len(data['mbti']['types'])}유형)")


if __name__ == "__main__":
    main()
