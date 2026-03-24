import anthropic
import json
import os
from datetime import datetime


client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def generate_blog_post(topic: dict) -> dict:
    """
    주어진 주제로 네이버 블로그용 글을 생성합니다.
    반환값: { title, content, summary, tags, image_prompt }
    """
    keywords_str = ", ".join(topic["keywords"])
    today = datetime.now().strftime("%Y년 %m월 %d일")

    prompt = f"""당신은 공인노무사 사무소 '노무법인 유영'의 블로그 전문 작가입니다.
아래 주제로 네이버 블로그에 발행할 실용적이고 전문적인 블로그 글을 작성해주세요.

주제: {topic['title']}
키워드: {keywords_str}
설명: {topic['description']}
작성일: {today}

작성 지침:
1. 제목은 검색에 잘 걸리도록 구체적이고 실용적으로 작성 (예: "[2025년 최신] 임금체불 신고 방법 완벽 가이드")
2. 글 길이: 1,500~2,500자 분량
3. 구조: 도입부 → 핵심 내용 (소제목 포함) → 마무리 및 상담 안내
4. 어투: 친근하지만 전문적인 말투 (독자가 실질적인 도움을 받을 수 있도록)
5. 마지막에 "노무법인 유영에 문의하기" CTA 포함
6. HTML 태그 없이 순수 텍스트로 작성
7. 소제목은 [소제목] 형식으로 표시

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "title": "블로그 제목",
  "content": "블로그 본문 내용",
  "summary": "블로그 요약 (2-3문장, 메타 설명용)",
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "image_prompt": "이 글의 대표 이미지 생성을 위한 영어 프롬프트 (DALL-E용, 전문적이고 한국적인 직장/법무 관련 이미지)"
}}"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # JSON 파싱
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    result = json.loads(response_text)
    result["topic_id"] = topic["id"]
    result["topic_title"] = topic["title"]
    result["created_at"] = datetime.now().isoformat()
    return result
