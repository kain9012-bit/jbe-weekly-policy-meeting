import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import type { IndexDoc, MeetingDoc, TranscriptDoc } from '../types';
import { Badge, EmptyState, SectionTitle, TimeLink } from './Ui';
import { hasDept, highlight, korDate, splitDepts, sortDepts } from '../lib/util';

interface Props {
  index: IndexDoc;
  meetings: Record<string, MeetingDoc>;
  transcripts: Record<string, TranscriptDoc>;
  initialQuery: string;
  onConsumeInitialQuery: () => void;
  loading: boolean;
}

type Kind = '안건' | '지시' | '보고' | '발언';
interface Hit {
  kind: Kind;
  dept: string;
  t: number;
  videoId: string;
  meetingTitle: string;
  meetingDate: string;
  title: string;
  body: string;
}

const KIND_TONE: Record<Kind, 'blue' | 'slate' | 'green' | 'amber'> = {
  안건: 'blue', 지시: 'amber', 보고: 'green', 발언: 'slate',
};

export const SearchTab: React.FC<Props> = ({
  index, meetings, transcripts, initialQuery, onConsumeInitialQuery, loading,
}) => {
  const [q, setQ] = useState(initialQuery);
  const [dept, setDept] = useState('ALL');
  const [scope, setScope] = useState<'all' | '안건' | '지시' | '보고' | '발언'>('all');
  const [limit, setLimit] = useState(100);

  // 홈에서 넘어온 검색어는 한 번만 쓴다. 남겨두면 나중에 탭을 다시 눌렀을 때 되살아난다.
  React.useEffect(() => {
    if (initialQuery) {
      setQ(initialQuery);
      onConsumeInitialQuery();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  React.useEffect(() => setLimit(100), [q, dept, scope]);

  const hits = useMemo<Hit[]>(() => {
    const k = q.trim().toLowerCase();
    if (!k) return [];
    const has = (...parts: (string | undefined)[]) =>
      parts.some((p) => (p ?? '').toLowerCase().includes(k));
    const out: Hit[] = [];

    for (const entry of index.meetings) {
      const m = meetings[entry.id];
      const base = {
        meetingTitle: entry.title,
        meetingDate: entry.date,
        videoId: entry.videoId,
      };

      if (m) {
        if (scope === 'all' || scope === '안건')
          for (const a of m.agenda)
            if ((dept === 'ALL' || hasDept(a.dept, dept)) && has(a.topic, a.gist))
              out.push({ ...base, kind: '안건', dept: a.dept, t: a.t, title: a.topic, body: a.gist });

        if (scope === 'all' || scope === '지시')
          for (const d of m.directives)
            if ((dept === 'ALL' || hasDept(d.dept, dept)) && has(d.text, d.quote))
              out.push({ ...base, kind: '지시', dept: d.dept, t: d.t, title: d.text, body: d.quote });

        if (scope === 'all' || scope === '보고')
          for (const f of m.followups)
            if ((dept === 'ALL' || hasDept(f.dept, dept)) && has(f.report, f.quote))
              out.push({ ...base, kind: '보고', dept: f.dept, t: f.t, title: f.report, body: f.quote });
      }

      // 발언(자막)에는 부서 정보가 없다. 부서를 고르면 자연히 빠진다.
      const tr = transcripts[entry.id];
      if (tr && dept === 'ALL' && (scope === 'all' || scope === '발언'))
        for (const c of tr.cues)
          if (has(c.text))
            out.push({ ...base, kind: '발언', dept: '', t: c.t, title: '', body: c.text });
    }

    return out.sort((a, b) => b.meetingDate.localeCompare(a.meetingDate) || a.t - b.t);
  }, [q, dept, scope, index, meetings, transcripts]);

  // 한 건이 여러 부서에 걸릴 수 있다. 쪼개서 개별 부서로 목록을 만든다.
  const depts = useMemo(() => {
    const s: string[] = [];
    Object.values(meetings).forEach((m) => {
      m.agenda.forEach((a) => s.push(...splitDepts(a.dept)));
      m.directives.forEach((d) => s.push(...splitDepts(d.dept)));
      m.followups.forEach((f) => s.push(...splitDepts(f.dept)));
    });
    return sortDepts(s);
  }, [meetings]);

  const loadedTranscripts = Object.keys(transcripts).length;

  return (
    <div className="space-y-5 pb-12">
      <SectionTitle desc="안건·지시·보고는 물론 회의 발언 전문까지 함께 찾습니다">통합검색</SectionTitle>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[260px]">
          <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" aria-hidden="true" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="예: 위원회, 창업 동아리, 변호사, 학부모"
            aria-label="회의 내용 검색"
            className="w-full h-12 pl-11 pr-3 rounded-md border border-slate-300 bg-white
                       text-slate-900 placeholder-slate-400 outline-none focus:border-blue-600"
          />
        </div>

        <select
          value={dept} onChange={(e) => setDept(e.target.value)}
          aria-label="부서"
          className="h-12 px-3 rounded-md border border-slate-300 bg-white text-sm font-semibold text-slate-800"
        >
          <option value="ALL">전체 부서</option>
          {depts.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>

        <select
          value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}
          aria-label="검색 범위"
          className="h-12 px-3 rounded-md border border-slate-300 bg-white text-sm font-semibold text-slate-800"
        >
          <option value="all">전체</option>
          <option value="안건">안건만</option>
          <option value="지시">지시사항만</option>
          <option value="보고">처리 결과만</option>
          <option value="발언">회의 발언만</option>
        </select>
      </div>

      {loading && <p className="text-sm text-slate-500" role="status">자료를 불러오는 중입니다…</p>}

      {!q.trim() ? (
        <EmptyState
          icon={<Search className="w-6 h-6" />}
          title="검색어를 입력하세요"
          desc={`자막을 확보한 ${loadedTranscripts}개 회차의 발언 전문과, 요약된 안건·지시·보고를 함께 찾습니다.`}
        />
      ) : hits.length === 0 ? (
        <EmptyState
          icon={<Search className="w-6 h-6" />}
          title="검색 결과가 없습니다"
          desc="다른 낱말로 찾아보거나, 검색 범위를 '전체'로 바꿔 보세요. 자막이 아직 없는 회차는 발언 검색에 잡히지 않습니다."
        />
      ) : (
        <>
          <p className="text-sm text-slate-700 px-1">
            검색 결과 <strong className="text-blue-700 font-bold tabular-nums">{hits.length}</strong>건
          </p>
          <div className="space-y-2">
            {hits.slice(0, limit).map((h, i) => (
              <article key={i} className="bg-white rounded-lg border border-slate-200 p-4 space-y-1.5
                                          hover:border-blue-600 transition-colors">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge tone={KIND_TONE[h.kind]}>{h.kind}</Badge>
                  {splitDepts(h.dept).map((d) => <Badge key={d} tone="blue">{d}</Badge>)}
                  <span className="text-xs text-slate-500">
                    {h.meetingTitle} · {korDate(h.meetingDate)}
                  </span>
                  <TimeLink videoId={h.videoId} t={h.t} />
                </div>
                {h.title && (
                  <p className="font-bold text-slate-900 leading-snug">{highlight(h.title, q)}</p>
                )}
                {h.body && (
                  <p className="text-sm text-slate-600 leading-relaxed">{highlight(h.body, q)}</p>
                )}
              </article>
            ))}
          </div>
          {hits.length > limit && (
            <button
              type="button"
              onClick={() => setLimit((n) => n + 200)}
              className="w-full py-3 rounded-md border border-slate-300 bg-white text-sm font-bold
                         text-slate-700 hover:border-blue-600 hover:text-blue-700"
            >
              더 보기 ({hits.length - limit}건 남음)
            </button>
          )}
        </>
      )}
    </div>
  );
};
