"""픽스처 기반 파서 회귀 테스트.  실행: python collector/tests/test_parse.py"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import board  # noqa: E402
import captions  # noqa: E402
from correct import correct_cues, correct_text  # noqa: E402

LIST_HTML = (HERE / "fixture_list.html").read_text(encoding="utf-8")
VIEW_HTML = (HERE / "fixture_view.html").read_text(encoding="utf-8")


def check(label, got, want):
    assert got == want, f"{label}: {got!r} != {want!r}"
    print(f"  ok  {label}")


def test_list():
    print("게시판 목록 파싱")
    posts = board.parse_list(LIST_HTML)
    check("건수", len(posts), 5)

    notice = posts[0]
    check("공지 판별", notice.is_notice, True)
    check("공지 제외", board.is_meeting_post(notice), False)

    latest = posts[1]
    check("dataSid", latest.post_id, "1165506")
    check("제목", latest.title, "2026년 8월 3주 주간정책회의")
    check("작성일", latest.date, "2026-08-18")
    check("URL", latest.url,
          "https://www.jbe.go.kr/board/view.jbe?boardId=BBS_0000681"
          "&menuCd=DOM_000000507001000000&paging=ok&startPage=1"
          "&searchOperation=AND&dataSid=1165506")
    check("회의 게시글", board.is_meeting_post(latest), True)
    check("회의 ID", board.meeting_id(latest), "2026-W34")

    check("7월5주 ID", board.meeting_id(posts[4]), "2026-W31")
    check("전체 회의 건수", sum(board.is_meeting_post(p) for p in posts), 4)


def test_view():
    print("상세 페이지 파싱")
    check("videoId", board.parse_video_id(VIEW_HTML), "MeLmER3fq_w")
    check("watch 링크도 인식",
          board.parse_video_id('<a href="https://youtu.be/MeLmER3fq_w">보기</a>'),
          "MeLmER3fq_w")
    check("영상 없음", board.parse_video_id("<div>본문만 있음</div>"), None)


def test_correct():
    print("자막 후보정")
    fixed, _ = correct_text("8월 셋째 주관 정책일 시작하겠습니다.")
    check("회의명", fixed, "8월 셋째 주간정책회의 시작하겠습니다.")

    fixed, _ = correct_text("2026년 청년 콘텐츠 공무전 시상식이 있습니다.")
    check("청렴 공모전", fixed, "2026년 청렴 콘텐츠 공모전 시상식이 있습니다.")

    fixed, _ = correct_text("노사 협력가와 논의 중입니다.")
    check("부서명", fixed, "노사협력과와 논의 중입니다.")

    fixed, _ = correct_text("지난 회의 때 교육감지지 사항에 대한 처리 결과입니다.")
    check("지시사항", fixed, "지난 회의 때 교육감 지시사항에 대한 처리 결과입니다.")

    cues, stats = correct_cues([
        {"t": 12, "text": "8월 셋째 주관 정책일 시작하겠습니다."},
        {"t": 20, "text": "변경 없는 문장입니다."},
    ])
    check("raw 보존", cues[0]["raw"], "8월 셋째 주관 정책일 시작하겠습니다.")
    check("미변경은 raw 없음", "raw" in cues[1], False)
    check("통계 산출", len(stats) >= 1, True)


def test_captions():
    print("자막 파싱 (1단계 핵심)")

    j = captions._parse_json3(HERE / "fixture_captions.json3")
    check("json3 큐 수 (빈 이벤트 제외)", len(j), 3)
    check("json3 시작 초", j[0]["t"], 12)
    check("json3 세그먼트 병합", j[0]["text"], "8월 셋째 주관 정책일 시작하겠습니다.")
    check("json3 줄바꿈 제거", j[2]["text"], "아, 복장이 노란색이어서 좀 색다른 느낌이 드네요.")

    v = captions._parse_vtt((HERE / "fixture_captions.vtt").read_text(encoding="utf-8"))
    check("vtt 겹침 제거", len(v), 3)
    check("vtt 인라인 태그 제거", v[0]["text"], "8월 셋째 주관 정책일 시작하겠습니다.")
    check("vtt 시작 초", v[0]["t"], 12)
    check("vtt 마지막 큐", v[2]["text"], "아, 복장이 노란색이어서 좀 색다른 느낌이 드네요.")

    check("두 경로 결과 일치", [c["text"] for c in j], [c["text"] for c in v])

    srt = captions.as_srt(j)
    check("SRT 첫 줄", srt.splitlines()[0], "1")
    check("SRT 시각 형식", srt.splitlines()[1], "00:00:12,000 --> 00:00:19,000")

    plain = captions.plain_text(j)
    check("LLM 입력 형식", plain.splitlines()[0].startswith("[0:12] "), True)


def test_refine():
    print("교정·화자 (1.5단계)")
    import json as _json
    import refine as RF

    # 잘게 쪼개진 자막을 문장으로 합치기
    frag = [
        {"t": 39, "text": "어 7월"},
        {"t": 42, "text": "자치단체장 직무평가 결과가"},
        {"t": 45, "text": "나왔는데 예상보다 잘 나왔습니다."},
        {"t": 58, "text": "그런데 이거는"},
        {"t": 61, "text": "교육감 평가를 얘기하지만", "raw": "교육감 평까를 얘기하지만"},
    ]
    merged = RF.merge_cues(frag)
    check("문장 단위로 합침", len(merged), 2)
    check("시각은 첫 줄 것", merged[0]["t"], 39)
    check("문장 이어붙이기", merged[0]["text"],
          "어 7월 자치단체장 직무평가 결과가 나왔는데 예상보다 잘 나왔습니다.")
    check("원문도 함께 합침", merged[1].get("raw"), "그런데 이거는 교육감 평까를 얘기하지만")
    check("길이 상한", all(len(c["text"]) < 300 for c in RF.merge_cues(
        [{"t": i, "text": "가나다라마바사아자차"} for i in range(60)])), True)

    cues = [
        {"t": 0,   "text": "정책 기획과로 가겠습니다."},
        {"t": 5,   "text": "네. 정책계과 말씀드리겠습니다.", "raw": "네. 정책계과 말씀드리겠습니다."},
        {"t": 12,  "text": "9월 계획을 보고드립니다."},
        {"t": 640, "text": "다음 감사 관실로 가죠."},
        {"t": 650, "text": "검사관실 말씀드리겠습니다."},
    ]
    spans = RF.chunk(cues, 600)
    check("10분 창으로 2토막", spans, [(0, 3), (3, 5)])
    check("첫 토막 줄 수", spans[0][1] - spans[0][0], 3)

    # LLM 을 가짜로 바꿔 병합·이어받기·누락 처리를 확인한다.
    replies = [
        {"cues": [
            {"i": 0, "text": "정책기획과로 가겠습니다.", "speaker": "교육감"},
            {"i": 1, "text": "네. 정책기획과 말씀드리겠습니다.", "speaker": "정책기획과"},
            {"i": 2, "text": "9월 계획을 보고드립니다."},
        ]},
        # 두 번째 토막은 일부러 한 줄을 빠뜨린다 → 원문이 유지돼야 한다
        {"cues": [{"i": 1, "text": "감사관실 말씀드리겠습니다.", "speaker": "감사관실"}]},
    ]
    calls = []
    original = RF._call
    RF._call = lambda p, m="": (calls.append(p),
                                _json.dumps(replies[len(calls) - 1], ensure_ascii=False))[1]
    try:
        out = RF.refine_doc(
            {"id": "T", "cues": cues, "cueCount": 5, "title": "t", "date": "2026-01-01"},
            window_sec=600, verbose=False,
        )
    finally:
        RF._call = original

    got = out["cues"]
    check("호출 횟수 = 토막 수", len(calls), 2)
    check("줄 수 보존", len(got), 5)
    check("문맥 교정 적용", got[1]["text"], "네. 정책기획과 말씀드리겠습니다.")
    check("원문 보존", got[1]["raw"], "네. 정책계과 말씀드리겠습니다.")
    check("화자 이어받기", got[2].get("speaker"), "정책기획과")
    check("누락된 줄은 원문 유지", got[3]["text"], "다음 감사 관실로 가죠.")
    check("누락된 줄 화자는 앞것 이어받음", got[3].get("speaker"), "정책기획과")
    check("두번째 토막 교정", got[4]["text"], "감사관실 말씀드리겠습니다.")
    check("화자 전환 횟수", out["speakerTurns"], 3)
    check("교정된 줄 수", out["changedLines"], 3)

    corr = RF.corrections_from(got)
    check("교정 내역 추출", any(c["to"] == "네. 정책기획과 말씀드리겠습니다." for c in corr), True)

    txt = RF.plain_text(got)
    check("화자는 바뀔 때만", txt.splitlines()[2], "[0:12] 9월 계획을 보고드립니다.")
    check("화자 표기 형식", txt.splitlines()[0], "[0:00] 교육감: 정책기획과로 가겠습니다.")


if __name__ == "__main__":
    test_list()
    test_view()
    test_captions()
    test_correct()
    test_refine()
    print("\n전부 통과")
