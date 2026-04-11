"""get_story_orchestrator 의존성 팩토리 테스트.

create_llm_client를 사용하여 Gemini fallback이 자동 연결되는지 검증.
"""

import os
from unittest.mock import patch

import pytest

from storytale.api.stories.router import get_story_orchestrator
from storytale.interpreter.story_orchestrator import StoryOrchestrator


@pytest.mark.asyncio()
async def test_returns_story_orchestrator_instance():
    """get_story_orchestrator가 StoryOrchestrator 인스턴스를 반환한다."""
    with patch.dict(os.environ, {"CLAUDE_API_KEY": "test-key"}, clear=False):
        os.environ.pop("GEMINI_API_KEY", None)
        orchestrator = await get_story_orchestrator()

    assert isinstance(orchestrator, StoryOrchestrator)


@pytest.mark.asyncio()
async def test_gemini_fallback_when_key_set():
    """GEMINI_API_KEY가 설정되면 LLMClient에 Gemini fallback이 연결된다."""
    with patch.dict(
        os.environ,
        {"CLAUDE_API_KEY": "test-key", "GEMINI_API_KEY": "test-gemini-key"},
        clear=False,
    ):
        orchestrator = await get_story_orchestrator()

    # personalizer 내부의 LLMClient에 fallback이 설정되어 있는지 확인
    llm_client = orchestrator._personalizer._client
    assert llm_client._fallback is not None


@pytest.mark.asyncio()
async def test_no_gemini_fallback_without_key():
    """GEMINI_API_KEY가 없으면 fallback이 None이다."""
    with patch.dict(os.environ, {"CLAUDE_API_KEY": "test-key"}, clear=False):
        os.environ.pop("GEMINI_API_KEY", None)
        orchestrator = await get_story_orchestrator()

    llm_client = orchestrator._personalizer._client
    assert llm_client._fallback is None


@pytest.mark.asyncio()
async def test_all_components_share_same_llm_client():
    """인터프리터와 personalizer가 동일한 LLMClient를 사용한다."""
    with patch.dict(os.environ, {"CLAUDE_API_KEY": "test-key"}, clear=False):
        os.environ.pop("GEMINI_API_KEY", None)
        orchestrator = await get_story_orchestrator()

    # interpreter 내부 컴포넌트들의 LLMClient가 동일 인스턴스인지 확인
    personalizer_client = orchestrator._personalizer._client
    analyzer_client = orchestrator._interpreter._analyzer._client
    planner_client = orchestrator._interpreter._planner._client

    assert personalizer_client is analyzer_client
    assert analyzer_client is planner_client
