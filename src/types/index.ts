export type ActiveTab = 'home' | 'meeting' | 'transcript' | 'directives' | 'search';

/**
 * 탭 이동. `at`(초) 를 주면 회의록 전문에서 그 시각의 발언으로 데려간다.
 * 지시사항에서 영상 말고 회의록으로도 갈 수 있어야 한다는 요구로 붙였다.
 */
export type Navigate = (tab: ActiveTab, query?: string, meetingId?: string, at?: number) => void;

/** 자막 한 문장 */
export interface Cue {
  t: number;         // 시작 초
  text: string;      // 교정된 문장
  raw?: string;      // 교정 전 자막 원문 (바뀐 문장에만 있다)
  /** 발언(문단)의 첫 문장인지 */
  turnStart?: boolean;
  /** 확인된 화자. 자기소개나 명확한 진행·지시 말투가 있을 때만 채운다. */
  speaker?: string;
  /** 이 발언이 속한 부서 보고 구간 */
  block?: string;
  /** 받아쓰기가 실패해 유튜브 자막에서 가져온 문장 (출처가 다르므로 표시한다) */
  fromCaption?: boolean;
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
  // 1.5단계(발언 단위 정리본)에만 있는 값
  segmentedAt?: string;
  turnCount?: number;
  /** 받아쓰기가 실패해 유튜브 자막으로 메운 구간 수 */
  captionFallbacks?: number;
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
  /** 대변인실 양식의 전달사항 hwpx 가 생성돼 있는지 */
  hasHandout?: boolean;
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
