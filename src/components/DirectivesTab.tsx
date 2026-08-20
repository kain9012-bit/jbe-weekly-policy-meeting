import React, { useMemo, useState } from 'react';
import { ListChecks, RotateCcw } from 'lucide-react';
import type { Directive, IndexDoc, MeetingDoc } from '../types';
import { Badge, EmptyState, Quote, SectionTitle, TimeLink } from './Ui';
import { highlight, korDate } from '../lib/util';

interface Props {
  index: IndexDoc;
  meetings: Record<string, MeetingDoc>;
  loading: boolean;
}

type Row = Directive & { meeting: MeetingDoc };

/**
 * 이행 여부는 "이후 회차에 처리 결과 보고가 있었는가" 로 본다.
 *   확인   — LLM이 지시사항 id를 직접 연결한 경우
 *   추정   — 같은 부서가 이후 회차에서 보고한 기록만 있는 경우
 * 둘을 구분해 표시한다. 추정을 확인처럼 보이면 안 된다.
 */
function traceFollowup(row: Row, all: MeetingDoc[]) {
  const later = all.filter((m) => m.date > row.meeting.date).sort((a, b) => a.date.localeCompare(b.date));
  for (const m of later) {
    const hit = m.followups.find((f) => f.matchedDirective === row.id);
    if (hit) return { meeting: m, followup: hit, exact: true };
  }
  for (const m of later) {
    const hit = m.followups.find((f) => f.dept && row.dept && f.dept === row.dept);
    if (hit) return { meeting: m, followup: hit, exact: false };
  }
  return null;
}

