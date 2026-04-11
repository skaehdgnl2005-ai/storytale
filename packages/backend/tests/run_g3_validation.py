"""G3 품질 게이트 — 생성된 텍스트 검증 스크립트.

g3_results.json의 결과를 가드레일 기준으로 검증한다.

Usage:
    cd packages/backend
    .venv/Scripts/python -m tests.run_g3_validation
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from storytale.interpreter.safety_checker import SafetyChecker  # noqa: E402

SEEDS_DIR = Path(__file__).resolve().parents[3] / "docs" / "guardrail-seeds"
RESULTS_FILE = Path(__file__).resolve().parent / "g3_results.json"


def load_json(name: str):
    return json.loads((SEEDS_DIR / name).read_text(encoding="utf-8"))


AGE_STYLE_GUIDES = load_json("age-style-guides.json")
AGE_STYLES = {g["age_group"]: g for g in AGE_STYLE_GUIDES}
SAFETY_RAILS = load_json("safety-rails.json")

CHILD_INFO = {
    "A": {"name": "\ud558\uc740", "comfort_object": "\ud1a0\ub2c8", "friend_name": "\uc11c\uc900", "favorite_animal": "\ud1a0\ub07c"},
    "B": {"name": "\uc2dc\uc6b0", "comfort_object": "\ub514\ub178", "friend_name": "\uc9c0\uc544", "favorite_animal": "\ud2b8\ub9ac\ucf00\ub77c\ud1b1\uc2a4"},
    "C": {"name": "\ubbfc\uc900", "comfort_object": "\ubcf4\uc774", "friend_name": "\uc720\uc9c4", "favorite_animal": "\uac15\uc544\uc9c0"},
}


def split_sentences(text: str) -> list[str]:
    lines = text.replace("\\n", "\n").split("\n")
    sentences: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?\u3002\u2026])\s*", line)
        for p in parts:
            p = p.strip()
            if p:
                sentences.append(p)
    return sentences


def main() -> None:
    results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    checker = SafetyChecker(content_filter=SAFETY_RAILS["content_filter"])

    all_pass = True
    gate_results: dict[str, str] = {}

    for sid in ["A", "B", "C"]:
        scenario = results[sid]
        age_group = scenario["age_group"]
        age_style = AGE_STYLES[age_group]
        child = CHILD_INFO[sid]
        scenes = scenario["scenes"]
        max_chars = age_style["sentence_rules"]["max_characters_per_sentence"]

        all_texts = [s["text"] for s in scenes.values()]
        full_text = "\n".join(all_texts)
        sentences = split_sentences(full_text)

        print(f"\n{'='*60}")
        print(f"[{sid}] {scenario['name']} (age: {age_group}, scenes: {len(scenes)})")
        print(f"{'='*60}")

        # --- Print all scene texts ---
        for key, scene in sorted(scenes.items(), key=lambda x: int(x[0])):
            print(f"\n  [{key}] {scene['scene_id']}:")
            for line in scene["text"].split("\n"):
                print(f"    {line}")

        print(f"\n--- Validation ---")
        scenario_pass = True

        # G3-2: Personalization
        name = child["name"]
        name_count = full_text.count(name)
        name_sentence_count = sum(1 for s in sentences if name in s)
        name_ratio = name_sentence_count / len(sentences) if sentences else 0

        co = child["comfort_object"]
        co_count = full_text.count(co)

        if name_count < 2:
            print(f"  [FAIL] name '{name}' appears only {name_count}x (need >=2)")
            scenario_pass = False
        elif name_ratio >= 0.8:
            print(f"  [FAIL] name '{name}' in {name_ratio:.0%} of sentences (mechanical)")
            scenario_pass = False
        else:
            print(f"  [PASS] personalization: name '{name}' {name_count}x, ratio {name_ratio:.0%}")

        if co_count < 2:
            print(f"  [FAIL] comfort_object '{co}' appears only {co_count}x (need >=2)")
            scenario_pass = False
        else:
            print(f"  [PASS] comfort_object: '{co}' {co_count}x")

        # G3-3: Age-style sentence length
        threshold = int(max_chars * 1.2)
        violations = []
        for i, s in enumerate(sentences):
            clen = len(s.strip())
            if clen > threshold:
                violations.append(f"    sentence {i+1} ({clen} chars): '{s[:50]}...'")

        violation_ratio = len(violations) / len(sentences) if sentences else 0
        if violation_ratio > 0.2:
            print(f"  [FAIL] sentence length: {len(violations)}/{len(sentences)} violations ({violation_ratio:.0%} > 20%)")
            for v in violations:
                print(v)
            scenario_pass = False
        elif violations:
            print(f"  [WARN] sentence length: {len(violations)} violations ({violation_ratio:.0%}), within tolerance")
            for v in violations:
                print(v)
        else:
            print(f"  [PASS] sentence length: all within {max_chars} chars (+20%)")

        avg_len = sum(len(s) for s in sentences) / len(sentences) if sentences else 0
        print(f"         avg sentence length: {avg_len:.1f} chars (limit: {max_chars})")

        # G3-5: Safety filter
        safety_violations = []
        for key, scene in scenes.items():
            result = checker.check_text(scene["text"])
            if result.blocked:
                safety_violations.append(
                    f"    scene '{scene['scene_id']}': {result.matched_keyword} ({result.matched_intent})"
                )

        if safety_violations:
            print(f"  [FAIL] safety: {len(safety_violations)} violations")
            for sv in safety_violations:
                print(sv)
            scenario_pass = False
        else:
            print(f"  [PASS] safety: content_filter passed")

        # Illustration prompt checks
        illust_issues = []
        for key, scene in scenes.items():
            prompt = scene.get("illustration_prompt", "")
            korean_chars = len(re.findall(r"[\uac00-\ud7a3]", prompt))
            total_chars = len(prompt)
            if total_chars > 0:
                korean_ratio = korean_chars / total_chars
                if korean_ratio > 0.1:
                    illust_issues.append(f"    scene '{scene['scene_id']}': {korean_ratio:.0%} Korean")
            if name in prompt:
                illust_issues.append(f"    scene '{scene['scene_id']}': child name in prompt")

        if illust_issues:
            print(f"  [FAIL] illustration prompts: {len(illust_issues)} issues")
            for ii in illust_issues:
                print(ii)
            scenario_pass = False
        else:
            print(f"  [PASS] illustration prompts: english, no child name")

        # Summary stats
        print(f"\n  [STATS] sentences: {len(sentences)}, avg_len: {avg_len:.1f}, "
              f"violations: {len(violations)}, safety: {len(safety_violations)}")

        if scenario_pass:
            gate_results[sid] = "PASS"
        else:
            gate_results[sid] = "FAIL"
            all_pass = False

    # Final summary
    print(f"\n{'='*60}")
    print(f"G3 Quality Gate Summary")
    print(f"{'='*60}")
    for sid, result in gate_results.items():
        print(f"  [{result}] {sid}: {results[sid]['name']}")

    if all_pass:
        print(f"\n  >>> G3 PASSED <<<")
    else:
        print(f"\n  >>> G3 FAILED <<<")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
