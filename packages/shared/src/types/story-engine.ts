// packages/shared/src/types/story-engine.ts

type AgeGroup = "3-4" | "5-6" | "7-8";

type Gender = "male" | "female";

type IntentCategory =
  | "value_teaching"      // 소중한 가치를 알려주고 싶어요
  | "interest_story"      // 아이의 관심사로 책을 만들래요
  | "problem_solving"     // 문제상황을 지혜롭게 해결했으면
  | "celebration";        // 특별한 날을 기념하고 싶어요

type IllustrationStyle = "watercolor" | "pastel_crayon" | "clean_digital";

// 나이(number) → AgeGroup 매핑 유틸리티 서명
export declare function resolveAgeGroup(age: number): AgeGroup;

// ============================================================
// 공통 에러 타입
// ============================================================

interface StoryEngineError {
  code:
    | "INTENT_ANALYSIS_FAILED"
    | "SCENE_PLAN_INVALID"
    | "SAFETY_VIOLATION"
    | "LLM_PARSE_ERROR"
    | "LLM_TIMEOUT"
    | "MAX_RETRIES_EXCEEDED";
  message: string;
  retryable: boolean;
  details?: Record<string, unknown>;
}

interface RejectedIntent {
  rejected: true;
  reason: string;
}

// ============================================================
// 0층: 가드레일
// ============================================================

interface ArcStage {
  phase: string;
  ratio: number;
  purpose: string;
}

interface EmotionalArcTemplate {
  arcId: string;
  description: string;
  targetAges: AgeGroup[];
  stages: ArcStage[];
  rules: string[];
}

interface SentenceRules {
  maxCharactersPerSentence: number;
  preferredStructure: string;
  repetitionPattern: string;
  vocabularyLevel: string;
}

interface ExpressionGuide {
  method: string;
  goodExamples: string[];
  badExamples: string[];
}

interface PageGuidelines {
  sentencesPerPage: { min: number; max: number };
  maxCharactersPerPage: number;
  totalPages: { min: number; max: number };
}

interface AgeStyleGuide {
  ageGroup: AgeGroup;
  sentenceRules: SentenceRules;
  emotionalExpression: ExpressionGuide;
  pageGuidelines: PageGuidelines;
}

interface SafetyRails {
  prohibitions: string[];
  requiredElements: string[];
}

// ============================================================
// 1층: AI 인터프리터
// ============================================================

interface IntentAnalysis {
  intentCategory: IntentCategory;
  coreTheme: string;
  triggerSituation: string;
  childCurrentBehavior: string;
  parentDesiredOutcome: string;
  emotionalKeywords: string[];
  recommendedArcId: string;
}

interface PlannedScene {
  sceneId: string;
  emotion: string;
  purpose: string;
  description: string;
  childElements: string[];
}

interface StyleNotes {
  tone: string;
  avoid: string[];
  repetitionMotif?: string;
}

interface ScenePlan {
  title: string;
  scenes: PlannedScene[];
  styleNotes: StyleNotes;
}

interface StoryInterpreter {
  analyzeIntent(
    parentText: string,
    purposeCategory: IntentCategory,
    childAge: number
  ): Promise<IntentAnalysis>;

  generateScenePlan(
    intent: IntentAnalysis,
    arc: EmotionalArcTemplate,
    ageStyle: AgeStyleGuide,
    safetyRails: SafetyRails
  ): Promise<ScenePlan>;

  reviseScenePlan(
    currentPlan: ScenePlan,
    parentFeedback: string,
    safetyRails: SafetyRails
  ): Promise<ScenePlan>;
}

// ============================================================
// 2층: 부모 확인
// ============================================================

interface StoryPreview {
  title: string;
  summary: string;
  sceneHighlights: string[];
  pageCount: number;
  style: IllustrationStyle;
}

interface PreviewGenerator {
  generatePreview(plan: ScenePlan, style: IllustrationStyle): Promise<StoryPreview>;
}

// ============================================================
// 3층: 개인화 생성
// ============================================================

interface ChildProfile {
  childId: string;
  name: string;
  age: number;
  gender: Gender;
  comfortObject?: string;
  friendName?: string;
  favoriteAnimal?: string;
  characterSheetUrl?: string;
}

interface PersonalizedScene {
  sceneId: string;
  pageNumber: number;
  text: string;
  illustrationPrompt: string;
}

interface StoryPersonalizer {
  generateScene(
    scene: PlannedScene,
    child: ChildProfile,
    previousSummary: string,
    ageStyle: AgeStyleGuide,
    styleNotes: StyleNotes
  ): Promise<PersonalizedScene>;
}

// ============================================================
// 오케스트레이터 (전체 흐름)
// ============================================================

interface StoryOrchestrator {
  interpretAndPlan(
    parentText: string,
    purposeCategory: IntentCategory,
    child: ChildProfile
  ): Promise<ScenePlan>;

  getPreview(
    plan: ScenePlan,
    style: IllustrationStyle
  ): Promise<StoryPreview>;

  revisePlan(
    plan: ScenePlan,
    feedback: string
  ): Promise<ScenePlan>;

  generateStory(
    confirmedPlan: ScenePlan,
    child: ChildProfile,
    style: IllustrationStyle
  ): AsyncGenerator<PersonalizedScene>;
}

export type {
  AgeGroup,
  Gender,
  IntentCategory,
  IllustrationStyle,
  StoryEngineError,
  RejectedIntent,
  ArcStage,
  EmotionalArcTemplate,
  SentenceRules,
  ExpressionGuide,
  PageGuidelines,
  AgeStyleGuide,
  SafetyRails,
  IntentAnalysis,
  PlannedScene,
  StyleNotes,
  ScenePlan,
  StoryInterpreter,
  StoryPreview,
  PreviewGenerator,
  ChildProfile,
  PersonalizedScene,
  StoryPersonalizer,
  StoryOrchestrator,
};
