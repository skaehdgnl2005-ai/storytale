// docs/contracts/story-engine.ts
// 스토리 엔진 인터페이스 계약
// 이 파일은 구현의 "청사진"이며 실제 런타임 코드가 아닙니다.
// Python 구현은 이 인터페이스를 Pydantic 모델 + ABC로 매핑합니다.

// ============================================================
// 공통 타입
// ============================================================

type AgeGroup = "3-4" | "5-6" | "7-8";

type Gender = "male" | "female";

type IntentCategory =
  | "value_teaching"      // 소중한 가치를 알려주고 싶어요
  | "interest_story"      // 아이의 관심사로 책을 만들래요
  | "problem_solving"     // 문제상황을 지혜롭게 해결했으면
  | "celebration";        // 특별한 날을 기념하고 싶어요

type IllustrationStyle = "watercolor" | "pastel_crayon" | "clean_digital";

// 나이(number) → AgeGroup 매핑 유틸리티
// 규칙: 3세 미만 → "3-4"(최소), 3-4세 → "3-4", 5-6세 → "5-6", 7-8세 → "7-8", 9세 이상 → "7-8"(최대)
function resolveAgeGroup(age: number): AgeGroup;

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

// 의도 분석에서 부적절한 요청 감지 시 반환
interface RejectedIntent {
  rejected: true;
  reason: string;
}

// ============================================================
// 0층: 가드레일
// ============================================================

interface ArcStage {
  phase: string;              // "공감", "전환점", "시도" 등
  ratio: number;              // 전체 스토리에서의 비중 (합계 1.0)
  purpose: string;            // 이 단계의 치료적/교육적 목적
}

interface EmotionalArcTemplate {
  arcId: string;              // "gentle_resolution", "courage_building" 등
  description: string;
  targetAges: AgeGroup[];
  stages: ArcStage[];
  rules: string[];            // 이 아크 사용 시 추가 규칙
}

interface SentenceRules {
  maxCharactersPerSentence: number;
  preferredStructure: string;
  repetitionPattern: string;   // "AAB", "AABB" 등
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
  coreTheme: string;              // "패배 수용", "나눔의 기쁨" 등
  triggerSituation: string;       // "게임에서 지는 상황"
  childCurrentBehavior: string;   // "지면 많이 움"
  parentDesiredOutcome: string;   // "지고도 괜찮다고 느끼길"
  emotionalKeywords: string[];    // ["좌절", "분노", "울음"]
  recommendedArcId: string;       // → 0층 EmotionalArcTemplate.arcId 참조
}

interface PlannedScene {
  sceneId: string;                // "opening", "turning_point" 등
  emotion: string;                // 이 장면의 주된 감정
  purpose: string;                // 치료적/교육적 목적
  description: string;            // 장면 개요 (AI가 텍스트 생성 시 참고)
  childElements: string[];        // 어떤 개인화 요소가 들어가는지
                                  // 예: ["comfort_object 등장", "friend_name과 함께"]
}

interface StyleNotes {
  tone: string;                   // "훈계하지 않고 경험으로 보여주기"
  avoid: string[];                // ["직접적 교훈 문장", "어른이 가르치는 장면"]
  repetitionMotif?: string;       // 반복 문구 패턴 (있을 경우)
}

interface ScenePlan {
  title: string;                  // 동화책 제목
  scenes: PlannedScene[];
  styleNotes: StyleNotes;
}

// AI 인터프리터 서비스 인터페이스
interface StoryInterpreter {
  // 1단계: 부모 텍스트 → 구조화된 의도
  analyzeIntent(
    parentText: string,
    purposeCategory: IntentCategory,
    childAge: number
  ): Promise<IntentAnalysis>;

  // 2단계: 의도 + 가드레일 → 장면 설계
  generateScenePlan(
    intent: IntentAnalysis,
    arc: EmotionalArcTemplate,
    ageStyle: AgeStyleGuide,
    safetyRails: SafetyRails
  ): Promise<ScenePlan>;

  // 수정: 부모 피드백 반영 (SafetyRails는 내부에서 자동 로드하여 검증)
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
  summary: string;                // 2~3문장 자연어 요약
  sceneHighlights: string[];      // 이모지 + 장면 한줄 요약 (UI 표시용)
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
  text: string;                   // 그림책에 나올 실제 한국어 텍스트
  illustrationPrompt: string;     // 영문, 일러스트 생성용 (50단어 이내)
}

interface StoryPersonalizer {
  generateScene(
    scene: PlannedScene,
    child: ChildProfile,
    previousSummary: string,      // 이전 장면까지의 요약 (연속성 유지)
    ageStyle: AgeStyleGuide,
    styleNotes: StyleNotes
  ): Promise<PersonalizedScene>;
}

// ============================================================
// 오케스트레이터 (전체 흐름)
// ============================================================

interface StoryOrchestrator {
  // Phase A: 해석 & 설계
  interpretAndPlan(
    parentText: string,
    purposeCategory: IntentCategory,
    child: ChildProfile
  ): Promise<ScenePlan>;

  // Phase B: 미리보기
  getPreview(
    plan: ScenePlan,
    style: IllustrationStyle
  ): Promise<StoryPreview>;

  // Phase C: 수정 (내부에서 SafetyRails를 자동 로드하여 검증)
  revisePlan(
    plan: ScenePlan,
    feedback: string
  ): Promise<ScenePlan>;

  // Phase D: 생성 (확정 후)
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

export { resolveAgeGroup };
