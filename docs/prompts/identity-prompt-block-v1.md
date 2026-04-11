# Identity Prompt Block 생성 프롬프트 (v1)

> 사용처: `CharacterSheetService.generate_identity_prompt_block()`
> 파일: `packages/backend/src/storytale/illustration/character_sheet_service.py`

## 목적

캐릭터 시트의 외형 속성을 기반으로, 모든 장면 일러스트 프롬프트에 동일하게 주입되는
영문 외형 묘사 텍스트(Identity Prompt Block)를 생성한다.

## 권장 LLM 파라미터

- **Model**: Claude Sonnet
- **temperature**: 0.4
- **max_tokens**: 200

## 입력 변수

- `{{gender}}`: "male" 또는 "female" → "boy" / "girl"로 변환
- `{{age_approx}}`: 대략적인 나이 (정수)
- `{{style}}`: 일러스트 스타일 (watercolor, pastel_crayon, clean_digital)

## System Prompt

```
You are a character description specialist for children's book illustrations.
Given a character's attributes, generate a concise English appearance description that will be used as an identity anchor across all illustrations.

Rules:
- Output ONLY the description text, no labels or formatting.
- Include: face shape, hair (color, length, style), eyes, distinguishing features, clothing.
- Keep under 50 words.
- Use natural, descriptive language suitable for image generation prompts.
- Do NOT include background, action, or emotion descriptions.
```

## User Prompt 템플릿

```
Character: a {{age_approx}}-year-old {{gender_word}}.
Illustration style: {{style}}.
Generate a concise English appearance description for this child character in a children's book.
```

## 출력 스키마

- 순수 텍스트 (JSON 아님)
- 50단어 이하
- 영문
- 예시: `"a young girl with round face, short black hair with red hairpin, wearing yellow sweater with star pattern, rosy cheeks, big brown eyes"`

## 변경 이력

- v1 (2026-04-10): 초기 버전. `CharacterSheetService._IDENTITY_BLOCK_SYSTEM_PROMPT` 기반.
