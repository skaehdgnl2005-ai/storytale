// docs/contracts/book-recommendation.ts
// 동화책 추천 인터페이스 계약
// 이 파일은 구현의 "청사진"이며 실제 런타임 코드가 아닙니다.
// Python 구현은 이 인터페이스를 Pydantic 모델 + ABC로 매핑합니다.

import type {
  IntentCategory,
  IntentAnalysis,
  AgeGroup,
} from "./story-engine";

// ============================================================
// 도서 메타데이터
// ============================================================

type BookSource = "nlcy" | "aladin" | "kyobo" | "manual";

interface BookMetadata {
  id: string;                         // UUID
  isbn: string;                       // 고유 ISBN
  title: string;
  author: string;
  publisher: string;
  coverImageUrl?: string;
  synopsis?: string;                  // 줄거리 (외부 API에서 가져옴)
  targetAgeMin: number;               // 권장 최소 연령
  targetAgeMax: number;               // 권장 최대 연령
  source: BookSource;                 // 데이터 출처
  createdAt: string;
}

// ============================================================
// 상황 태그 (핵심 자산)
// ============================================================

type TagSource = "ai_generated" | "user_feedback" | "publisher";

interface SituationTag {
  id: string;                         // UUID
  bookId: string;                     // → BookMetadata.id 참조
  tagCategory: IntentCategory;        // story-engine.ts IntentCategory 재사용
  situationDescription: string;       // "동생이 태어나 질투하는 상황"
  emotionalKeywords: string[];        // IntentAnalysis.emotionalKeywords와 동일 어휘
  recommendedArcId?: string;          // → EmotionalArcTemplate.arcId 참조
  confidenceScore: number;            // AI 태그 생성 신뢰도 (0.0~1.0)
  source: TagSource;
  createdAt: string;
}

// ============================================================
// 독후 가이드
// ============================================================

interface BookGuide {
  bookId: string;
  whyThisBook: string;                // 왜 이 책인지 (2~3문장)
  readingQuestions: string[];          // 읽어줄 때 질문 (3~5개)
  conversationGuide: string[];        // 독후 대화 가이드 (3~4개)
}

// ============================================================
// 매칭 결과
// ============================================================

interface BookMatch {
  book: BookMetadata;
  matchScore: number;                 // 0.0~1.0 종합 점수
  matchedTags: SituationTag[];        // 매칭된 상황 태그들
}

// ============================================================
// 추천 결과 (API 응답)
// ============================================================

interface BookRecommendationResult {
  intentAnalysis: IntentAnalysis;     // 공유 피봇: 유료 전환 시 그대로 전달
  recommendations: Array<BookMatch & BookGuide>;
  hasCustomStoryOption: boolean;      // 맞춤 동화 전환 가능 여부
  customStoryPrompt: string;          // 전환 유도 문구
}

// ============================================================
// 추천 이력 (DB 저장용)
// ============================================================

interface BookRecommendationRecord {
  id: string;                         // UUID
  userId: string;
  childId: string;
  parentText: string;                 // 원본 부모 입력
  intentAnalysis: IntentAnalysis;
  recommendedBooks: Array<{
    bookId: string;
    rank: number;
    matchScore: number;
  }>;
  guides: BookGuide[];
  createdAt: string;
}

// ============================================================
// 에러 타입
// ============================================================

interface BookRecommendationError {
  code:
    | "NO_MATCHING_BOOKS"             // 매칭 도서 없음 (폴백 후에도)
    | "GUIDE_GENERATION_FAILED"       // LLM 가이드 생성 실패
    | "EXTERNAL_API_ERROR"            // 외부 도서 API 오류
    | "TAG_GENERATION_FAILED";        // 태그 자동 생성 실패
  message: string;
  retryable: boolean;
  details?: Record<string, unknown>;
}

// ============================================================
// 서비스 인터페이스
// ============================================================

interface BookRecommender {
  // 핵심: IntentAnalysis → 추천 결과 + 독후 가이드
  recommend(
    intent: IntentAnalysis,
    childAge: number,
    limit?: number                    // 기본값 3
  ): Promise<BookRecommendationResult>;
}

interface TagGenerator {
  // 책 메타데이터(줄거리+리뷰) → 상황 태그 생성
  generateTags(
    book: BookMetadata
  ): Promise<SituationTag[]>;
}

interface ExternalBookClient {
  // 외부 API에서 도서 검색
  searchBooks(
    query: string,
    limit?: number
  ): Promise<BookMetadata[]>;

  // ISBN으로 단건 조회
  getBookByIsbn(
    isbn: string
  ): Promise<BookMetadata | null>;
}

export type {
  BookSource,
  BookMetadata,
  TagSource,
  SituationTag,
  BookGuide,
  BookMatch,
  BookRecommendationResult,
  BookRecommendationRecord,
  BookRecommendationError,
  BookRecommender,
  TagGenerator,
  ExternalBookClient,
};
