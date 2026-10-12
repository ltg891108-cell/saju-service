# 평생사주 × MBTI

생년월일시를 입력하면 브라우저에서 사주명식·십성·오행 분포·대운 흐름을 계산하고,
16Personalities의 MBTI 유형과 사주로 추정한 MBTI를 비교합니다. 2026 사천에어쇼 홍보 배너가 들어 있습니다.

페이지: https://ltg891108-cell.github.io/saju-service/

## 구성

| 파일 | 역할 |
| --- | --- |
| `crawl.py` | Firecrawl API로 데이터 수집 (`carat`, `unsin`, `mbti`) |
| `build_page.py` | 수집 데이터 + 템플릿으로 페이지 생성 |
| `saju_mbti_template.html` | 페이지 템플릿 (입력 폼, 만세력 계산, MBTI 비교) |
| `docs/index.html` | GitHub Pages 배포본 (`build_page.py --public` 결과) |

## 사용법

```bash
# .env 에 FIRECRAWL_API_KEY=... 를 넣은 뒤
py crawl.py mbti                 # MBTI 16유형 수집
py build_page.py --public        # docs/index.html 생성 (운세의신 원문 제외)
git add docs && git commit -m "Rebuild page" && git push
```

`py build_page.py`(옵션 없음)는 수집한 운세의신 원문을 포함한 개인 확인용 페이지를 `output/`에 만듭니다. `output/`과 `.env`는 저장소에 올라가지 않습니다.

## 계산 기준

- 만세력: [lunar-javascript](https://github.com/6tail/lunar-javascript) 1.6.13
- 년·월주는 절기 기준, 입력 시각에서 30분을 빼서 계산 (子시 = 23:30~01:29, 23:30부터 다음 날 일주)
- 사주 기반 MBTI 추정은 십성과 오행 비중으로 점수를 매긴 재미용 규칙이며 과학적 근거는 없습니다.
