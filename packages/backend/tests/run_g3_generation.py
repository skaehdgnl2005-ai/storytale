"""G3 스토리 생성 스크립트 (비-pytest, 장면 단위 저장/재개 지원).

Usage:
    cd packages/backend
    .venv/Scripts/python -m tests.run_g3_generation

결과: tests/g3_results.json 에 저장.
이후 pytest tests/test_g3_text_quality.py -k validate 로 검증.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# src를 패스에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from storytale.interpreter.llm_client import LLMClient  # noqa: E402
from storytale.interpreter.scene_planner import PlannedScene, ScenePlan, StyleNotes  # noqa: E402
from storytale.interpreter.story_personalizer import (  # noqa: E402
    ChildProfile,
    StoryPersonalizer,
)

SEEDS_DIR = Path(__file__).resolve().parents[3] / "docs" / "guardrail-seeds"
RESULTS_FILE = Path(__file__).resolve().parent / "g3_results.json"


def load_json(name: str):
    return json.loads((SEEDS_DIR / name).read_text(encoding="utf-8"))


AGE_STYLE_GUIDES = load_json("age-style-guides.json")
AGE_STYLES = {g["age_group"]: g for g in AGE_STYLE_GUIDES}

SCENARIOS = [
    {
        "id": "A",
        "name": "3-4se new_experience",
        "child": {
            "child_id": "g3-child-a",
            "name": "\ud558\uc740",
            "age": 4,
            "gender": "female",
            "comfort_object": "\ud1a0\ub2c8(\uacf0 \uc778\ud615)",
            "friend_name": "\uc11c\uc900",
            "favorite_animal": "\ud1a0\ub07c",
        },
        "age_group": "3-4",
        "plan": {
            "title": "\ud1a0\ub2c8\uc640 \ud568\uaed8\ud558\ub294 \ud558\uc740\uc774\uc758 \ud558\ub8e8",
            "scenes": [
                {"scene_id": "opening", "emotion": "sadness", "purpose": "\ud604\uc7ac \uac10\uc815 \uacf5\uac10", "description": "\ud558\uc740\uc774\uac00 \uc5c4\ub9c8 \uc606\uc5d0 \uc549\uc544 \uc788\uc9c0\ub9cc \uc5c4\ub9c8\ub294 \ub3d9\uc0dd\uc744 \uc548\uace0 \uc788\ub2e4. \ud558\uc740\uc774\ub294 \ud1a0\ub2c8\ub97c \uaf49 \uaed0\uc548\uace0 \uc788\ub2e4.", "child_elements": ["comfort_object \ub4f1\uc7a5", "\uc5c4\ub9c8\uc640\uc758 \uac70\ub9ac\uac10 \ud45c\ud604"]},
                {"scene_id": "transition", "emotion": "sadness", "purpose": "\uac10\uc815 \uc2ec\ud654", "description": "\ud558\uc740\uc774\uac00 \ud1a0\ub2c8\uc5d0\uac8c \uc18d\uc0ad\uc778\ub2e4. \ud1a0\ub2c8\ub9cc \ub0b4 \ub9d0 \ub4e4\uc5b4\uc918.", "child_elements": ["comfort_object \ub300\ud654", "\uc678\ub85c\uc6c0 \uac10\uac01 \ud45c\ud604"]},
                {"scene_id": "turning_point", "emotion": "curiosity", "purpose": "\uc2dc\uc120 \uc804\ud658", "description": "\ub3d9\uc0dd\uc774 \ud558\uc740\uc774\ub97c \ubcf4\uba70 \ubc29\uae0b \uc6c3\ub294\ub2e4. \ud558\uc740\uc774\ub294 \uae5c\uc9dd \ub180\ub780\ub2e4.", "child_elements": ["\ub3d9\uc0dd\uacfc\uc758 \uccab \uad50\uac10"]},
                {"scene_id": "attempt", "emotion": "courage", "purpose": "\uc791\uc740 \uc2dc\ub3c4", "description": "\ud558\uc740\uc774\uac00 \uc870\uc2ec\uc870\uc2ec \ub3d9\uc0dd\uc5d0\uac8c \ud1a0\ub2c8\ub97c \ubcf4\uc5ec\uc900\ub2e4.", "child_elements": ["comfort_object \uacf5\uc720 \uc2dc\ub3c4"]},
                {"scene_id": "retry", "emotion": "joy", "purpose": "\uc7ac\uc2dc\ub3c4\uc640 \ubc1c\uacac", "description": "\ub3d9\uc0dd\uc774 \ud1a0\ub2c8 \ubc1c\uc744 \uc7a1\uc790 \ud558\uc740\uc774\uac00 \ud53c\uc2dd \uc6c3\ub294\ub2e4. \ud1a0\ub2c8\ub294 \uc6b0\ub9ac \ub458\uc758 \uce5c\uad6c\ub2e4.", "child_elements": ["comfort_object \uacf5\uc720 \uc131\uacf5", "friend_name \uc5b8\uae09"]},
                {"scene_id": "acceptance_a", "emotion": "comfort", "purpose": "\uc218\uc6a9", "description": "\ud558\uc740\uc774\uac00 \uc5c4\ub9c8 \uc606\uc5d0 \ub2e4\uc2dc \uc549\ub294\ub2e4. \uc774\ubc88\uc5d4 \ub3d9\uc0dd\ub3c4, \ud1a0\ub2c8\ub3c4 \ud568\uaed8. \ud558\uc740\uc774\uac00 \uc791\uac8c \uc6c3\ub294\ub2e4.", "child_elements": ["comfort_object \ud568\uaed8", "\uac00\uc871 \uc548\uc804\uac10"]},
                {"scene_id": "acceptance_b", "emotion": "comfort", "purpose": "\uc5f4\ub9b0 \uacb0\ub9d0", "description": "\ud558\uc740\uc774\uac00 \ud1a0\ub2c8\uc5d0\uac8c \uc18d\uc0ad\uc778\ub2e4. \ub0b4\uc77c\ub3c4 \ub3d9\uc0dd\uc774\ub791 \ub180\uc790, \ud1a0\ub2c8.", "child_elements": ["comfort_object \ub300\ud654", "\ub0b4\uc77c \uae30\ub300"]},
                {"scene_id": "closing", "emotion": "comfort", "purpose": "\ub9c8\ubb34\ub9ac", "description": "\ub2ec\ube5b \uc544\ub798 \uc7a0\ub4e0 \ud558\uc740\uc774. \ud1a0\ub2c8\uac00 \ud314 \uc548\uc5d0 \uc788\ub2e4.", "child_elements": ["comfort_object \ud568\uaed8", "\uc548\uc804\ud55c \uc7a0\uc790\ub9ac"]},
            ],
            "style_notes": {"tone": "\ud6c8\uacc4\ud558\uc9c0 \uc54a\uace0 \uacbd\ud5d8\uc73c\ub85c \ubcf4\uc5ec\uc8fc\uae30", "avoid": ["\uc9c1\uc811\uc801 \uad50\ud6c8 \ubb38\uc7a5", "\uc5b4\ub978\uc774 \uac00\ub974\uce58\ub294 \uc7a5\uba74"], "repetition_motif": "\ud1a0\ub2c8\uac00 \uc606\uc5d0 \uc788\uc73c\ub2c8\uae4c \uad1c\ucc2e\uc544"},
        },
    },
    {
        "id": "B",
        "name": "5-6se joy_of_discovery",
        "child": {
            "child_id": "g3-child-b",
            "name": "\uc2dc\uc6b0",
            "age": 6,
            "gender": "male",
            "comfort_object": "\uacf5\ub8e1 \uc778\ud615(\ub514\ub178)",
            "friend_name": "\uc9c0\uc544",
            "favorite_animal": "\ud2b8\ub9ac\ucf00\ub77c\ud1b1\uc2a4",
        },
        "age_group": "5-6",
        "plan": {
            "title": "\uc2dc\uc6b0\uc640 \ub514\ub178\uc758 \uacf5\ub8e1 \ud0d0\ud5d8",
            "scenes": [
                {"scene_id": "curiosity", "emotion": "joy", "purpose": "\ud638\uae30\uc2ec \uc2dc\uc791", "description": "\uc2dc\uc6b0\uac00 \ub3c4\uc11c\uad00\uc5d0\uc11c \ud070 \uacf5\ub8e1 \ucc45\uc744 \ubc1c\uacac\ud55c\ub2e4. \ud2b8\ub9ac\ucf00\ub77c\ud1b1\uc2a4 \uadf8\ub9bc\uc5d0\uc11c \ub208\uc744 \ubabb \ub5f4\ub2e4.", "child_elements": ["favorite_animal \uccab \ub4f1\uc7a5", "comfort_object \ud568\uaed8"]},
                {"scene_id": "exploration_1", "emotion": "joy", "purpose": "\ud0d0\ud5d8 \uc2dc\uc791", "description": "\uc2dc\uc6b0\uac00 \ub514\ub178\ub97c \ub4e4\uace0 \ub4b7\ub9c8\ub2f9\uc73c\ub85c \ub098\uac04\ub2e4. \ub3cc\uad29\uc774\uac00 \uacf5\ub8e1\uc54c \uac19\ub2e4\uba70 \uc8fc\uc6cc \ubaa8\uc740\ub2e4.", "child_elements": ["comfort_object \ub3d9\ud589", "\uc0c1\uc0c1 \ub180\uc774"]},
                {"scene_id": "exploration_2", "emotion": "joy", "purpose": "\uc0c1\uc0c1 \ud655\uc7a5", "description": "\uc2dc\uc6b0\uac00 \ubaa8\ub798\uc0ac\uc7a5\uc744 \uacf5\ub8e1 \ub545\uc73c\ub85c \uc0c1\uc0c1\ud55c\ub2e4. \ub514\ub178\uac00 \ud2b8\ub9ac\ucf00\ub77c\ud1b1\uc2a4\ub97c \ub9cc\ub0ac\ub2e4\uace0 \ub9d0\ud55c\ub2e4.", "child_elements": ["comfort_object \ub300\ud654", "favorite_animal \uc0c1\uc0c1"]},
                {"scene_id": "challenge", "emotion": "sadness", "purpose": "\uc5b4\ub824\uc6b4 \uc21c\uac04", "description": "\uce5c\uad6c \uc9c0\uc544\uac00 \uacf5\ub8e1\uc740 \uc9c4\uc9dc\uac00 \uc544\ub2c8\ub77c\uace0 \ub9d0\ud55c\ub2e4. \uc2dc\uc6b0\ub294 \uc0b4\uc9dd \ud480\uc774 \uc8fd\ub294\ub2e4.", "child_elements": ["friend_name \ub4f1\uc7a5", "\uac10\uc815 \ud45c\ud604"]},
                {"scene_id": "discovery", "emotion": "courage", "purpose": "\ubc1c\uacac", "description": "\uc2dc\uc6b0\uac00 \uacf5\ub8e1 \ubf08 \ud654\uc11d \uc0ac\uc9c4\uc744 \ubcf4\uc5ec\uc8fc\uba70 \uc9c4\uc9dc\uc600\ub2e4\uace0 \ub9d0\ud55c\ub2e4. \uc9c0\uc544\ub3c4 \uc2e0\uae30\ud574\ud55c\ub2e4.", "child_elements": ["friend_name \uad50\uac10", "favorite_animal \uc9c0\uc2dd"]},
                {"scene_id": "sharing_1", "emotion": "joy", "purpose": "\ub098\ub214 \uc2dc\uc791", "description": "\uc2dc\uc6b0\uc640 \uc9c0\uc544\uac00 \ud568\uaed8 \uacf5\ub8e1 \uadf8\ub9bc\uc744 \uadf8\ub9b0\ub2e4. \uc2dc\uc6b0\ub294 \ud2b8\ub9ac\ucf00\ub77c\ud1b1\uc2a4, \uc9c0\uc544\ub294 \ud504\ud14c\ub77c\ub178\ub3c8.", "child_elements": ["friend_name \ud568\uaed8 \ud65c\ub3d9", "favorite_animal \ud45c\ud604"]},
                {"scene_id": "sharing_2", "emotion": "joy", "purpose": "\ub098\ub214 \ud655\uc7a5", "description": "\uc2dc\uc6b0\uac00 \uc5c4\ub9c8\uc5d0\uac8c \uc624\ub298 \ubc1c\uacac\ud55c \uac83\uc744 \uc790\ub791\ud55c\ub2e4. \ub514\ub178\ub3c4 \ud568\uaed8 \ubcf4\uc5ec\uc900\ub2e4.", "child_elements": ["comfort_object \ud568\uaed8", "\uac00\uc871 \ub098\ub214"]},
                {"scene_id": "closing", "emotion": "comfort", "purpose": "\ub9c8\ubb34\ub9ac", "description": "\uc7a0\uc790\ub9ac\uc5d0\uc11c \uc2dc\uc6b0\uac00 \ub514\ub178\uc5d0\uac8c \uc18d\uc0ad\uc778\ub2e4. \ub0b4\uc77c\uc740 \ubf08\ub97c \ucc3e\uc544\ubcfc\uae4c?", "child_elements": ["comfort_object \ub300\ud654", "\ub0b4\uc77c \uae30\ub300"]},
            ],
            "style_notes": {"tone": "\ud638\uae30\uc2ec\uacfc \uc990\uac70\uc6c0\uc744 \uc0b4\ub824\uc11c", "avoid": ["\uad50\ud6c8\uc801 \ubb38\uc7a5", "\uad00\uc2ec\uc0ac\ub97c \ubb34\uc2dc\ud558\ub294 \ud45c\ud604"], "repetition_motif": "\ub514\ub178\uc57c, \uc774\uac83 \ubd10!"},
        },
    },
    {
        "id": "C",
        "name": "7-8se celebration",
        "child": {
            "child_id": "g3-child-c",
            "name": "\ubbfc\uc900",
            "age": 8,
            "gender": "male",
            "comfort_object": "\ub85c\ubd07 \uc7a5\ub09c\uac10(\ubcf4\uc774)",
            "friend_name": "\uc720\uc9c4",
            "favorite_animal": "\uac15\uc544\uc9c0",
        },
        "age_group": "7-8",
        "plan": {
            "title": "\ubbfc\uc900\uc774\uc758 \ud2b9\ubcc4\ud55c \uc0dd\uc77c",
            "scenes": [
                {"scene_id": "anticipation_1", "emotion": "joy", "purpose": "\uae30\ub300", "description": "\ubbfc\uc900\uc774\uac00 \ub2ec\ub825\uc744 \ubcf4\uba70 \uc0dd\uc77c\uae4c\uc9c0 \uba70\uce60 \ub0a8\uc558\ub294\uc9c0 \uc13c\ub2e4. \ubcf4\uc774\uc5d0\uac8c \uc120\ubb3c \ubbf0 \ubc1b\uc744\uae4c \uc774\uc57c\uae30\ud55c\ub2e4.", "child_elements": ["comfort_object \ub300\ud654", "\uc0dd\uc77c \uae30\ub300"]},
                {"scene_id": "anticipation_2", "emotion": "joy", "purpose": "\uae30\ub300 \uc2ec\ud654", "description": "\ubbfc\uc900\uc774\uac00 \uc720\uc9c4\uc774\uc5d0\uac8c \uc0dd\uc77c \ud30c\ud2f0\uc5d0 \uc640\ub2ec\ub77c\uace0 \ucd08\ub300\ud55c\ub2e4. \uac15\uc544\uc9c0 \ubaa8\uc591 \ucf00\uc774\ud06c\ub97c \ub9cc\ub4e4\uc790\uace0 \ud55c\ub2e4.", "child_elements": ["friend_name \ucd08\ub300", "favorite_animal \ucf00\uc774\ud06c"]},
                {"scene_id": "preparation", "emotion": "joy", "purpose": "\uc900\ube44", "description": "\ubbfc\uc900\uc774\uc640 \uc5c4\ub9c8\uac00 \ud568\uaed8 \uac15\uc544\uc9c0 \ubaa8\uc591 \ucfe0\ud0a4\ub97c \ub9cc\ub4e0\ub2e4. \ubc18\uc8fd\uc774 \uc190\uc5d0 \ub2ec\ub77c\ubd99\uc5b4 \uc6c3\uc74c\uc774 \ub09c\ub2e4.", "child_elements": ["favorite_animal \ubaa8\uc591 \ucfe0\ud0a4", "\uac00\uc871 \ud568\uaed8"]},
                {"scene_id": "unexpected", "emotion": "sadness", "purpose": "\uc608\uc0c1 \ubc16\uc758 \uc0c1\ud669", "description": "\uc0dd\uc77c \uc544\uce68, \ube44\uac00 \uc3df\uc544\uc9c4\ub2e4. \uc57c\uc678 \ud30c\ud2f0\ub97c \uacc4\ud68d\ud588\ub294\ub370. \ubbfc\uc900\uc774\ub294 \uc2dc\ubb34\ub8e9\ud574\uc9c4\ub2e4.", "child_elements": ["\uc608\uc0c1 \ubc16 \ubcc0\uc218", "\uac10\uc815 \ud45c\ud604"]},
                {"scene_id": "twist", "emotion": "courage", "purpose": "\uc804\ud658", "description": "\ubbfc\uc900\uc774\uac00 \uc0dd\uac01\ud55c\ub2e4. \ube44\uac00 \uc640\ub3c4 \ud30c\ud2f0\ub294 \ud560 \uc218 \uc788\uc5b4. \ubcf4\uc774\ub97c \ub4e4\uace0 \uac70\uc2e4\ub85c \uac04\ub2e4.", "child_elements": ["comfort_object \ud568\uaed8", "\uc544\uc774 \uc8fc\ub3c4 \ud574\uacb0"]},
                {"scene_id": "together_1", "emotion": "joy", "purpose": "\ud568\uaed8\ud558\ub294 \uc21c\uac04", "description": "\uc720\uc9c4\uc774\uc640 \uce5c\uad6c\ub4e4\uc774 \ub3c4\ucc29\ud55c\ub2e4. \uac70\uc2e4\uc5d0 \ub2f4\uc694 \ud150\ud2b8\ub97c \uce58\uace0 \ud30c\ud2f0\ub97c \uc2dc\uc791\ud55c\ub2e4.", "child_elements": ["friend_name \ud568\uaed8", "\ucc3d\uc758\uc801 \ud574\uacb0"]},
                {"scene_id": "together_2", "emotion": "joy", "purpose": "\ub098\ub214\uacfc \uae30\uc068", "description": "\uac15\uc544\uc9c0 \ubaa8\uc591 \ucfe0\ud0a4\ub97c \ub098\ub220 \uba39\uc73c\uba70 \uc774\uc57c\uae30\ub97c \ub098\ub208\ub2e4. \ube57\uc18c\ub9ac\uac00 \uc74c\uc545\ucc98\ub7fc \ub4e4\ub9b0\ub2e4.", "child_elements": ["favorite_animal \ucfe0\ud0a4 \ub098\ub214", "\uac10\uac01 \ubb18\uc0ac"]},
                {"scene_id": "gratitude_1", "emotion": "comfort", "purpose": "\uac10\uc0ac\uc640 \uc5ec\uc6b4", "description": "\uce5c\uad6c\ub4e4\uc774 \ub3cc\uc544\uac04 \ud6c4, \ubbfc\uc900\uc774\uac00 \uc5c4\ub9c8\uc5d0\uac8c \ub9d0\ud55c\ub2e4. \ube44\uac00 \uc640\uc11c \ub354 \uc88b\uc558\uc5b4.", "child_elements": ["\uac00\uc871 \ub300\ud654", "\uc131\uc7a5 \ud45c\ud604"]},
                {"scene_id": "gratitude_2", "emotion": "comfort", "purpose": "\ub9c8\ubb34\ub9ac", "description": "\uc7a0\uc790\ub9ac\uc5d0\uc11c \ubbfc\uc900\uc774\uac00 \ubcf4\uc774\ub97c \uc548\uace0 \uc18d\uc0ad\uc778\ub2e4. \uc624\ub298\uc774 \ub0b4 \ucd5c\uace0\uc758 \uc0dd\uc77c\uc774\uc57c.", "child_elements": ["comfort_object \ud568\uaed8", "\uac10\uc0ac\uc758 \ub9c8\ubb34\ub9ac"]},
            ],
            "style_notes": {"tone": "\ub530\ub73b\ud558\uace0 \uc124\ub808\ub294 \ud1a4, \uc544\uc774\uc758 \ub0b4\uba74 \uc131\uc7a5 \ubcf4\uc5ec\uc8fc\uae30", "avoid": ["\uc120\ubb3c \uac00\uce58 \uac15\uc870", "\uc644\ubcbd\ud55c \ud30c\ud2f0 \ubb18\uc0ac"], "repetition_motif": "\ubcf4\uc774\uc57c, \uc774\ubc88 \uc0dd\uc77c\uc740 \ud2b9\ubcc4\ud574"},
        },
    },
]


def _load_results() -> dict:
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_results(results: dict) -> None:
    RESULTS_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def main() -> None:
    client = LLMClient()
    personalizer = StoryPersonalizer(llm_client=client)

    results = _load_results()

    for scenario in SCENARIOS:
        sid = scenario["id"]
        if sid not in results:
            results[sid] = {"name": scenario["name"], "age_group": scenario["age_group"], "scenes": {}}

        child = ChildProfile(**scenario["child"])
        plan_data = scenario["plan"]
        plan = ScenePlan(
            title=plan_data["title"],
            scenes=[PlannedScene(**s) for s in plan_data["scenes"]],
            style_notes=StyleNotes(**plan_data["style_notes"]),
        )
        age_style = AGE_STYLES[scenario["age_group"]]
        total = len(plan.scenes)
        previous_summary = "없음"

        # 이미 생성된 장면의 마지막 텍스트를 previous_summary로 사용
        completed = results[sid]["scenes"]
        if completed:
            last_idx = max(int(k) for k in completed.keys())
            previous_summary = completed[str(last_idx)]["text"]

        print(f"\n=== {scenario['name']} ({len(completed)}/{total} done) ===")

        for idx, scene in enumerate(plan.scenes, start=1):
            key = str(idx)
            if key in completed:
                continue

            print(f"  [{idx}/{total}] {scene.scene_id} ({scene.emotion})...", end=" ", flush=True)
            try:
                ps = await personalizer.generate_scene(
                    scene=scene,
                    child=child,
                    previous_summary=previous_summary,
                    age_style=age_style,
                    style_notes=plan.style_notes,
                    scene_index=idx,
                    total_scenes=total,
                )
                completed[key] = {
                    "scene_id": ps.scene_id,
                    "page_number": ps.page_number,
                    "text": ps.text,
                    "illustration_prompt": ps.illustration_prompt,
                }
                previous_summary = ps.text
                _save_results(results)
                print("OK")

                # API 부하 방지: 장면 간 3초 대기
                await asyncio.sleep(3)

            except Exception as e:
                print(f"FAIL ({e})")
                print(f"  >> Saving progress and moving to next scenario.")
                _save_results(results)
                break

    _save_results(results)

    # 결과 요약
    print(f"\n{'='*50}")
    print(f"Results saved to: {RESULTS_FILE}")
    for scenario in SCENARIOS:
        sid = scenario["id"]
        done = len(results.get(sid, {}).get("scenes", {}))
        total = len(scenario["plan"]["scenes"])
        status = "COMPLETE" if done == total else f"PARTIAL ({done}/{total})"
        print(f"  {scenario['name']}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
