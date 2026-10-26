# sampro-daily-report

삼프로TV(@3protv) 영상 자막을 매일 수집해, Claude가 시황 분석과 성향별 모델 포트폴리오 리포트를 작성하는 저장소 (NH투자증권 PB 면접 대비 학습용).

- `.github/workflows/fetch.yml` — 매일 06:00 KST에 Claude 예약 작업이 실행(백업 cron 22:30, 05:40 KST) (Actions 탭에서 수동 실행 가능)
- `scripts/fetch_transcripts.py` — 자막 수집 스크립트 (사용자 PC에서 실행: `python scripts/fetch_transcripts.py [YYYY-MM-DD]`)
- `transcripts/` — 날짜별 자막 JSON, `_last_run.json`에 최근 수집 결과
- `REPORT_GUIDE.md` — 리포트 작성 규칙 (수정하면 다음 리포트부터 반영)
- `reports/` — 날짜별 HTML 리포트
- `portfolio/history.json` — 일자별 모델 포트폴리오 기록

## 왜 PC에서 수집하나
GitHub Actions·클라우드 서버 IP는 유튜브가 "로봇 확인"으로 차단한다(2026-10-26 확인). 가정용 IP인 개인 PC에서만 자막을 받을 수 있다.
나중에 완전 자동화가 필요하면 주거용 프록시(`PROXY_URL` 환경변수) 방식으로 전환 가능.

## 사용법
PC를 켜고 Claude 데스크톱 앱에서 리포트 채팅을 연 뒤 "보고서 만들어" (특정 날짜: "22일 보고서 만들어").
