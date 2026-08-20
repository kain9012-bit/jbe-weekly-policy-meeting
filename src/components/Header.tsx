import React from 'react';
import { Captions } from 'lucide-react';
import type { ActiveTab } from '../types';

const TABS: { id: ActiveTab; label: string }[] = [
  { id: 'home', label: '홈' },
  { id: 'meeting', label: '회의 요약' },
  { id: 'transcript', label: '회의록 전문' },
  { id: 'directives', label: '지시사항' },
  { id: 'search', label: '통합검색' },
];

interface Props {
  activeTab: ActiveTab;
  setActiveTab: (t: ActiveTab) => void;
  updatedAt?: string | null;
}

export const Header: React.FC<Props> = ({ activeTab, setActiveTab, updatedAt }) => (
  <header className="bg-white sticky top-0 z-30 border-b border-slate-200">
    {/* 안내 띠 — 공식 회의록이 아님을 먼저 밝힌다 (KRDS 마스트헤드 관례) */}
    <div className="bg-slate-50 text-slate-600 border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs">
        <span>
          유튜브 자동생성 자막을 정리한 <strong className="font-bold text-slate-900">비공식</strong> 자료입니다
        </span>
        {updatedAt && (
          <span className="shrink-0 tabular-nums">최근 갱신 {updatedAt.slice(0, 16).replace('T', ' ')}</span>
        )}
      </div>
    </div>

    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-center justify-between gap-x-6">
        <button
          type="button"
          onClick={() => setActiveTab('home')}
          className="flex items-center gap-2.5 py-3.5 text-left group shrink-0"
        >
          <span className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shrink-0 group-hover:bg-blue-700 transition-colors">
            <Captions className="w-5 h-5" aria-hidden="true" />
          </span>
          <span className="flex items-baseline gap-2">
            <span className="text-lg font-bold text-slate-900 whitespace-nowrap">주간정책회의 브리핑</span>
            <span className="hidden sm:inline text-xs font-medium text-slate-400 whitespace-nowrap">
              전북특별자치도교육청
            </span>
          </span>
        </button>

        <nav aria-label="주 메뉴" className="-mb-px w-full sm:w-auto">
          <ul className="flex overflow-x-auto overflow-y-hidden no-scrollbar" role="tablist">
            {TABS.map(({ id, label }) => {
              const on = activeTab === id;
              return (
                <li key={id} role="presentation" className="shrink-0">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={on}
                    onClick={() => setActiveTab(id)}
                    className={`px-3.5 sm:px-4 py-4 text-base font-bold whitespace-nowrap
                                border-b-[3px] transition-colors ${
                                  on
                                    ? 'text-blue-700 border-blue-600'
                                    : 'text-slate-600 border-transparent hover:text-slate-900'
                                }`}
                  >
                    {label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </div>
  </header>
);
