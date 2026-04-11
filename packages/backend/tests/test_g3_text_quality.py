"""G3 품질 게이트 — 텍스트 품질 검증 통합 테스트.

3개 스토리를 실제 Claude API로 생성하고 가드레일을 검증한다.

실행: pytest tests/test_g3_text_quality.py -v -m integration --run-integration -s
(-s: 생성된 텍스트 출력 → 수동 품질 검토)
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from storytale.interpreter.llm_client import LLMClient
from storytale.interpreter.scene_planner import PlannedScene, ScenePlan, StyleNotes
from storytale.interpreter.safety_checker import SafetyChecker
from storytale.interpreter.story_personalizer import (
    ChildProfile,
    PersonalizedScene,
    StoryPersonalizer,
)

# ---------------------------------------------------------------------------
# 가드레일 데이터 로드
# ---------------------------------------------------------------------------

_SEEDS_DIR = Path(__file__).resolve().parents[3] / "docs" / "guardrail-seeds"


def _load_json(name: str) -> Any:
    return json.loads((_SEEDS_DIR / name).read_text(encoding="utf-8"))


AGE_STYLE_GUIDES: list[dict[str, Any]] = _load_json("age-style-guides.json")
SAFETY_RAILS: dict[str, Any] = _load_json("safety-rails.json")

AGE_STYLES = {g["age_group"]: g for g in AGE_STYLE_GUIDES}


# ---------------------------------------------------------------------------
# 3개 테스트 시나리오 (다른 연령대, 다른 목적)
# ---------------------------------------------------------------------------

SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "시나리오A — 3-4세 · 새 경험 (동생 탄생)",
        "child": ChildProfile(
            child_id="g3-child-a",
            name="하은",
            age=4,
            gender="female",
            comfort_object="토니(곰 인형)",
            friend_name="서준",
            favorite_animal="토끼",
        ),
        "age_group": "3-4",
        "plan": ScenePlan(
            title="토니와 함께하는 하은이의 하루",
            scenes=[
                PlannedScene(
                    scene_id="opening",
                    emotion="sadness",
                    purpose="현재 감정 공감",
                    description="하은이가 엄마 옆에 앉아 있지만 엄마는 동생을 안고 있다. 하은이는 토니를 꼭 껴안고 있다.",
                    child_elements=["comfort_object 등장", "엄마와의 거리감 표현"],
                ),
                PlannedScene(
                    scene_id="transition",
                    emotion="sadness",
                    purpose="감정 심화",
                    description="하은이가 토니에게 속삭인다. 토니만 내 말 들어줘.",
                    child_elements=["comfort_object 대화", "외로움 감각 표현"],
                ),
                PlannedScene(
                    scene_id="turning_point",
                    emotion="curiosity",
                    purpose="시선 전환",
                    description="동생이 하은이를 보며 방긋 웃는다. 하은이는 깜짝 놀란다.",
                    child_elements=["동생과의 첫 교감"],
                ),
                PlannedScene(
                    scene_id="attempt",
                    emotion="courage",
                    purpose="작은 시도",
                    description="하은이가 조심조심 동생에게 토니를 보여준다.",
                    child_elements=["comfort_object 공유 시도"],
                ),
                PlannedScene(
                    scene_id="retry",
                    emotion="joy",
                    purpose="재시도와 발견",
                    description="동생이 토니 발을 잡자 하은이가 피식 웃는다. 토니는 우리 둘의 친구다.",
                    child_elements=["comfort_object 공유 성공", "friend_name 언급"],
                ),
                PlannedScene(
                    scene_id="acceptance_a",
                    emotion="comfort",
                    purpose="수용",
                    description="하은이가 엄마 옆에 다시 앉는다. 이번엔 동생도, 토니도 함께. 하은이가 작게 웃는다.",
                    child_elements=["comfort_object 함께", "가족 안전감"],
                ),
                PlannedScene(
                    scene_id="acceptance_b",
                    emotion="comfort",
                    purpose="열린 결말",
                    description="하은이가 토니에게 속삭인다. 내일도 동생이랑 놀자, 토니.",
                    child_elements=["comfort_object 대화", "내일 기대"],
                ),
                PlannedScene(
                    scene_id="closing",
                    emotion="comfort",
                    purpose="마무리",
                    description="달빛 아래 잠든 하은이. 토니가 팔 안에 있다.",
                    child_elements=["comfort_object 함께", "안전한 잠자리"],
                ),
            ],
            style_notes=StyleNotes(
                tone="훈계하지 않고 경험으로 보여주기",
                avoid=["직접적 교훈 문장", "어른이 가르치는 장면"],
                repetition_motif="토니가 옆에 있으니까 괜찮아",
            ),
        ),
    },
    {
        "name": "시나리오B — 5-6세 · 발견의 기쁨 (공룡 탐험)",
        "child": ChildProfile(
            child_id="g3-child-b",
            name="시우",
            age=6,
            gender="male",
            comfort_object="공룡 인형(디노)",
            friend_name="지아",
            favorite_animal="트리케라톱스",
        ),
        "age_group": "5-6",
        "plan": ScenePlan(
            title="시우와 디노의 공룡 탐험",
            scenes=[
                PlannedScene(
                    scene_id="curiosity",
                    emotion="joy",
                    purpose="호기심 시작",
                    description="시우가 도서관에서 큰 공룡 책을 발견한다. 트리케라톱스 그림에서 눈을 못 떤다.",
                    child_elements=["favorite_animal 첫 등장", "comfort_object 함께"],
                ),
                PlannedScene(
                    scene_id="exploration_1",
                    emotion="joy",
                    purpose="탐험 시작",
                    description="시우가 디노를 들고 뒷마당으로 나간다. 돌멩이가 공룡알 같다며 주워 모은다.",
                    child_elements=["comfort_object 동행", "상상 놀이"],
                ),
                PlannedScene(
                    scene_id="exploration_2",
                    emotion="joy",
                    purpose="상상 확장",
                    description="시우가 모래사장을 공룡 땅으로 상상한다. 디노가 트리케라톱스를 만났다고 말한다.",
                    child_elements=["comfort_object 대화", "favorite_animal 상상"],
                ),
                PlannedScene(
                    scene_id="challenge",
                    emotion="sadness",
                    purpose="어려운 순간",
                    description="친구 지아가 공룡은 진짜가 아니라고 말한다. 시우는 살짝 풀이 죽는다.",
                    child_elements=["friend_name 등장", "감정 표현"],
                ),
                PlannedScene(
                    scene_id="discovery",
                    emotion="courage",
                    purpose="발견",
                    description="시우가 공룡 뼈 화석 사진을 보여주며 진짜였다고 말한다. 지아도 신기해한다.",
                    child_elements=["friend_name 교감", "favorite_animal 지식"],
                ),
                PlannedScene(
                    scene_id="sharing_1",
                    emotion="joy",
                    purpose="나눔 시작",
                    description="시우와 지아가 함께 공룡 그림을 그린다. 시우는 트리케라톱스, 지아는 프테라노돈.",
                    child_elements=["friend_name 함께 활동", "favorite_animal 표현"],
                ),
                PlannedScene(
                    scene_id="sharing_2",
                    emotion="joy",
                    purpose="나눔 확장",
                    description="시우가 엄마에게 오늘 발견한 것을 자랑한다. 디노도 함께 보여준다.",
                    child_elements=["comfort_object 함께", "가족 나눔"],
                ),
                PlannedScene(
                    scene_id="closing",
                    emotion="comfort",
                    purpose="마무리",
                    description="잠자리에서 시우가 디노에게 속삭인다. 내일은 뭘 찾아볼까?",
                    child_elements=["comfort_object 대화", "내일 기대"],
                ),
            ],
            style_notes=StyleNotes(
                tone="호기심과 즐거움을 살려서",
                avoid=["교훈적 문장", "관심사를 무시하는 표현"],
                repetition_motif="디노야, 이것 봐!",
            ),
        ),
    },
    {
        "name": "시나리오C — 7-8세 · 축하 (생일 이야기)",
        "child": ChildProfile(
            child_id="g3-child-c",
            name="민준",
            age=8,
            gender="male",
            comfort_object="로봇 장난감(보이)",
            friend_name="유진",
            favorite_animal="강아지",
        ),
        "age_group": "7-8",
        "plan": ScenePlan(
            title="민준이의 특별한 생일",
            scenes=[
                PlannedScene(
                    scene_id="anticipation_1",
                    emotion="joy",
                    purpose="기대",
                    description="민준이가 달력을 보며 생일까지 며칠 남았는지 센다. 보이에게 선물 뭐 받을까 이야기한다.",
                    child_elements=["comfort_object 대화", "생일 기대"],
                ),
                PlannedScene(
                    scene_id="anticipation_2",
                    emotion="joy",
                    purpose="기대 심화",
                    description="민준이가 유진이에게 생일 파티에 와달라고 초대한다. 강아지 모양 케이크를 만들자고 한다.",
                    child_elements=[
                        "friend_name 초대",
                        "favorite_animal 케이크",
                    ],
                ),
                PlannedScene(
                    scene_id="preparation",
                    emotion="joy",
                    purpose="준비",
                    description="민준이와 엄마가 함께 강아지 모양 쿠키를 만든다. 반죽이 손에 달라붙어 웃음이 난다.",
                    child_elements=["favorite_animal 모양 쿠키", "가족 함께"],
                ),
                PlannedScene(
                    scene_id="unexpected",
                    emotion="sadness",
                    purpose="예상 밖의 상황",
                    description="생일 아침, 비가 쏟아진다. 야외 파티를 계획했는데. 민준이는 시무룩해진다.",
                    child_elements=["예상 밖 변수", "감정 표현"],
                ),
                PlannedScene(
                    scene_id="twist",
                    emotion="courage",
                    purpose="전환",
                    description="민준이가 생각한다. 비가 와도 파티는 할 수 있어. 보이를 들고 거실로 간다.",
                    child_elements=["comfort_object 함께", "아이 주도 해결"],
                ),
                PlannedScene(
                    scene_id="together_1",
                    emotion="joy",
                    purpose="함께하는 순간",
                    description="유진이와 친구들이 도착한다. 거실에 담요 텐트를 치고 파티를 시작한다.",
                    child_elements=["friend_name 함께", "창의적 해결"],
                ),
                PlannedScene(
                    scene_id="together_2",
                    emotion="joy",
                    purpose="나눔과 기쁨",
                    description="강아지 모양 쿠키를 나눠 먹으며 이야기를 나눈다. 빗소리가 음악처럼 들린다.",
                    child_elements=["favorite_animal 쿠키 나눔", "감각 묘사"],
                ),
                PlannedScene(
                    scene_id="gratitude_1",
                    emotion="comfort",
                    purpose="감사와 여운",
                    description="친구들이 돌아간 후, 민준이가 엄마에게 말한다. 비가 와서 더 좋았어.",
                    child_elements=["가족 대화", "성장 표현"],
                ),
                PlannedScene(
                    scene_id="gratitude_2",
                    emotion="comfort",
                    purpose="마무리",
                    description="잠자리에서 민준이가 보이를 안고 속삭인다. 오늘이 내 최고의 생일이야.",
                    child_elements=["comfort_object 함께", "감사의 마무리"],
                ),
            ],
            style_notes=StyleNotes(
                tone="따뜻하고 설레는 톤, 아이의 내면 성장 보여주기",
                avoid=["선물 가치 강조", "완벽한 파티 묘사"],
                repetition_motif="보이야, 이번 생일은 특별해",
            ),
        ),
    },
]


# ---------------------------------------------------------------------------
# 헬퍼: 문장 분리
# ---------------------------------------------------------------------------

_SENTENCE_RE = re.compile(r"[^.!?。…\n]+[.!?。…]?")


def split_sentences(text: str) -> list[str]:
    """한국어 텍스트를 문장 단위로 분리한다."""
    lines = text.replace("\\n", "\n").split("\n")
    sentences: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 마침표/물음표/느낌표/줄임표 기준 분리
        parts = re.split(r"(?<=[.!?。…])\s*", line)
        for p in parts:
            p = p.strip()
            if p:
                sentences.append(p)
    return sentences


# ---------------------------------------------------------------------------
# 픽스처: LLM 클라이언트
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def llm_client() -> LLMClient:
    """실제 Claude API 클라이언트. CLAUDE_API_KEY 환경변수 필요."""
    return LLMClient()


@pytest.fixture(scope="module")
def personalizer(llm_client: LLMClient) -> StoryPersonalizer:
    return StoryPersonalizer(llm_client=llm_client)


@pytest.fixture(scope="module")
def safety_checker() -> SafetyChecker:
    return SafetyChecker(content_filter=SAFETY_RAILS["content_filter"])


# ---------------------------------------------------------------------------
# G3 통합 테스트: 3개 시나리오를 순차 실행
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[s["name"] for s in SCENARIOS],
)
async def test_g3_full_story_generation(
    scenario: dict[str, Any],
    personalizer: StoryPersonalizer,
    safety_checker: SafetyChecker,
) -> None:
    """G3 게이트: 전체 스토리 텍스트 품질 검증.

    검증 항목:
    1. PersonalizedScene JSON 스키마 유효
    2. 개인화 자연스러움 (아이 이름 포함)
    3. 연령별 문체 규칙 준수 (문장 길이)
    4. 안전규칙 위반 여부 (content_filter)
    5. 텍스트 출력 (수동 검토용)
    """
    child: ChildProfile = scenario["child"]
    plan: ScenePlan = scenario["plan"]
    age_group: str = scenario["age_group"]
    age_style = AGE_STYLES[age_group]
    style_notes = plan.style_notes

    max_chars = age_style["sentence_rules"]["max_characters_per_sentence"]
    page_guide = age_style["page_guidelines"]
    max_chars_per_page = page_guide["max_characters_per_page"]

    all_scenes: list[PersonalizedScene] = []
    all_texts: list[str] = []
    previous_summary = "없음"
    total_scenes = len(plan.scenes)

    print(f"\n{'='*60}")
    print(f"[STORY] {scenario['name']}")
    print(f"   child: {child.name} ({child.age}, {age_group})")
    print(f"   scenes: {total_scenes}")
    print(f"{'='*60}")

    # ------------------------------------------------------------------
    # 장면별 생성 + 검증
    # ------------------------------------------------------------------
    for idx, scene in enumerate(plan.scenes, start=1):
        personalized = await personalizer.generate_scene(
            scene=scene,
            child=child,
            previous_summary=previous_summary,
            age_style=age_style,
            style_notes=style_notes,
            scene_index=idx,
            total_scenes=total_scenes,
        )
        all_scenes.append(personalized)
        all_texts.append(personalized.text)
        previous_summary = personalized.text

        # --- 출력 (수동 검토용) ---
        print(f"\n--- 장면 {idx}/{total_scenes}: {scene.scene_id} ({scene.emotion}) ---")
        print(f"[텍스트]\n{personalized.text}")
        print(f"[일러스트 프롬프트]\n{personalized.illustration_prompt[:120]}...")

    # ------------------------------------------------------------------
    # G3-1: PersonalizedScene 스키마 검증
    # ------------------------------------------------------------------
    for ps in all_scenes:
        assert isinstance(ps, PersonalizedScene)
        assert ps.scene_id, "scene_id 비어있음"
        assert ps.page_number >= 1, f"page_number 비정상: {ps.page_number}"
        assert len(ps.text) > 0, "text 비어있음"
        assert len(ps.illustration_prompt) > 0, "illustration_prompt 비어있음"

    # ------------------------------------------------------------------
    # G3-2: 개인화 자연스러움 — 이름 포함 여부
    # ------------------------------------------------------------------
    full_text = "\n".join(all_texts)
    name_count = full_text.count(child.name)
    assert name_count >= 2, (
        f"아이 이름 '{child.name}'이 전체 텍스트에 {name_count}회만 등장. "
        f"최소 2회 이상 필요."
    )

    # 이름이 모든 문장에 들어있으면 기계적 → 전체 문장 대비 비율 체크
    sentences = split_sentences(full_text)
    name_sentence_count = sum(1 for s in sentences if child.name in s)
    name_ratio = name_sentence_count / len(sentences) if sentences else 0
    assert name_ratio < 0.8, (
        f"이름 '{child.name}'이 문장의 {name_ratio:.0%}에 등장 — "
        "기계적 끼워넣기 의심. 80% 미만이어야 자연스러움."
    )

    print(f"\n[PASS] personalization: name '{child.name}' {name_count}x, "
          f"ratio {name_ratio:.0%}")

    # comfort_object 등장 확인
    if child.comfort_object:
        # 괄호 안 이름 추출 (예: "토니(곰 인형)" → "토니")
        co_name = child.comfort_object.split("(")[0].strip()
        co_count = full_text.count(co_name)
        assert co_count >= 2, (
            f"comfort_object '{co_name}'이 {co_count}회만 등장. 최소 2회 필요."
        )
        print(f"[PASS] comfort_object '{co_name}' {co_count}x")

    # ------------------------------------------------------------------
    # G3-3: 연령별 문체 규칙 — 문장 길이
    # ------------------------------------------------------------------
    violations: list[str] = []
    for i, sentence in enumerate(sentences):
        char_count = len(sentence.strip())
        # 20% 여유 허용 (LLM이 정확히 맞추기 어려움)
        threshold = int(max_chars * 1.2)
        if char_count > threshold:
            violations.append(
                f"  문장 {i+1} ({char_count}자 > {threshold}자 허용치): "
                f"'{sentence[:40]}...'"
            )

    if violations:
        print(f"\n[WARN] sentence length violations ({len(violations)}):")
        for v in violations:
            print(v)
    else:
        print(f"\n[PASS] sentence length: all within {max_chars} chars (+20%)")

    # 위반이 전체 문장의 20% 이하면 통과 (LLM 특성 고려)
    violation_ratio = len(violations) / len(sentences) if sentences else 0
    assert violation_ratio <= 0.2, (
        f"문장 길이 위반 비율 {violation_ratio:.0%}가 20%를 초과. "
        f"연령대 {age_group} 기준 최대 {max_chars}자."
    )

    # ------------------------------------------------------------------
    # G3-4: 감정 아크 흐름 (구조적 검증)
    # ------------------------------------------------------------------
    emotions = [s.emotion for s in plan.scenes]
    # 마지막 장면은 comfort/joy여야 함 (열린 결말/긍정 마무리)
    assert emotions[-1] in ("comfort", "joy"), (
        f"마지막 장면 감정이 '{emotions[-1]}'입니다. "
        f"comfort 또는 joy여야 합니다 (열린 결말/긍정 마무리)."
    )
    # 감정 변화가 있어야 함 (같은 감정만 연속되면 안 됨)
    unique_emotions = set(emotions)
    assert len(unique_emotions) >= 2, (
        f"감정 종류가 {len(unique_emotions)}가지뿐. "
        "최소 2가지 이상의 감정 변화가 있어야 합니다."
    )
    print(f"[PASS] emotion arc: {' -> '.join(emotions)}")

    # ------------------------------------------------------------------
    # G3-5: 안전규칙 위반 여부
    # ------------------------------------------------------------------
    safety_violations: list[str] = []
    for ps in all_scenes:
        result = safety_checker.check_text(ps.text)
        if result.blocked:
            safety_violations.append(
                f"  장면 '{ps.scene_id}': {result.matched_keyword} "
                f"({result.matched_intent})"
            )

    if safety_violations:
        print(f"\n[FAIL] safety violations ({len(safety_violations)}):")
        for sv in safety_violations:
            print(sv)
    else:
        print(f"[PASS] safety: content_filter passed")

    assert not safety_violations, (
        f"안전규칙 위반 {len(safety_violations)}건 발견:\n"
        + "\n".join(safety_violations)
    )

    # ------------------------------------------------------------------
    # 일러스트 프롬프트 검증
    # ------------------------------------------------------------------
    for ps in all_scenes:
        prompt = ps.illustration_prompt
        # 영문인지 확인 (한글 포함 비율 10% 미만)
        korean_chars = len(re.findall(r"[가-힣]", prompt))
        total_chars = len(prompt)
        korean_ratio = korean_chars / total_chars if total_chars else 0
        assert korean_ratio < 0.1, (
            f"장면 '{ps.scene_id}' 일러스트 프롬프트에 한글 "
            f"{korean_ratio:.0%} 포함. 영문으로 작성해야 합니다."
        )
        # 아이 이름이 프롬프트에 포함되면 안 됨 (개인정보 보호)
        assert child.name not in prompt, (
            f"장면 '{ps.scene_id}' 일러스트 프롬프트에 "
            f"아이 이름 '{child.name}'이 포함됨. 개인정보 보호 위반."
        )
        # 금지된 negative prompt 요소 체크
        for neg in SAFETY_RAILS.get("illustration_safety", {}).get(
            "negative_prompts", []
        ):
            assert neg.lower() not in prompt.lower(), (
                f"장면 '{ps.scene_id}' 일러스트 프롬프트에 "
                f"금지 요소 '{neg}' 포함."
            )

    print(f"[PASS] illust prompts: english, no name, safety ok")

    # ------------------------------------------------------------------
    # 요약 통계
    # ------------------------------------------------------------------
    avg_sentence_len = (
        sum(len(s) for s in sentences) / len(sentences) if sentences else 0
    )
    print(f"\n[STATS]")
    print(f"   sentences: {len(sentences)}")
    print(f"   avg length: {avg_sentence_len:.1f} chars (limit: {max_chars})")
    print(f"   pages: {len(all_scenes)}")
    print(f"   safety violations: {len(safety_violations)}")
    print(f"   length violations: {len(violations)}")
