import os
import uuid
import requests
from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "static", "images")


def generate_image(image_prompt: str, topic_title: str) -> str:
    """
    DALL-E 3으로 블로그 대표 이미지를 생성하고 로컬에 저장합니다.
    반환값: 저장된 이미지 파일 경로 (static/images/xxx.png)
    """
    os.makedirs(IMAGE_DIR, exist_ok=True)

    # 한국 노무/법무 블로그에 어울리는 프롬프트 보강
    full_prompt = (
        f"{image_prompt}. "
        "Professional, clean, modern Korean office/legal environment. "
        "No text, no people's faces. Suitable for a Korean labor law firm blog thumbnail. "
        "High quality, 16:9 ratio style."
    )

    response = client.images.generate(
        model="dall-e-3",
        prompt=full_prompt,
        size="1792x1024",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url

    # 이미지 다운로드 및 저장
    filename = f"{uuid.uuid4().hex}.png"
    filepath = os.path.join(IMAGE_DIR, filename)

    img_response = requests.get(image_url, timeout=30)
    img_response.raise_for_status()

    with open(filepath, "wb") as f:
        f.write(img_response.content)

    # 웹에서 접근 가능한 경로 반환
    return f"static/images/{filename}"
