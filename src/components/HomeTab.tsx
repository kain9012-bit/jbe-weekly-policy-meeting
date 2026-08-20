import React, { useState } from 'react';
import { Search, ArrowRight, FileText, Captions, ListChecks, CircleAlert, CircleCheck, UserRound } from 'lucide-react';
import type { ActiveTab, IndexDoc } from '../types';
import { Badge, SectionTitle } from './Ui';
import { duration, korDate, stageOf, STAGE_LABEL } from '../lib/util';

interface Props {
  index: IndexDoc;
  onNavigate: (tab: ActiveTab, query?: string, meetingId?: string) => void;
}

export const HomeTab: React.FC<Props> = ({ index, onNavigate }) => {
  const [q, setQ] = useState('');

  const meetings = index.meetings;
  const withTranscript = meetings.filter((m) => m.hasTranscript);
  const withRefined = meetings.filter((m) => m.hasRefined);
  const withSummary = meetings.filter((m) => m.hasSummary);
  const totalCues = meetings.reduce((n, m) => n + (m.cueCount || 0), 0);
  const totalDirectives = meetings.reduce((n, m) => n + (m.directiveCount || 0), 0);
  const latest = withSummary[0] ?? meetings[0];

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onNavigate('search', q.trim());
  };

  const QUICK = ['위원회', '공약', '창업 동아리', '변호사', '학부모', '청렴', '예산'];

  return (
    <div className="space-y-8 pb-12">
      {/* ── 검색 띠 ── */}
      <section
        className="relative left-1/2 w-screen -translate-x-1/2 -mt-6
                   px-4 sm:px-6 lg:px-8 py-10 sm:py-16
                   bg-blue-50 border-b border-blue-100"
      >
        <div className="max-w-4xl mx-auto text-center space-y-6">
          <h2 className="text-3xl sm:text-[2.75rem] font-bold text-slate-900 leading-tight">
            <span className="block sm:inline">주간정책회의에서</span>{' '}
            <span className="text-blue-700">무슨 말이 오갔는지</span>
          </h2>
          <p className="text-base sm:text-lg text-slate-600">
            매주 생중계되는 회의의 <strong className="font-bold text-slate-900">자막 전문</strong> ·
            <strong className="font-bold text-slate-900"> 교육감 지시사항</strong> ·
            <strong className="font-bold text-slate-900"> 부서별 보고</strong>를 한곳에서 찾습니다
          </p>

          <form onSubmit={submit} className="max-w-2xl mx-auto">
            <label htmlFor="heroSearch" className="sr-only">회의 내용 검색</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search
                  className="w-6 h-6 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
                  aria-hidden="true"
                />
                <input
                  id="heroSearch"
                  type="search"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="예: 위원회 정비, 창업 동아리, 학부모 아카데미"
                  className="w-full h-16 pl-12 pr-4 text-lg text-slate-900 placeholder-slate-400
                             bg-white border-2 border-blue-600 rounded-lg outline-none focus:border-blue-700"
                />
              </div>
              <button
                type="submit"
                className="h-16 px-5 sm:px-10 bg-blue-600 hover:bg-blue-700 text-white font-bold
                           text-lg rounded-lg transition-colors flex items-center gap-2 shrink-0"
              >
                <span>검색</span>
                <ArrowRight className="w-4 h-4 hidden sm:block" aria-hidden="true" />
              </button>
            </div>
          </form>

          <div className="flex flex-wrap items-center justify-center gap-2">
            {QUICK.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => onNavigate('search', k)}
                className="px-3 py-1.5 rounded-full bg-white border border-blue-200 text-sm
                           font-semibold text-blue-700 hover:bg-blue-100 transition-colors"
              >
                #{k}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ── 지표 ── */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { icon: FileText, label: '수집한 회의', value: `${meetings.length}회차`, sub: '게시판 기준' },
          { icon: Captions, label: '자막 확보', value: `${withTranscript.length}회차`, sub: `${totalCues.toLocaleString()}줄 · ${duration(meetings.reduce((n, m) => n + (m.durationSec || 0), 0))}` },
          { icon: UserRound, label: '교정·화자', value: `${withRefined.length}회차`, sub: '문맥 교정 후 화자 태깅' },
          { icon: ListChecks, label: '정리된 지시사항', value: `${totalDirectives}건`, sub: `요약 완료 ${withSummary.length}회차` },
        ].map(({ icon: Icon, label, value, sub }) => (
          <div key={label} className="bg-white rounded-lg border border-slate-200 p-4 space-y-1">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-500">
              <Icon className="w-3.5 h-3.5" aria-hidden="true" />
              {label}
            </div>
            <p className="text-2xl font-bold text-slate-900 tabular-nums">{value}</p>
            <p className="text-xs text-slate-500">{sub}</p>
          </div>
        ))}
      </section>

      {/* ── 최근 회의 ── */}
      {latest && (
        <section className="space-y-3">
          <SectionTitle desc={korDate(latest.date)}>가장 최근 회의</SectionTitle>
          <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge tone="blue">{latest.id}</Badge>
              <Badge>{duration(latest.durationSec)}</Badge>
              {latest.hasSummary ? (
                <Badge tone="green">지시사항 {latest.directiveCount}건</Badge>
              ) : (
                <Badge tone="amber">요약 미생성</Badge>
              )}
            </div>
            <h3 className="text-xl font-bold text-slate-900">{latest.title}</h3>
            {latest.summary ? (
              <p className="text-slate-700 leading-relaxed line-clamp-5">{latest.summary}</p>
            ) : (
              <p className="text-slate-500 text-sm">아직 요약이 만들어지지 않았습니다.</p>
            )}
            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={() => onNavigate('meeting', undefined, latest.id)}
                className="px-4 py-2 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-sm font-bold"
              >
                회의 요약 보기
              </button>
              <button
                type="button"
                onClick={() => onNavigate('transcript', undefined, latest.id)}
                className="px-4 py-2 rounded-md border border-slate-300 hover:border-blue-600
                           hover:text-blue-700 text-slate-700 text-sm font-bold"
              >
                회의록 전문 보기
              </button>
            </div>
          </div>
        </section>
      )}

      {/* ── 수집 현황 ── */}
      <section className="space-y-3">
        <SectionTitle desc="자막을 먼저 확보한 뒤 요약을 만듭니다">수집 현황</SectionTitle>
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500">
                  <th className="text-left font-bold px-4 py-3 whitespace-nowrap">회차</th>
                  <th className="text-left font-bold px-4 py-3 whitespace-nowrap">일자</th>
                  <th className="text-left font-bold px-4 py-3">제목</th>
                  <th className="text-right font-bold px-4 py-3 whitespace-nowrap">길이</th>
                  <th className="text-right font-bold px-4 py-3 whitespace-nowrap">자막 줄</th>
                  <th className="text-left font-bold px-4 py-3 whitespace-nowrap">상태</th>
                </tr>
              </thead>
              <tbody>
                {meetings.map((m) => {
                  const st = stageOf(m);
                  return (
                    <tr key={m.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                      <td className="px-4 py-3 font-bold text-slate-900 tabular-nums whitespace-nowrap">{m.id}</td>
                      <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{korDate(m.date)}</td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => onNavigate(m.hasSummary ? 'meeting' : 'transcript', undefined, m.id)}
                          className="font-semibold text-slate-800 hover:text-blue-700 text-left"
                        >
                          {m.title}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600 tabular-nums whitespace-nowrap">
                        {duration(m.durationSec)}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-600 tabular-nums whitespace-nowrap">
                        {m.cueCount ? m.cueCount.toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1.5">
                          {st === 'done' && <CircleCheck className="w-4 h-4 text-green-600" aria-hidden="true" />}
                          {st === 'refined' && <UserRound className="w-4 h-4 text-blue-600" aria-hidden="true" />}
                          {st === 'transcript' && <Captions className="w-4 h-4 text-slate-500" aria-hidden="true" />}
                          {st === 'pending' && <CircleAlert className="w-4 h-4 text-amber-600" aria-hidden="true" />}
                          <span className="font-semibold text-slate-700">{STAGE_LABEL[st]}</span>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
        {index._note && <p className="text-xs text-slate-500 px-1">{index._note}</p>}
      </section>
    </div>
  );
};
