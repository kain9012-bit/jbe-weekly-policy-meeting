import React, { useMemo, useState } from 'react';
import { Captions, Copy, Check, Download, Search } from 'lucide-react';
import type { IndexDoc, TranscriptDoc } from '../types';
import { Badge, EmptyState, SampleNotice, TimeLink } from './Ui';
import { duration, highlight, korDate, mmss } from '../lib/util';

interface Props {
  index: IndexDoc;
  currentId: string;
  setCurrentId: (id: string) => void;
  transcript: TranscriptDoc | null;
  loading: boolean;
}

type View = 'lines' | 'flow';

export const TranscriptTab: React.FC<Props> = ({
  index, currentId, setCurrentId, transcript, loading,
}) => {
  const [q, setQ] = useState('');
  const [view, setView] = useState<View>('lines');
  const [showRaw, setShowRaw] = useState(false);
  const [copied, setCopied] = useState(false);

  const entry = index.meetings.find((m) => m.id === currentId);

  const cues = useMemo(() => {
    if (!transcript) return [];
    const k = q.trim().toLowerCase();
    return k ? transcript.cues.filter((c) => c.text.toLowerCase().includes(k)) : transcript.cues;
  }, [transcript, q]);

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

  const correctedCount = transcript ? transcript.cues.filter((c) => c.raw).length : 0;

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
          aria-pressed={showRaw}
          onClick={() => setShowRaw((v) => !v)}
          className={`h-11 px-3.5 rounded-md border text-sm font-bold transition-colors ${
            showRaw
              ? 'bg-blue-600 border-blue-600 text-white'
              : 'bg-white border-slate-300 text-slate-600 hover:text-slate-900'
          }`}
        >
          자막 원문 {correctedCount > 0 && `(${correctedCount})`}
        </button>

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
            <Badge tone="blue">{transcript.id}</Badge>
            <Badge>{korDate(transcript.date)}</Badge>
            <Badge>{duration(transcript.durationSec)}</Badge>
            <Badge>{transcript.cueCount.toLocaleString()}줄 · {transcript.charCount.toLocaleString()}자</Badge>
            {correctedCount > 0 && <Badge tone="green">교정 {correctedCount}줄</Badge>}
            {transcript.refinedAt ? (
              <Badge tone="green">화자 {transcript.speakerTurns ?? 0}회 전환</Badge>
            ) : (
              <Badge tone="amber">교정·화자 미적용</Badge>
            )}
            <a
              href={transcript.videoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-bold text-blue-700 hover:underline underline-offset-4"
            >
              영상 열기
            </a>
          </div>

          {q && (
            <p className="text-sm text-slate-600 px-1">
              <strong className="text-blue-700 font-bold tabular-nums">{cues.length}</strong>줄에서 찾았습니다
            </p>
          )}

          <div className="bg-white rounded-lg border border-slate-200 p-5">
            {cues.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-8">검색어와 맞는 발언이 없습니다.</p>
            ) : view === 'lines' ? (
              <ol className="space-y-1">
                {cues.map((c, i) => {
                  // 화자는 바뀔 때만 적는다. 같은 사람이 이어 말하면 다시 쓰지 않는다.
                  const turn = c.speaker && c.speaker !== cues[i - 1]?.speaker;
                  return (
                    <li
                      key={`${c.t}-${i}`}
                      className={`grid grid-cols-[68px_1fr] gap-3 py-1.5 border-b border-slate-50 last:border-0 ${
                        turn ? 'mt-3 pt-3 border-t border-slate-100' : ''
                      }`}
                    >
                      <TimeLink videoId={transcript.videoId} t={c.t} />
                      <div>
                        {turn && (
                          <p className="mb-0.5">
                            <Badge tone={c.speaker === '교육감' ? 'amber' : 'blue'}>{c.speaker}</Badge>
                          </p>
                        )}
                        <p className={`text-slate-800 leading-relaxed ${c.raw ? 'border-b border-dashed border-slate-300 inline' : ''}`}>
                          {highlight(c.text, q)}
                        </p>
                        {showRaw && c.raw && (
                          <p className="text-xs text-slate-400 mt-0.5">자막 원문: {c.raw}</p>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ol>
            ) : (
              <p className="text-slate-800 leading-[2] text-[1.0625rem]">
                {cues.map((c, i) => (
                  <React.Fragment key={`${c.t}-${i}`}>
                    {highlight(c.text, q)}{' '}
                  </React.Fragment>
                ))}
              </p>
            )}
          </div>

          <p className="text-xs text-slate-400 px-1">
            자막 경로 {transcript.source} · 받은 시각 {transcript.fetchedAt?.slice(0, 16).replace('T', ' ')}
            {correctedCount > 0 && ' · 밑줄 친 문장은 사전으로 바로잡은 곳입니다'}
          </p>
        </>
      )}
    </div>
  );
};
