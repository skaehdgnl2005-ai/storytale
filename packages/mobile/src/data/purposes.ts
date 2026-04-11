/**
 * 목적(Intent) 카드 데이터 — S29.
 *
 * 백엔드 contracts/story-engine.ts 의 IntentCategory 와 1:1 매핑된다.
 * 4가지 목적은 가드레일/인터프리터 파이프라인 전체에서 동일한 식별자를 사용하므로
 * 여기서 임의로 늘리거나 줄이지 말 것 (변경 시 contracts 와 함께 수정).
 */

export type PurposeId =
  | "value_teaching"
  | "interest_story"
  | "problem_solving"
  | "celebration";

export interface PurposeCard {
  id: PurposeId;
  /** 카드 상단 큰 글씨. 부모에게 친근한 톤으로. */
  title: string;
  /** 카드 본문. 부모가 어떤 상황에서 고를지 한눈에 와닿게. */
  description: string;
  /** 카드 좌측/상단 표현용 이모지 1개. (가이드: 문장 끝 1개 원칙) */
  emoji: string;
}

/**
 * 부모가 보는 4가지 목적 카드.
 *
 * 톤 가이드(CLAUDE.md):
 *   - "전문가가 함께하고 있어요"가 아니라 "당신이 아이를 가장 잘 알아요"
 *   - 시스템 용어("카테고리", "옵션") 대신 부모의 언어
 *   - 이모지는 1개씩만
 */
// 타입 어노테이션 없이 `as const` 를 사용해 readonly 튜플 타입을 보존한다.
// (`readonly PurposeCard[]` 로 annotate 하면 길이 정보가 사라져 컴파일 어서션 무력화)
export const PURPOSE_CARDS = [
  {
    id: "value_teaching",
    title: "소중한 가치를 알려주고 싶어요",
    description: "정직, 용기, 배려처럼 아이가 천천히 배웠으면 하는 마음을 담아요",
    emoji: "🌱",
  },
  {
    id: "interest_story",
    title: "아이의 관심사로 책을 만들래요",
    description: "공룡, 우주, 자동차 — 아이가 푹 빠진 세계를 책으로 옮겨요",
    emoji: "🦕",
  },
  {
    id: "problem_solving",
    title: "지금 겪는 일을 함께 풀어보고 싶어요",
    description: "동생이 생겼거나, 어린이집이 낯설거나 — 마음을 다독여줄 이야기예요",
    emoji: "🤝",
  },
  {
    id: "celebration",
    title: "특별한 날을 기념하고 싶어요",
    description: "생일, 입학, 첫 여행 — 오래 간직할 한 권을 만들어요",
    emoji: "🎂",
  },
] as const satisfies readonly PurposeCard[];

// ---------------------------------------------------------------------------
// 컴파일 타임 어서션 (TDD: jest-expo 가 깨져 있어 런타임 테스트 대신 사용)
// ---------------------------------------------------------------------------

// (1) PURPOSE_CARDS 길이는 정확히 4 — 백엔드 IntentCategory 와 동일.
type _Length<T extends readonly unknown[]> = T["length"];
type _AssertFour = _Length<typeof PURPOSE_CARDS> extends 4 ? true : false;
const _purposeCardsAreFour: _AssertFour = true;
void _purposeCardsAreFour;

// (2) 4개 id 가 PurposeId 를 정확히 덮어야 한다 (오타/누락 컴파일타임 차단).
type _CardIds = (typeof PURPOSE_CARDS)[number]["id"];
type _Equal<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
const _purposeIdsAreExhaustive: _Equal<_CardIds, PurposeId> = true;
void _purposeIdsAreExhaustive;
