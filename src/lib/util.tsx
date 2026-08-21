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

// ── 부서 ──────────────────────────────────────────────────────────────────

/**
 * 한 지시가 여러 부서에 걸리는 일이 흔하다("교육협력과 / 교육지원청").
 * 데이터에는 한 문자열로 들어 있지만, **화면에서는 반드시 쪼개 다뤄야 한다.**
 * 통째로 두면 필터 목록에 `교육협력과 / 교육지원청` 같은 항목이 따로 생겨서,
 * 교육협력과를 고른 사람에게 그 건이 안 보인다.
 */
const DEPT_ALIAS: Record<string, string> = {
  '도교육청 각 부서': '전 부서',
  '본청 전 부서': '전 부서',
};

/** 여러 기관을 한꺼번에 가리키는 말 — 목록에서 개별 부서 뒤로 보낸다. */
const COLLECTIVE = ['전 부서', '모든 기관', '교육지원청', '직속기관'];

export function splitDepts(value?: string | null): string[] {
  if (!value) return [];
  return value
    .split(/[/,·]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => DEPT_ALIAS[s] ?? s);
}

/** 이 건이 해당 부서에 걸리는가 */
export function hasDept(value: string | null | undefined, want: string): boolean {
  return splitDepts(value).includes(want);
}

/** 필터 목록용 — 개별 부서를 가나다순으로, 여러 기관을 뜻하는 말은 맨 뒤로 */
export function sortDepts(list: Iterable<string>): string[] {
  const uniq = [...new Set(list)].filter(Boolean);
  const rank = (d: string) => (COLLECTIVE.includes(d) ? 1 : 0);
  return uniq.sort((a, b) => rank(a) - rank(b) || a.localeCompare(b, 'ko'));
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
