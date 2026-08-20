import type { ReactNode } from 'react';
import type { IndexEntry } from '../types';

/** 초 → "12:34" (한 시간이 넘으면 "1:02:34") */
export function mmss(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
    : `${m}:${String(r).padStart(2, '0')}`;
}

/** 초 → "57분" / "1시간 2분" */
export function duration(sec: number): string {
  if (!sec) return '—';
  const m = Math.round(sec / 60);
  return m < 60 ? `${m}분` : `${Math.floor(m / 60)}시간 ${m % 60}분`;
}

/** 2026-08-18 → 2026. 8. 18.(화) */
export function korDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '');
  if (!m) return iso ?? '';
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  // 보는 사람의 시간대에 따라 날짜가 하루 밀리면 안 된다. UTC 기준으로만 요일을 구한다.
  const wd = ['일', '월', '화', '수', '목', '금', '토'][new Date(Date.UTC(y, mo - 1, d)).getUTCDay()];
  return `${y}. ${mo}. ${d}.(${wd})`;
}

/** 유튜브 특정 시점 링크 */
export function ytAt(videoId: string, t: number): string {
  return `https://www.youtube.com/watch?v=${videoId}&t=${Math.max(0, Math.floor(t))}s`;
}

/** 검색어를 <mark>로 감싸 React 노드로 돌려준다 (dangerouslySetInnerHTML 없이) */
export function highlight(text: string, query: string): ReactNode[] {
  const q = query.trim();
  if (!q) return [text];
  const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(<mark key={`h${k++}`}>{m[0]}</mark>);
    last = m.index + m[0].length;
    if (m[0].length === 0) re.lastIndex += 1;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** 회차 진행 상태 — 자막 → 교정·화자 → 요약 순으로 쌓인다 */
export type Stage = 'done' | 'refined' | 'transcript' | 'pending';

export function stageOf(m: IndexEntry): Stage {
  if (m.hasSummary) return 'done';
  if (m.hasRefined) return 'refined';
  if (m.hasTranscript) return 'transcript';
  return 'pending';
}

export const STAGE_LABEL: Record<Stage, string> = {
  done: '요약 완료',
  refined: '교정·화자 완료',
  transcript: '자막만 확보',
  pending: '자막 미확보',
};
