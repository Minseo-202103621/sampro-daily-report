"""
삼프로TV(@3protv) 최근 영상의 자막을 수집해 transcripts/YYYY-MM-DD/ 에 저장한다.

- 채널의 '동영상' 탭과 '라이브' 탭에서 최근 영상 목록을 가져온다.
- 공개된 지 LOOKBACK_HOURS 이내이고, 아직 저장하지 않은 영상만 처리한다.
- 자막은 youtube-transcript-api 로 먼저 시도하고, 실패하면 yt-dlp 자동자막으로 재시도한다.
- 결과 요약은 transcripts/_last_run.json 에 남긴다 (리포트 작성 시 수집 상태 확인용).

사용법
  python scripts/fetch_transcripts.py              # 어제(KST) 올라온 영상
  python scripts/fetch_transcripts.py 2026-10-22   # 특정 날짜 영상

환경변수
  LOOKBACK_HOURS   날짜를 안 줄 때만 쓰는 대체 기준(시간), 기본 32
  MAX_PER_TAB      탭별로 확인할 최신 영상 수, 기본 60
  MIN_DURATION     이보다 짧은 영상(쇼츠 등)은 건너뜀(초), 기본 180
  PROXY_URL        (선택) 유튜브가 IP를 막을 때 사용할 프록시 http://user:pass@host:port
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig

CHANNEL = "https://www.youtube.com/@3protv"
TABS = ["videos", "streams"]
KST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "transcripts"

LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "32"))
MAX_PER_TAB = int(os.getenv("MAX_PER_TAB", "60"))
MIN_DURATION = int(os.getenv("MIN_DURATION", "180"))
PROXY_URL = os.getenv("PROXY_URL") or None


def ydl_opts(**extra):
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "ignoreerrors": True}
    if PROXY_URL:
        opts["proxy"] = PROXY_URL
    opts.update(extra)
    return opts


def list_recent_ids() -> list[tuple[str, str]]:
    ids: list[tuple[str, str]] = []
    seen: set[str] = set()
    with yt_dlp.YoutubeDL(ydl_opts(extract_flat="in_playlist", playlistend=MAX_PER_TAB)) as ydl:
        for tab in TABS:
            info = ydl.extract_info(f"{CHANNEL}/{tab}", download=False) or {}
            for e in info.get("entries") or []:
                if e and e.get("id") and e["id"] not in seen:
                    seen.add(e["id"])
                    ids.append((tab, e["id"]))
    return ids


def already_saved() -> set[str]:
    return {Path(p).stem for p in glob.glob(str(OUT_DIR / "*" / "*.json")) if not Path(p).name.startswith("_")}


def video_meta(ydl, vid: str) -> dict | None:
    info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    if not info:
        return None
    ts = info.get("release_timestamp") or info.get("timestamp")
    if ts is None and info.get("upload_date"):
        ts = datetime.strptime(info["upload_date"], "%Y%m%d").replace(tzinfo=KST).timestamp()
    return {
        "video_id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": info.get("title"),
        "published_at": datetime.fromtimestamp(ts, KST).isoformat() if ts else None,
        "duration_sec": info.get("duration"),
        "live_status": info.get("live_status"),
        "description": (info.get("description") or "")[:1500],
        "_auto_subs": info.get("automatic_captions") or {},
        "_subs": info.get("subtitles") or {},
    }


def transcript_via_api(vid: str) -> tuple[str, str] | None:
    proxy = GenericProxyConfig(http_url=PROXY_URL, https_url=PROXY_URL) if PROXY_URL else None
    api = YouTubeTranscriptApi(proxy_config=proxy)
    fetched = api.fetch(vid, languages=["ko", "ko-KR", "en"])
    text = " ".join(s.text.replace("\n", " ") for s in fetched.snippets)
    return text, f"youtube-transcript-api ({fetched.language_code}, generated={fetched.is_generated})"


def transcript_via_ytdlp(vid: str) -> tuple[str, str] | None:
    with tempfile.TemporaryDirectory() as tmp:
        opts = ydl_opts(
            writesubtitles=True,
            writeautomaticsub=True,
            subtitleslangs=["ko", "ko-KR", "ko.*"],
            subtitlesformat="vtt",
            outtmpl=f"{tmp}/%(id)s.%(ext)s",
        )
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={vid}"])
        files = glob.glob(f"{tmp}/*.vtt")
        if not files:
            return None
        return vtt_to_text(Path(files[0]).read_text(encoding="utf-8")), "yt-dlp vtt"


def vtt_to_text(vtt: str) -> str:
    lines, prev = [], None
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in line or line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line != prev:  # 자동자막의 롤링 중복 제거
            lines.append(line)
            prev = line
    return " ".join(lines)


def main() -> int:
    now = datetime.now(KST)
    target = sys.argv[1] if len(sys.argv) > 1 else (now - timedelta(days=1)).strftime("%Y-%m-%d")
    run = {"run_at": now.isoformat(), "target_date": target, "saved": [], "skipped": [], "failed": []}

    try:
        ids = list_recent_ids()
    except Exception as e:  # 목록조차 못 가져오면 IP 차단 가능성이 큼
        run["fatal"] = f"{type(e).__name__}: {e}"
        ids = []
    run["candidates"] = len(ids)
    saved = already_saved()

    with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
        done_tabs: set[str] = set()
        for tab, vid in ids:  # 탭별 최신순
            if tab in done_tabs or vid in saved:
                continue
            try:
                meta = video_meta(ydl, vid)
            except Exception as e:
                run["failed"].append({"video_id": vid, "stage": "meta", "error": str(e)[:300]})
                continue
            if not meta:
                run["failed"].append({"video_id": vid, "stage": "meta", "error": "no info"})
                continue
            title = meta["title"]
            if meta["live_status"] in ("is_upcoming", "is_live"):
                run["skipped"].append({"video_id": vid, "title": title, "reason": meta["live_status"]})
                continue
            if not meta["published_at"]:
                continue
            day = meta["published_at"][:10]
            if day > target:
                continue  # 대상 날짜 이후 영상
            if day < target:
                done_tabs.add(tab)  # 이 탭은 최신순이므로 더 볼 필요 없음
                continue
            if (meta["duration_sec"] or 0) < MIN_DURATION:
                run["skipped"].append({"video_id": vid, "title": title, "reason": "short"})
                continue

            result, errors = None, []
            for fn in (transcript_via_api, transcript_via_ytdlp):
                try:
                    result = fn(vid)
                    if result and result[0].strip():
                        break
                except Exception as e:
                    errors.append(f"{fn.__name__}: {type(e).__name__}: {str(e)[:200]}")
                time.sleep(2)
            if not result:
                run["failed"].append({"video_id": vid, "title": title, "stage": "transcript", "error": errors})
                continue

            text, source = result
            out = OUT_DIR / day
            out.mkdir(parents=True, exist_ok=True)
            record = {k: v for k, v in meta.items() if not k.startswith("_")}
            record.update({"transcript_source": source, "char_count": len(text), "fetched_at": now.isoformat(), "transcript": text})
            (out / f"{vid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
            run["saved"].append({"video_id": vid, "title": title, "published_at": meta["published_at"], "chars": len(text)})
            time.sleep(3)

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "_last_run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in run.items()}, ensure_ascii=False))
    for f in run["failed"][:3]:
        print("FAILED:", f.get("title"), f.get("error"))
    # 목록 자체를 못 가져온 경우만 실패 처리 → Actions 화면에서 빨간불로 보임
    return 1 if "fatal" in run or run["candidates"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
