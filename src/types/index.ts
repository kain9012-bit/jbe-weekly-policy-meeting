export type ActiveTab = 'home' | 'meeting' | 'transcript' | 'directives' | 'search';

/** 자막 한 줄 */
export interface Cue {
  t: number;        // 시작 초
  text: string;     // 교정된 문장
  raw?: string;     // 교정 전 자막 원문 (바뀐 줄에만 있다)
  speaker?: string; // 1.5단계에서 붙인 화자 (추정)
}

/** 1단계 산출물 — data/transcripts/<id>.json */
export interface TranscriptDoc {
  id: string;
  postId: string;
  postUrl: string;
  title: string;
  date: string;
  videoId: string;
  videoUrl: string;
  durationSec: number;
  cueCount: number;
  charCount: number;
  source: string;
  fetchedAt: string;
  glossaryHits?: { rule: string; count: number }[];
  cues: Cue[];
  // 1.5단계(교정본)에만 있는 값
  refinedAt?: string;
  refineModel?: string;
  chunkCount?: number;
  changedLines?: number;
  speakerTurns?: number;
  _sample?: boolean;
  _sampleNote?: string;
}

export interface AgendaItem {
  seq: number;
  dept: string;
  topic: string;
  gist: string;
  t: number;
}

export interface Directive {
  id: string;
  dept: string;
  text: string;
  quote: string;
  t: number;
  type: string;     // 지시 | 당부 | 질의
  due: string;
}

export interface Followup {
  dept: string;
  matchedDirective: string;
  report: string;
  quote: string;
  t: number;
  progress: string; // 완료 | 진행중 | 계획수립 | 미착수
}

/** 2단계 산출물 — data/meetings/<id>.json */
export interface MeetingDoc {
  id: string;
  postId: string;
  postUrl: string;
  title: string;
  date: string;
  videoId: string;
  videoUrl: string;
  durationSec: number;
  summary: string;
  highlights: string[];
  agenda: AgendaItem[];
  directives: Directive[];
  followups: Followup[];
  corrections: { from: string; to: string; count?: number }[];
  meta: {
    captionSource: string;
    refined?: boolean;
    refineModel?: string | null;
    llm: string | null;
    summarizedAt?: string;
  };
  _sample?: boolean;
  _sampleNote?: string;
}

/** 목록 — data/index.json */
export interface IndexEntry {
  id: string;
  title: string;
  date: string;
  videoId: string;
  postId: string;
  postUrl: string;
  durationSec: number;
  hasTranscript: boolean;
  cueCount: number;
  charCount: number;
  captionSource: string;
  hasRefined?: boolean;
  speakerTurns?: number;
  hasSummary: boolean;
  summary: string;
  directiveCount: number;
  depts: string[];
}

export interface IndexDoc {
  updatedAt: string | null;
  seenPostIds: string[];
  meetings: IndexEntry[];
  _note?: string;
}

export const emptyIndex: IndexDoc = { updatedAt: null, seenPostIds: [], meetings: [] };
