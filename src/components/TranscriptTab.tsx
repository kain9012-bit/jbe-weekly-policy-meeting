import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Captions, Copy, Check, Download, Search } from 'lucide-react';
import type { Cue, IndexDoc, TranscriptDoc } from '../types';
import { Badge, EmptyState, SampleNotice, TimeLink } from './Ui';
import { duration, highlight, korDate, mmss } from '../lib/util';

interface Props {
  index: IndexDoc;
  currentId: string;
  setCurrentId: (id: string) => void;
  transcript: TranscriptDoc | null;
  loading: boolean;
  /** 이 시각(초)의 발언으로 데려간다. 지시사항 탭에서 넘어올 때 쓴다. */
  jumpTo?: number | null;
  onJumped?: () => void;
}

type View = 'lines' | 'flow';

export const TranscriptTab: React.FC<Props> = ({
  index, currentId, setCurrentId, transcript, loading, jumpTo, onJumped,
}) => {
  const [q, setQ] = useState('');
  const [view, setView] = useState<View>('lines');
  const [block, setBlock] = useState('ALL');
  const [copied, setCopied] = useState(false);

  const entry = index.meetings.find((m) => m.id === currentId);
  const boxRef = useRef<HTMLDivElement>(null);
  const [flash, setFlash] = useState<number | null>(null);

  /** 부서 보고 구간 목록 — 회의에 나온 순서대로 */
  const blocks = useMemo(() => {
    const seen: string[] = [];
    for (const c of transcript?.cues ?? []) {
      if (c.block && !seen.includes(c.block)) seen.push(c.block);
    }
    return seen;
  }, [transcript]);

  const cues = useMemo(() => {
    if (!transcript) return [];
    const k = q.trim().toLowerCase();
    return transcript.cues.filter(
      (c) =>
        (block === 'ALL' || c.block === block) &&
        (!k || c.text.toLowerCase().includes(k)),
    );
  }, [transcript, q, block]);

  /**
   * 문장을 발언(문단) 단위로 다시 묶는다.
   * 검색·구간 필터로 걸러진 뒤에도 문단이 유지되도록 여기서 묶는다.
   */
  const turns = useMemo(() => {
    const out: Cue[][] = [];
    for (const c of cues) {
      if (c.turnStart || out.length === 0) out.push([]);
      out[out.length - 1].push(c);
    }
    return out;
  }, [cues]);

  /**
   * 넘겨받은 시각의 발언으로 데려간다.
   * 지시가 나온 순간이 발언 한가운데인 일이 많으므로, **그 시각을 넘지 않는
   * 마지막 발언**을 고른다. 정확히 일치하는 발언만 찾으면 대개 못 찾는다.
   */
  useEffect(() => {
    if (jumpTo == null || !transcript) return;
    const heads = transcript.cues.filter((c) => c.turnStart);
    const target = [...heads].reverse().find((c) => c.t <= jumpTo) ?? heads[0];
    if (!target) return;
    // 필터가 걸려 있으면 대상이 화면에 없다. 먼저 푼다.
    setBlock('ALL');
    setQ('');
    const id = window.setTimeout(() => {
      const el = boxRef.current?.querySelector<HTMLElement>(`[data-t="${target.t}"]`);
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setFlash(target.t);
      window.setTimeout(() => setFlash(null), 2200);
      onJumped?.();
    }, 60);
    return () => window.clearTimeout(id);
  }, [jumpTo, transcript, onJumped]);

  const fullText = useMemo(() => {
    if (!transcript) return '';
    let cur = '';
    return transcript.cues
      .map((c) => {
        const head = c.speaker && c.speaker !== cur ? `${c.speaker}: ` : '';
        if (c.speaker) cur = c.speaker;
        return `[${mmss(c.t)}] ${head}${c.text}`;
      })
      .join('\n');
  }, [transcript]);

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText(fullText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  const downloadTxt = () => {
    if (!transcript) return;
    const blob = new Blob([`${transcript.title}\n${transcript.videoUrl}\n\n${fullText}`], {
      type: 'text/plain;charset=utf-8',
    });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${transcript.id}_회의록.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="space-y-5 pb-12">
      {/* ── 조작 줄 ── */}
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="trMeeting" className="sr-only">회차 선택</label>
        <select
          id="trMeeting"
          value={currentId}
          onChange={(e) => setCurrentId(e.target.value)}
          className="h-11 px-3 rounded-md border border-slate-300 bg-white text-sm font-semibold text-slate-800"
        >
          {index.meetings.map((m) => (
            <option key={m.id} value={m.id}>
              {m.title} {m.hasTranscript ? '' : '(자막 없음)'}
            </option>
          ))}
        </select>

        {blocks.length > 0 && (
          <>
            <label htmlFor="trBlock" className="sr-only">부서 보고 구간</label>
            <select
              id="trBlock"
              value={block}
              onChange={(e) => setBlock(e.target.value)}
              className="h-11 px-3 rounded-md border border-slate-300 bg-white text-sm font-semibold text-slate-800"
            >
              <option value="ALL">전체 구간</option>
              {blocks.map((b) => <option key={b} value={b}>{b} 보고</option>)}
            </select>
          </>
        )}

        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" aria-hidden="true" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="이 회의록 안에서 찾기"
            className="w-full h-11 pl-9 pr-3 rounded-md border border-slate-300 bg-white text-sm
                       text-slate-900 placeholder-slate-400 outline-none focus:border-blue-600"
          />
        </div>

        <div className="flex rounded-md border border-slate-300 overflow-hidden" role="group" aria-label="보기 방식">
          {([['lines', '시간별'], ['flow', '이어보기']] as [View, string][]).map(([v, label]) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className={`h-11 px-3.5 text-sm font-bold transition-colors ${
                view === v ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:text-slate-900'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={copyAll}
          disabled={!transcript}
          className="h-11 px-3.5 rounded-md border border-slate-300 bg-white text-sm font-bold
                     text-slate-600 hover:text-slate-900 disabled:opacity-40 inline-flex items-center gap-1.5"
        >
          {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
          {copied ? '복사됨' : '전체 복사'}
        </button>

        <button
          type="button"
          onClick={downloadTxt}
          disabled={!transcript}
          className="h-11 px-3.5 rounded-md border border-slate-300 bg-white text-sm font-bold
                     text-slate-600 hover:text-slate-900 disabled:opacity-40 inline-flex items-center gap-1.5"
        >
          <Download className="w-4 h-4" />
          TXT
        </button>
      </div>

      {loading && <p className="text-sm text-slate-500" role="status">자막을 불러오는 중입니다…</p>}

      {!loading && !transcript && (
        <EmptyState
          icon={<Captions className="w-6 h-6" />}
          title={
            entry ? `${entry.title} — 자막이 아직 없습니다` : '이 회차의 자막이 아직 없습니다'
          }
          desc={
            entry
              ? `${duration(entry.durationSec)} 분량의 영상입니다. 자막 확보가 이 서비스의 1단계입니다. `
                + '아래 명령을 사무실 PC(또는 자체 호스팅 러너)에서 실행하면 전 회차 자막이 채워집니다.'
              : '자막 확보가 이 서비스의 1단계입니다. 아래 명령을 실행하면 전 회차 자막이 채워집니다.'
          }
        >
          <code className="inline-block text-xs bg-slate-50 border border-slate-200 rounded px-3 py-2 text-slate-700">
            python collector/fetch_transcripts.py --all
          </code>
        </EmptyState>
      )}

      {transcript && (
        <>
          {transcript._sample && <SampleNotice note={transcript._sampleNote} />}

          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge>{korDate(transcript.date)}</Badge>
            <Badge>{duration(transcript.durationSec)}</Badge>
            {/* 줄 수·글자 수·'부서 확인' 같은 내부 수치는 읽는 사람이 쓸 데가 없다. */}
            {transcript.turnCount ? <Badge>발언 {transcript.turnCount}개</Badge> : null}
            <a
              href={transcript.videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-bold text-blue-700 hover:underline underline-offset-4"
            >
              영상 열기
            </a>
          </div>

          {(q || block !== 'ALL') && (
            <p className="text-sm text-slate-600 px-1">
              <strong className="text-blue-700 font-bold tabular-nums">{cues.length}</strong>문장
              {block !== 'ALL' && <> · {block} 보고 구간</>}
            </p>
          )}

          <div ref={boxRef} className="bg-white rounded-lg border border-slate-200 p-5">
            {turns.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-8">검색어와 맞는 발언이 없습니다.</p>
            ) : view === 'lines' ? (
              <div className="space-y-4">
                {turns.map((turn, ti) => {
                  const head = turn[0];
                  // 구간이 바뀌는 자리에 '○○과 보고' 머리글을 넣는다.
                  const newBlock = head.block && head.block !== turns[ti - 1]?.[0]?.block;
                  return (
                    <React.Fragment key={`${head.t}-${ti}`}>
                      {newBlock && (
                        <h3 className="flex items-center gap-2 pt-4 mt-2 border-t border-slate-200 first:border-0 first:mt-0 first:pt-0">
                          <span className="text-sm font-bold text-blue-800">{head.block}</span>
                          <span className="text-xs text-slate-400">보고 구간</span>
                        </h3>
                      )}
                      <div
                        data-t={head.t}
                        className={`grid grid-cols-[68px_1fr] gap-3 rounded-md transition-colors ${
                          flash === head.t ? 'bg-amber-50 ring-2 ring-amber-300 -mx-2 px-2 py-1' : ''
                        }`}
                      >
                        <TimeLink videoId={transcript.videoId} t={head.t} />
                        <div className="min-w-0">
                          {head.speaker && (
                            <p className="mb-1">
                              <Badge tone={head.speaker === '교육감' ? 'amber' : 'blue'}>
                                {head.speaker}
                              </Badge>
                            </p>
                          )}
                          {turn.map((c, i) => (
                            <p
                              key={`${c.t}-${i}`}
                              className="text-slate-800 leading-[1.85]"
                            >
                              {highlight(c.text, q)}
                            </p>
                          ))}
                        </div>
                      </div>
                    </React.Fragment>
                  );
                })}
              </div>
            ) : (
              <div className="space-y-3">
                {turns.map((turn, ti) => (
                  <p key={`${turn[0].t}-${ti}`} className="text-slate-800 leading-[2] text-[1.0625rem]">
                    {turn[0].speaker && (
                      <strong className="font-bold text-slate-900 mr-1.5">{turn[0].speaker}:</strong>
                    )}
                    {turn.map((c, i) => (
                      <React.Fragment key={`${c.t}-${i}`}>{highlight(c.text, q)}{' '}</React.Fragment>
                    ))}
                  </p>
                ))}
              </div>
            )}
          </div>

          {/*
            예전에는 '자막 원문' 토글과 '자막 출처' 표시가 있었지만 뺐다.
            보여주던 '원문' 도 기계의 추측이라 대조해 봐야 확인되는 게 없었고,
            일부 문장에만 출처를 표시하면 나머지는 검증됐다는 착각을 준다.
            회의록 전체가 기계가 받아쓴 것이다. 확인 경로는 모든 줄에 붙어 있는
            타임스탬프 → 영상 하나뿐이고, 그 사실만 아래에 적는다.
          */}
          <p className="text-xs text-slate-400 px-1">
            이 회의록은 영상의 음성을 기계가 받아쓴 것입니다. 사람이 확인하지 않은 문장이 섞여 있을 수 있으니,
            정확한 내용은 왼쪽 시각을 눌러 영상에서 확인하세요.
          </p>
        </>
      )}
    </div>
  );
};
