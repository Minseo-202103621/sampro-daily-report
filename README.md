# sampro-daily-report

삼프로TV(@3protv) 영상 자막을 매일 수집해, Claude가 시황 분석과 성향별 모델 포트폴리오 리포트를 작성하는 저장소 (NH투자증권 PB 면접 대비 학습용).

- `.github/workflows/fetch.yml` — 매일 09:40, 21:30 KST에 자막 수집 (Actions 탭에서 수동 실행 가능)
- `scripts/fetch_transcripts.py` — 자막 수집 스크립트
- `transcripts/` — 날짜별 자막 JSON, `_last_run.json`에 최근 수집 결과
- `REPORT_GUIDE.md` — 리포트 작성 규칙 (수정하면 다음 리포트부터 반영)
- `reports/` — 날짜별 HTML 리포트
- `portfolio/history.json` — 일자별 모델 포트폴리오 기록

## 유튜브가 Actions IP를 막을 때
Settings → Secrets and variables → Actions 에 `PROXY_URL` (예: 주거용 프록시 `http://user:pass@host:port`) 추가.
또는 PC에서 `pip install yt-dlp youtube-transcript-api && python scripts/fetch_transcripts.py` 실행 후 push.
