import React from 'react';
import { Play } from 'lucide-react';
import { mmss, ytAt } from '../lib/util';

/** 부서·상태 배지 — KRDS 색 토큰 위에서 쓰는 공통 조각 */
export const Badge: React.FC<{
  tone?: 'blue' | 'slate' | 'amber' | 'green' | 'red';
  children: React.ReactNode;
}> = ({ tone = 'slate', children }) => {
  const cls = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    slate: 'bg-slate-50 text-slate-700 border-slate-200',
    amber: 'bg-amber-50 text-amber-800 border-amber-200',
    green: 'bg-green-50 text-green-700 border-green-100',
    red: 'bg-red-50 text-red-700 border-red-200',
  }[tone];
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-bold whitespace-nowrap ${cls}`}>
      {children}
    </span>
  );
};

/** 영상의 해당 시점으로 가는 링크. 요약을 원문으로 검증하게 하는 핵심 장치다. */
export const TimeLink: React.FC<{ videoId: string; t: number; label?: string }> = ({
  videoId,
  t,
  label,
}) => (
  <a
    href={ytAt(videoId, t)}
    target="_blank"
    rel="noopener noreferrer"
    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-slate-200
               text-xs font-bold text-slate-600 tabular-nums hover:border-blue-600
               hover:text-blue-700 transition-colors shrink-0"
    title="영상의 이 지점으로 이동"
  >
    <Play className="w-3 h-3" aria-hidden="true" />
    {label ?? mmss(t)}
  </a>
);

/** 자막에서 그대로 따온 문장 */
export const Quote: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <blockquote className="mt-2 pl-3 border-l-[3px] border-slate-200 text-sm text-slate-600">
    “{children}”
  </blockquote>
);

export const SectionTitle: React.FC<{
  children: React.ReactNode;
  count?: number;
  desc?: string;
}> = ({ children, count, desc }) => (
  <div className="flex items-baseline gap-2 flex-wrap">
    <h3 className="text-lg font-bold text-slate-900">{children}</h3>
    {count !== undefined && (
      <span className="text-sm font-bold text-blue-700 tabular-nums">{count}건</span>
    )}
    {desc && <span className="text-xs text-slate-500">{desc}</span>}
  </div>
);

export const EmptyState: React.FC<{
  icon: React.ReactNode;
  title: string;
  desc?: string;
  children?: React.ReactNode;
}> = ({ icon, title, desc, children }) => (
  <div className="bg-white rounded-lg border border-slate-200 p-12 text-center space-y-3">
    <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
      {icon}
    </div>
    <h3 className="text-base font-bold text-slate-800">{title}</h3>
    {desc && <p className="text-sm text-slate-500 max-w-md mx-auto">{desc}</p>}
    {children}
  </div>
);

/** 자동 생성물임을 알리는 띠 */
export const SampleNotice: React.FC<{ note?: string }> = ({ note }) => (
  <div role="note" className="rounded-lg border border-amber-300 bg-amber-50 p-4 space-y-1">
    <p className="font-bold text-slate-900 text-sm">아직 표본 데이터입니다</p>
    <p className="text-sm text-slate-700">
      {note ??
        '수집기를 한 번 돌리면 실제 자막·요약으로 교체됩니다. 없는 자료를 임의로 채워 보여주지 않습니다.'}
    </p>
    <code className="inline-block text-xs bg-white border border-amber-200 rounded px-2 py-1 text-slate-700">
      python collector/fetch_transcripts.py --all
    </code>
  </div>
);
