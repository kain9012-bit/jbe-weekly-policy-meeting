import React from 'react';
import { FileText, ChevronRight, Download } from 'lucide-react';
import type { ActiveTab, IndexDoc, MeetingDoc } from '../types';
import { Badge, EmptyState, Quote, SampleNotice, SectionTitle, TimeLink } from './Ui';
import { duration, korDate } from '../lib/util';

interface Props {
  index: IndexDoc;
  currentId: string;
  setCurrentId: (id: string) => void;
  meeting: MeetingDoc | null;
  loading: boolean;
  onNavigate: (tab: ActiveTab, query?: string, meetingId?: string) => void;
}

const progressTone = (p: string) =>
  p === '완료' ? 'green' : p === '미착수' ? 'amber' : 'slate';

export const MeetingTab: React.FC<Props> = ({
  index, currentId, setCurrentId, meeting, loading, onNavigate,
}) => {
  const entry = index.meetings.find((m) => m.id === currentId);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6 items-start pb-12">
      {/* ── 회차 목록 ── */}
      <aside className="bg-white rounded-lg border border-slate-200 p-2 lg:sticky lg:top-32">
        <ul className="space-y-1 max-h-[70vh] overflow-y-auto">
          {index.meetings.map((m) => {
            const on = m.id === currentId;
            return (
              <li key={m.id}>
                <button
                  type="button"
                  onClick={() => setCurrentId(m.id)}
                  aria-current={on}
                  className={`w-full text-left px-3 py-2.5 rounded-md transition-colors ${
                    on ? 'bg-blue-50 text-blue-800' : 'hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <span className="block text-sm font-bold">{m.title}</span>
                  <span className="block text-xs text-slate-500 mt-0.5">
                    {korDate(m.date)} · {m.hasSummary ? `지시 ${m.directiveCount}건` : '요약 없음'}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </aside>

      {/* ── 본문 ── */}
      <div className="min-w-0 space-y-6">
        {loading && <p className="text-sm text-slate-500" role="status">회의 자료를 불러오는 중입니다…</p>}

        {!loading && !meeting && (
          <EmptyState
            icon={<FileText className="w-6 h-6" />}
            title="아직 이 회차의 요약이 없습니다"
            desc={
              entry?.hasTranscript
                ? '자막은 확보돼 있습니다. 요약만 아직 만들어지지 않았습니다. 회의록 전문은 지금 바로 볼 수 있습니다.'
                : '자막부터 확보해야 합니다. 수집기를 실행하면 자막을 받은 뒤 요약을 만듭니다.'
            }
          >
            <button
              type="button"
              onClick={() => onNavigate('transcript', undefined, currentId)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-50 text-blue-700
                         hover:bg-blue-100 font-bold text-sm rounded-md transition"
            >
              회의록 전문으로 이동
              <ChevronRight className="w-4 h-4" />
            </button>
          </EmptyState>
        )}

        {meeting && (
          <>
            {meeting._sample && <SampleNotice note={meeting._sampleNote} />}

            <div className="flex items-center gap-2 flex-wrap">
              <Badge tone="blue">{meeting.id}</Badge>
              <Badge>{korDate(meeting.date)}</Badge>
              <Badge>{duration(meeting.durationSec)}</Badge>
              <a
                href={meeting.postUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-bold text-blue-700 hover:underline underline-offset-4"
              >
                원 게시글
              </a>
            </div>

            <div className="flex items-start justify-between gap-4 flex-wrap">
              <h2 className="text-2xl font-bold text-slate-900">{meeting.title}</h2>
              {entry?.hasHandout && (
                <a
                  href={`${import.meta.env.BASE_URL || './'}data/handouts/${meeting.id}.hwpx`.replace(
                    /([^:]\/)\/+/g,
                    '$1',
                  )}
                  download={`${meeting.id}_전달사항.hwpx`}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-slate-900
                             hover:bg-slate-800 text-white text-sm font-bold shrink-0"
                >
                  <Download className="w-4 h-4" aria-hidden="true" />
                  전달사항 내려받기 (hwpx)
                </a>
              )}
            </div>

            <div className="rounded-lg overflow-hidden border border-slate-200 bg-black aspect-video">
              <iframe
                key={meeting.videoId}
                src={`https://www.youtube.com/embed/${meeting.videoId}`}
                title={meeting.title}
                className="w-full h-full"
                allow="accelerometer; encrypted-media; picture-in-picture; fullscreen"
                allowFullScreen
              />
            </div>

            {/* 한눈에 보기 */}
            {meeting.highlights.length > 0 && (
              <section className="bg-blue-50 border border-blue-100 rounded-lg p-5 space-y-2.5">
                <h3 className="text-sm font-bold text-blue-900">한눈에 보기</h3>
                <ul className="space-y-2">
                  {meeting.highlights.map((h, i) => (
                    <li key={i} className="flex gap-2.5 text-slate-800 font-medium">
                      <span className="mt-2 w-1.5 h-1.5 rounded-full bg-blue-600 shrink-0" aria-hidden="true" />
                      <span>{h}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* 회의 요약 */}
            {meeting.summary && (
              <section className="space-y-2">
                <SectionTitle>회의 요약</SectionTitle>
                <p className="text-slate-700 leading-[1.9] bg-white rounded-lg border border-slate-200 p-5">
                  {meeting.summary}
                </p>
              </section>
            )}

            {/* 지난주 지시 처리 결과 */}
            <section className="space-y-3">
              <SectionTitle count={meeting.followups.length} desc="지난 회의 지시사항에 대한 부서 보고">
                처리 결과 보고
              </SectionTitle>
              <div className="space-y-2">
                {meeting.followups.map((f, i) => (
                  <div key={i} className="bg-white rounded-lg border border-slate-200 p-4 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge tone="blue">{f.dept || '부서 미상'}</Badge>
                      <Badge tone={progressTone(f.progress)}>{f.progress}</Badge>
                      <TimeLink videoId={meeting.videoId} t={f.t} />
                    </div>
                    <p className="text-slate-700">{f.report}</p>
                    {f.quote && <Quote>{f.quote}</Quote>}
                  </div>
                ))}
                {meeting.followups.length === 0 && (
                  <p className="text-sm text-slate-500 px-1">정리된 처리 결과가 없습니다.</p>
                )}
              </div>
            </section>

            {/* 안건 */}
            <section className="space-y-3">
              <SectionTitle count={meeting.agenda.length}>안건</SectionTitle>
              <div className="space-y-2">
                {meeting.agenda.map((a) => (
                  <div key={a.seq} className="bg-white rounded-lg border border-slate-200 p-4 space-y-1.5
                                              hover:border-blue-600 transition-colors">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge tone="blue">{a.dept || '부서 미상'}</Badge>
                      <span className="font-bold text-slate-900">{a.topic}</span>
                      <TimeLink videoId={meeting.videoId} t={a.t} />
                    </div>
                    <p className="text-slate-600 text-sm leading-relaxed">{a.gist}</p>
                  </div>
                ))}
                {meeting.agenda.length === 0 && (
                  <p className="text-sm text-slate-500 px-1">정리된 안건이 없습니다.</p>
                )}
              </div>
            </section>

            {/* 신규 지시사항 */}
            <section className="space-y-3">
              <SectionTitle count={meeting.directives.length} desc="이 회의에서 새로 나온 것">
                교육감 지시사항
              </SectionTitle>
              <div className="space-y-2">
                {meeting.directives.map((d) => (
                  <div key={d.id} className="bg-white rounded-lg border border-slate-200 p-4 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge tone="blue">{d.dept || '전 부서'}</Badge>
                      <Badge>{d.type || '지시'}</Badge>
                      {d.due && <Badge tone="amber">{d.due}</Badge>}
                      <TimeLink videoId={meeting.videoId} t={d.t} />
                    </div>
                    <p className="text-slate-900 font-semibold">{d.text}</p>
                    {d.quote && <Quote>{d.quote}</Quote>}
                  </div>
                ))}
                {meeting.directives.length === 0 && (
                  <p className="text-sm text-slate-500 px-1">정리된 지시사항이 없습니다.</p>
                )}
              </div>
            </section>

            {/*
              '자막 교정' 목록은 여기서 뺐다.
              회의에서 무슨 일이 있었나를 보러 온 사람에게 '자막이 누리집을 무리집으로
              들었다'는 건 회의 내용이 아니라 시스템 사정이다. 그 정보가 필요한 자리는
              회의록 전문 탭의 '자막 원문' 토글이다 — 교정된 문장마다 원문을 그 자리에
              붙여 보여주므로, 맥락 안에서 볼 사람만 본다.
            */}

            <p className="text-xs text-slate-400">
              자막 경로 {meeting.meta.captionSource || '—'}
              {entry?.hasTranscript && (
                <>
                  {' · '}
                  <button
                    type="button"
                    onClick={() => onNavigate('transcript', undefined, meeting.id)}
                    className="underline underline-offset-2 hover:text-slate-600"
                  >
                    회의록 전문에서 원문 대조
                  </button>
                </>
              )}
            </p>
          </>
        )}
      </div>
    </div>
  );
};
