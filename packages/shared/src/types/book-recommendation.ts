// packages/shared/src/types/book-recommendation.ts

import type { IntentCategory, IntentAnalysis } from "./story-engine";

// ============================================================
// 도서 메타데이터
// ============================================================

type BookSource = "nlcy" | "aladin" | "kyobo" | "manual";

interface BookMetadata {
  id: string;
  isbn: string;
  title: string;
  author: string;
  publisher: string;
  coverImageUrl?: string;
  synopsis?: string;
  targetAgeMin: number;
  targetAgeMax: number;
  source: BookSource;
  createdAt: string;
}

// ============================================================
// 상황 태그
// ============================================================

type TagSource = "ai_generated" | "user_feedback" | "publisher";

interface SituationTag {
  id: string;
  bookId: string;
  tagCategory: IntentCategory;
  situationDescription: string;
  emotionalKeywords: string[];
  recommendedArcId?: string;
  confidenceScore: number;
  source: TagSource;
  createdAt: string;
}

// ============================================================
// 독후 가이드
// ============================================================

interface BookGuide {
  bookId: string;
  whyThisBook: string;
  readingQuestions: string[];
  conversationGuide: string[];
}

// ============================================================
// 매칭 & 추천 결과
// ============================================================

interface BookMatch {
  book: BookMetadata;
  matchScore: number;
  matchedTags: SituationTag[];
}

interface BookRecommendationResult {
  intentAnalysis: IntentAnalysis;
  recommendations: Array<BookMatch & BookGuide>;
  hasCustomStoryOption: boolean;
  customStoryPrompt: string;
}

// ============================================================
// 추천 이력
// ============================================================

interface BookRecommendationRecord {
  id: string;
  userId: string;
  childId: string;
  parentText: string;
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
// 에러
// ============================================================

interface BookRecommendationError {
  code:
    | "NO_MATCHING_BOOKS"
    | "GUIDE_GENERATION_FAILED"
    | "EXTERNAL_API_ERROR"
    | "TAG_GENERATION_FAILED";
  message: string;
  retryable: boolean;
  details?: Record<string, unknown>;
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
};