export const DirectivesTab: React.FC<Props> = ({ index, meetings, loading }) => {
  const [dept, setDept] = useState('ALL');
  const [type, setType] = useState('ALL');
  const [status, setStatus] = useState<'ALL' | 'open' | 'reported'>('ALL');
  const [q, setQ] = useState('');
  const [showQuote, setShowQuote] = useState(true);

  const all = useMemo(
    () => index.meetings.map((m) => meetings[m.id]).filter(Boolean) as MeetingDoc[],
    [index, meetings],
  );

  const rows = useMemo<Row[]>(
    () => all.flatMap((m) => m.directives.map((d) => ({ ...d, meeting: m }))),
    [all],
  );

  const depts = useMemo(
    () => [...new Set(rows.map((r) => r.dept).filter(Boolean))].sort(),
    [rows],
  );
  const types = useMemo(
    () => [...new Set(rows.map((r) => r.type || '지시'))].sort(),
    [rows],
  );

  const traced = useMemo(
    () => rows.map((r) => ({ row: r, trace: traceFollowup(r, all) })),
    [rows, all],
  );

  const view = useMemo(() => {
    const k = q.trim().toLowerCase();
    return traced
      .filter(({ row, trace }) => {
        if (dept !== 'ALL' && row.dept !== dept) return false;
        if (type !== 'ALL' && (row.type || '지시') !== type) return false;
        if (status === 'open' && trace) return false;
        if (status === 'reported' && !trace) return false;
        if (k && !`${row.text} ${row.quote}`.toLowerCase().includes(k)) return false;
        return true;
      })
      .sort((a, b) =>
        b.row.meeting.date.localeCompare(a.row.meeting.date) || a.row.t - b.row.t,
      );
  }, [traced, dept, type, status, q]);

  const reset = () => { setDept('ALL'); setType('ALL'); setStatus('ALL'); setQ(''); };

  if (loading) {
    return <p className="text-sm text-slate-500 py-2" role="status">지시사항을 모으는 중입니다…</p>;
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<ListChecks className="w-6 h-6" />}
        title="아직 정리된 지시사항이 없습니다"
        desc="자막을 확보한 뒤 요약 단계까지 실행해야 지시사항이 만들어집니다."
      >
        <code className="inline-block text-xs bg-slate-50 border border-slate-200 rounded px-3 py-2 text-slate-700">
          python collector/run.py --all
        </code>
      </EmptyState>
    );
  }

  return (
    <div className="space-y-5 pb-12">
      <SectionTitle count={view.length} desc="지시가 나온 회차와, 이후 회차의 보고를 연결해 보여줍니다">
        교육감 지시사항
      </SectionTitle>

      {/* ── 필터 ── */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={dept} onChange={(e) => setDept(e.target.value)}
          aria-label="부서"
          className="h-11 px-3 rounded-md border border-slate-300 bg-white text-sm font-semibold text-slate-800"
        >
          <option value="ALL">전체 부서</option>
          {depts.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>

        <select
          value={type} onChange={(e) => setType(e.target.value)}
          aria-label="유형"
          className="h-11 px-3 rounded-md border border-slate-300 bg-white text-sm font-semibold text-slate-800"
        >
          <option value="ALL">지시·당부·질의 전체</option>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>

        <div className="flex rounded-md border border-slate-300 overflow-hidden" role="group" aria-label="이행 상태">
          {([['ALL', '전체'], ['open', '보고 없음'], ['reported', '보고 있음']] as const).map(([v, label]) => (
            <button
              key={v}
              type="button"
              aria-pressed={status === v}
              onClick={() => setStatus(v)}
              className={`h-11 px-3.5 text-sm font-bold transition-colors ${
                status === v ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:text-slate-900'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <input
          type="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="지시 내용 검색"
          aria-label="지시 내용 검색"
          className="h-11 px-3 rounded-md border border-slate-300 bg-white text-sm flex-1 min-w-[200px]
                     text-slate-900 placeholder-slate-400 outline-none focus:border-blue-600"
        />

        <button
          type="button"
          aria-pressed={showQuote}
          onClick={() => setShowQuote((v) => !v)}
          className={`h-11 px-3.5 rounded-md border text-sm font-bold transition-colors ${
            showQuote ? 'bg-blue-600 border-blue-600 text-white'
                      : 'bg-white border-slate-300 text-slate-600 hover:text-slate-900'
          }`}
        >
          원문 인용
        </button>
      </div>

      {/* ── 목록 ── */}
      {view.length === 0 ? (
        <EmptyState
          icon={<ListChecks className="w-6 h-6" />}
          title="조건에 맞는 지시사항이 없습니다"
          desc="필터를 조정하거나 검색어를 지워 보세요."
        >
          <button
            type="button" onClick={reset}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-50 text-blue-700
                       hover:bg-blue-100 font-bold text-sm rounded-md transition"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            필터 초기화
          </button>
        </EmptyState>
      ) : (
        <div className="space-y-2">
          {view.map(({ row, trace }) => (
            <article
              key={row.id}
              className="bg-white rounded-lg border border-slate-200 p-5 hover:border-blue-600
                         transition-colors flex flex-col md:flex-row md:items-start gap-4"
            >
              <div className="flex-1 min-w-0 space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge tone="blue">{row.dept || '전 부서'}</Badge>
                  <Badge>{row.type || '지시'}</Badge>
                  {row.due && <Badge tone="amber">{row.due}</Badge>}
                  <span className="text-xs text-slate-500">{korDate(row.meeting.date)}</span>
                  <TimeLink videoId={row.meeting.videoId} t={row.t} />
                </div>
                <p className="text-base font-bold text-slate-900 leading-snug">
                  {highlight(row.text, q)}
                </p>
                {showQuote && row.quote && <Quote>{row.quote}</Quote>}
              </div>

              <div className="md:w-56 shrink-0 md:text-right space-y-1">
                {trace ? (
                  <>
                    <Badge tone={trace.exact ? 'green' : 'slate'}>
                      {trace.exact ? '처리 결과 보고됨' : '같은 부서 보고 있음'}
                    </Badge>
                    <p className="text-xs text-slate-500">{korDate(trace.meeting.date)} 회의</p>
                    <p className="text-xs text-slate-600 line-clamp-3">{trace.followup.report}</p>
                  </>
                ) : (
                  <Badge tone="amber">이후 보고 확인 안 됨</Badge>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400 px-1">
        ‘같은 부서 보고 있음’은 지시와 보고를 직접 연결한 것이 아니라 부서가 같아 추정한 것입니다.
        확정 판단은 타임스탬프를 눌러 원 영상으로 확인하세요.
      </p>
    </div>
  );
};
