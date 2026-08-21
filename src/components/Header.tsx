import React from 'react';
import { Captions } from 'lucide-react';
import { korDate } from '../lib/util';
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
  /** 가장 최근 회의 날짜 (ISO). 자료가 어디까지 와 있는지 보여준다. */
  latestDate?: string | null;
}

export const Header: React.FC<Props> = ({ activeTab, setActiveTab, latestDate }) => (
  <header className="bg-white sticky top-0 z-30 border-b border-slate-200">
    {/* 안내 띠 — 공식 회의록이 아님을 먼저 밝힌다 (KRDS 마스트헤드 관례) */}
    <div className="bg-slate-50 text-slate-600 border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs">
        <span>
          유튜브 자동생성 자막을 정리한 <strong className="font-bold text-slate-900">비공식</strong> 자료입니다
        </span>
        {/*
          예전에는 `index.updatedAt`(수집기가 마지막으로 돈 시각)을 '최근 갱신' 으로 보여줬다.
          그런데 요약을 손으로 고쳐도 이 값은 안 바뀌어서, 실제와 다른 시각이 떠 있었다.
          읽는 사람이 알고 싶은 건 '자료가 어느 회의까지 와 있나' 이지 처리 시각이 아니다.
          가장 최근 회의 날짜는 데이터에서 바로 나오므로 어긋날 수가 없다.
        */}
        {latestDate && (
          <span className="shrink-0">최근 회의 {korDate(latestDate)}</span>
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
