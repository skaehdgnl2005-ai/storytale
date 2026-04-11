"""2-Tier 안전 필터.

Tier 1: allowlist → exact_block → pattern_block (정규식) 순서로 텍스트 검증.
Tier 2: pattern_block 매칭 시 LLM 문맥 판단 (선택적, 향후 확장).

scene_planner.py, plan_reviser.py의 중복 키워드 검증을 이 모듈로 통합.
"""

import re
from dataclasses import dataclass
from typing import Any

from storytale.interpreter.scene_planner import ScenePlan, ScenePlanSafetyError


@dataclass
class SafetyCheckResult:
    """안전 검증 결과."""

    blocked: bool = False
    tier: int | None = None
    matched_keyword: str = ""
    matched_intent: str = ""


class SafetyChecker:
    """2-Tier 안전 필터.

    Args:
        content_filter: safety-rails.json의 content_filter dict.
    """

    def __init__(self, content_filter: dict[str, Any]) -> None:
        self._exact_block: list[str] = content_filter.get("exact_block", [])
        self._pattern_block: list[dict[str, str]] = content_filter.get(
            "pattern_block", []
        )
        self._allowlist: list[str] = content_filter.get("allowlist", [])
        # 정규식 사전 컴파일
        self._compiled_patterns: list[tuple[re.Pattern[str], str]] = [
            (re.compile(p["pattern"]), p["intent"]) for p in self._pattern_block
        ]

    def check_text(self, text: str) -> SafetyCheckResult:
        """텍스트를 Tier 1 기준으로 검증한다.

        Returns:
            SafetyCheckResult. blocked=True면 위반.
        """
        if not text:
            return SafetyCheckResult()

        # Step 1: allowlist에 해당하는 부분을 플레이스홀더로 치환
        cleaned = text
        for allowed in sorted(self._allowlist, key=len, reverse=True):
            cleaned = cleaned.replace(allowed, "\x00" * len(allowed))

        # Step 2: exact_block 검사 (치환된 텍스트에서)
        for keyword in self._exact_block:
            if keyword in cleaned:
                return SafetyCheckResult(
                    blocked=True,
                    tier=1,
                    matched_keyword=keyword,
                    matched_intent=f"exact_block: {keyword}",
                )

        # Step 3: pattern_block 정규식 검사 (치환된 텍스트에서)
        for pattern, intent in self._compiled_patterns:
            if pattern.search(cleaned):
                return SafetyCheckResult(
                    blocked=True,
                    tier=1,
                    matched_keyword=pattern.pattern,
                    matched_intent=intent,
                )

        return SafetyCheckResult()

    def validate_plan(self, plan: ScenePlan) -> None:
        """ScenePlan 전체 장면의 description을 검증한다.

        Raises:
            ScenePlanSafetyError: 위반 장면이 있을 때.
        """
        for scene in plan.scenes:
            result = self.check_text(scene.description)
            if result.blocked:
                raise ScenePlanSafetyError(
                    f"장면 '{scene.scene_id}'의 description에 "
                    f"금지 표현이 포함되어 있습니다: {result.matched_keyword} "
                    f"({result.matched_intent})"
                )
