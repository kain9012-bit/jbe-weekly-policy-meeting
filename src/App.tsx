import React, { useCallback, useEffect, useState } from 'react';
import { ArrowUp } from 'lucide-react';
import type { ActiveTab, IndexDoc, MeetingDoc, TranscriptDoc } from './types';
import { emptyIndex } from './types';
import { Header } from './components/Header';
import { HomeTab } from './components/HomeTab';
import { MeetingTab } from './components/MeetingTab';
import { TranscriptTab } from './components/TranscriptTab';
import { DirectivesTab } from './components/DirectivesTab';
import { SearchTab } from './components/SearchTab';

/** data/*.json 을 BASE_URL 기준 상대경로로 읽는다 (Pages 하위 경로 대응) */
async function loadJson<T>(path: string): Promise<T | null> {
  const base = import.meta.env.BASE_URL || './';
  const url = `${base}data/${path}`.replace(/([^:]\/)\/+/g, '$1');
  try {
    const res = await fetch(url);
    if (res.ok) return (await res.json()) as T;
    console.warn(`${path} 응답 ${res.status}`);
  } catch (err) {
    console.warn(`${path} 을 불러오지 못했습니다.`, err);
  }
  return null;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('home');
  const [searchQuery, setSearchQuery] = useState('');

  // 자료가 도착하기 전에는 빈 껍데기를 쓴다.
  // 그럴듯한 표본을 채워두면 못 받았을 때 가짜가 진짜처럼 보인다.
  const [index, setIndex] = useState<IndexDoc>(emptyIndex);
  const [meetings, setMeetings] = useState<Record<string, MeetingDoc>>({});
  const [transcripts, setTranscripts] = useState<Record<string, TranscriptDoc>>({});

  const [currentId, setCurrentId] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [retryToken, setRetryToken] = useState(0);
  const [detailLoading, setDetailLoading] = useState(false);

  // ── 목록 ──
  useEffect(() => {
    let alive = true;
    setLoading(true);
    (async () => {
      const idx = await loadJson<IndexDoc>('index.json');
      if (!alive) return;
      if (idx) {
        setIndex(idx);
        setCurrentId((cur) => cur || idx.meetings[0]?.id || '');
      }
      setLoadFailed(!idx);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [retryToken]);

  // ── 회차 상세: 지금 보는 회차만 먼저 받는다 ──
  const ensureDetail = useCallback(async (id: string) => {
    if (!id) return;
    const entry = index.meetings.find((m) => m.id === id);
    if (!entry) return;
    const needMeeting = entry.hasSummary && !meetings[id];
    const needTranscript = entry.hasTranscript && !transcripts[id];
    if (!needMeeting && !needTranscript) return;

    setDetailLoading(true);
    // 교정본이 있으면 그것을 읽는다. 화면에 보이는 회의록은 항상 최신 단계의 결과다.
    const path = entry.hasRefined ? `refined/${id}.json` : `transcripts/${id}.json`;
    const [m, t] = await Promise.all([
      needMeeting ? loadJson<MeetingDoc>(`meetings/${id}.json`) : null,
      needTranscript ? loadJson<TranscriptDoc>(path) : null,
    ]);
    if (m) setMeetings((prev) => ({ ...prev, [id]: m }));
    if (t) setTranscripts((prev) => ({ ...prev, [id]: t }));
    setDetailLoading(false);
  }, [index, meetings, transcripts]);

  useEffect(() => { void ensureDetail(currentId); }, [currentId, ensureDetail]);

  // ── 지시사항·검색 탭은 전 회차가 필요하다. 그 탭에 들어갈 때만 받는다. ──
  const bulkRequested = React.useRef(false);
  useEffect(() => {
    if (activeTab !== 'directives' && activeTab !== 'search') return;
    if (bulkRequested.current || index.meetings.length === 0) return;
    bulkRequested.current = true;

    setDetailLoading(true);
    (async () => {
      const results = await Promise.all(
        index.meetings.map(async (e) => ({
          id: e.id,
          m: e.hasSummary ? await loadJson<MeetingDoc>(`meetings/${e.id}.json`) : null,
          t: e.hasTranscript
            ? await loadJson<TranscriptDoc>(
                e.hasRefined ? `refined/${e.id}.json` : `transcripts/${e.id}.json`,
              )
            : null,
        })),
      );
      const okAny = results.some((r) => r.m || r.t);
      setMeetings((prev) => {
        const next = { ...prev };
        results.forEach((r) => { if (r.m) next[r.id] = r.m; });
        return next;
      });
      setTranscripts((prev) => {
        const next = { ...prev };
        results.forEach((r) => { if (r.t) next[r.id] = r.t; });
        return next;
      });
      setDetailLoading(false);
      // 한 번 끊겼다고 새로고침 전까지 계속 빈 목록만 보이면 안 된다.
      if (!okAny) bulkRequested.current = false;
    })();
  }, [activeTab, index]);

  // 탭을 바꾸면 화면 맨 위부터 보여준다.
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'auto' }); }, [activeTab]);

  const navigate = (tab: ActiveTab, query?: string, meetingId?: string) => {
    if (query !== undefined) setSearchQuery(query);
    if (meetingId) setCurrentId(meetingId);
    setActiveTab(tab);
  };

  return (
    <div className="min-h-screen overflow-x-clip bg-white text-slate-800 font-sans antialiased flex flex-col selection:bg-blue-600 selection:text-white">
      <a href="#container" className="krds-skip">본문 바로가기</a>

      <Header activeTab={activeTab} setActiveTab={setActiveTab} updatedAt={index.updatedAt} />

      <main id="container" className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {loading && (
          <p className="text-sm text-slate-500 py-2" role="status">수집 자료를 불러오는 중입니다…</p>
        )}

        {!loading && loadFailed && (
          <div role="alert" className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-5 space-y-2">
            <p className="font-bold text-slate-900">수집 자료를 불러오지 못했습니다</p>
            <p className="text-sm text-slate-700">
              화면에 아무 회의도 표시되지 않습니다. 없는 자료를 임의로 채워 보여주지 않습니다.
              연결 상태를 확인한 뒤 다시 시도해 주세요.
            </p>
            <button
              type="button"
              onClick={() => { bulkRequested.current = false; setRetryToken((n) => n + 1); }}
              className="px-4 py-2 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-sm font-bold"
            >
              다시 시도
            </button>
          </div>
        )}

        {!loading && !loadFailed && (
          <>
            {activeTab === 'home' && <HomeTab index={index} onNavigate={navigate} />}

            {activeTab === 'meeting' && (
              <MeetingTab
                index={index}
                currentId={currentId}
                setCurrentId={setCurrentId}
                meeting={meetings[currentId] ?? null}
                loading={detailLoading}
                onNavigate={navigate}
              />
            )}

            {activeTab === 'transcript' && (
              <TranscriptTab
                index={index}
                currentId={currentId}
                setCurrentId={setCurrentId}
                transcript={transcripts[currentId] ?? null}
                loading={detailLoading}
              />
            )}

            {activeTab === 'directives' && (
              <DirectivesTab index={index} meetings={meetings} loading={detailLoading} />
            )}

            {activeTab === 'search' && (
              <SearchTab
                index={index}
                meetings={meetings}
                transcripts={transcripts}
                initialQuery={searchQuery}
                onConsumeInitialQuery={() => setSearchQuery('')}
                loading={detailLoading}
              />
            )}
          </>
        )}
      </main>

      <footer className="bg-slate-900 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-5">
            <div className="space-y-1.5">
              <p className="text-base font-bold text-white">
                주간정책회의 브리핑{' '}
                <span className="text-slate-400 font-medium">전북특별자치도교육청</span>
              </p>
              <p className="text-sm text-slate-300">
                유튜브 자동생성 자막을 정리한 자료입니다. 공식 회의록이 아닙니다.
              </p>
            </div>
            <div className="text-sm text-slate-300 md:text-right space-y-1">
              <p>영상 출처: 전북교육 열린회의생중계 유튜브 채널</p>
              <p>게시글 출처: 전북특별자치도교육청 주간정책회의 게시판</p>
              <p>중요한 내용은 타임스탬프를 눌러 원 영상으로 확인하세요.</p>
            </div>
          </div>
        </div>
      </footer>

      <ScrollToTopButton />
    </div>
  );
}

/** 화면을 어느 정도 내렸을 때만 나타나는 '맨 위로' 버튼 (KRDS 상단이동 패턴) */
function ScrollToTopButton() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 400);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <button
      type="button"
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      aria-label="맨 위로 이동"
      className={`fixed bottom-6 right-6 z-40 flex items-center gap-1.5 px-4 py-3
                  rounded-full border border-slate-300 bg-white text-slate-700 shadow-lg
                  text-sm font-bold hover:bg-blue-600 hover:border-blue-600 hover:text-white
                  transition-all ${show ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3 pointer-events-none'}`}
    >
      <ArrowUp className="w-4 h-4" aria-hidden="true" />
      <span className="hidden sm:inline">맨 위로</span>
    </button>
  );
}
