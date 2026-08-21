/**
 * 수집 결과(data/)를 빌드 산출물 옆에 복사한다.
 *
 * 화면은 `data/*.json` 을 실행 시점에 fetch 한다. 번들에 들어가지 않으므로
 * 따로 옮겨야 한다. 예전에는 이 복사가 GitHub Actions 워크플로에만 있었는데,
 * 그러면 **Vercel 처럼 `npm run build` 만 부르는 곳에서는 데이터가 빠진 채로
 * 배포된다.** 화면은 뜨는데 회의가 하나도 없는 상태가 된다.
 * 그래서 빌드 명령 안으로 옮겼다. 어디서 빌드하든 같은 결과가 나온다.
 */
import { cp, rm, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = path.join(root, 'data');
const dest = path.join(root, 'dist', 'data');

try {
  await stat(src);
} catch {
  console.error('data/ 가 없습니다. 수집을 먼저 실행하세요.');
  process.exit(1);
}

// 지난 빌드가 남아 있으면 지운 회차가 계속 배포된다.
await rm(dest, { recursive: true, force: true });
/**
 * 화면이 실제로 받아 가는 것만 배포한다.
 *   index.json · meetings/ · refined/ · transcripts/(교정 전 대비용) · handouts/
 * 빼는 것:
 *   audio/  원본 오디오. 회차당 25MB이고 유튜브에 이미 있다.
 *   asr/    받아쓰기 원본. 재현용이라 저장소에는 두지만 브라우저는 안 받는다.
 *   human/  사람이 채운 화자·교정. 이미 refined/ 에 반영돼 있다.
 */
const SKIP = new Set(['audio', 'asr', 'human']);

await cp(src, dest, {
  recursive: true,
  filter: (p) => {
    const rel = path.relative(src, p);
    return !rel || !SKIP.has(rel.split(path.sep)[0]);
  },
});

console.log(`data/ → dist/data 복사 완료 (${[...SKIP].join(', ')} 제외)`);
