import asyncio
import json
import os
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


COOKIES_FILE = os.path.join(os.path.dirname(__file__), "naver_cookies.json")


async def _login_naver(page, naver_id: str, naver_pw: str):
    """네이버 로그인 (쿠키 없을 때)"""
    await page.goto("https://nid.naver.com/nidlogin.login", wait_until="networkidle")

    # JavaScript로 ID/PW 입력 (보안 필터 우회)
    await page.evaluate(f"document.querySelector('#id').value = '{naver_id}'")
    await page.evaluate(f"document.querySelector('#pw').value = '{naver_pw}'")
    await page.click(".btn_login")

    # OTP / 2단계 인증 대기 (최대 60초)
    try:
        await page.wait_for_url("https://www.naver.com/**", timeout=60000)
    except PlaywrightTimeout:
        raise Exception(
            "로그인 실패 또는 2단계 인증이 필요합니다. "
            "브라우저 창에서 직접 인증을 완료해주세요."
        )


async def _save_cookies(context):
    """쿠키 저장 (다음 실행 시 재사용)"""
    cookies = await context.cookies()
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


async def _load_cookies(context):
    """저장된 쿠키 불러오기"""
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        return True
    return False


async def _is_logged_in(page) -> bool:
    """로그인 상태 확인"""
    await page.goto("https://www.naver.com", wait_until="networkidle")
    try:
        await page.wait_for_selector(".MyView-module__my_menu___fvHgA", timeout=3000)
        return True
    except PlaywrightTimeout:
        return False


async def _format_content_for_blog(content: str) -> str:
    """블로그 본문 포맷팅 (소제목 처리 등)"""
    lines = content.split("\n")
    formatted = []
    for line in lines:
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            # 소제목
            formatted.append(f"\n▶ {line[1:-1]}\n")
        elif line:
            formatted.append(line)
        else:
            formatted.append("")
    return "\n".join(formatted)


async def publish_to_naver(
    title: str,
    content: str,
    image_path: str,
    tags: list[str],
) -> dict:
    """
    네이버 블로그에 글을 발행합니다.
    반환값: { success: bool, url: str, error: str }
    """
    naver_id = os.getenv("NAVER_ID")
    naver_pw = os.getenv("NAVER_PW")
    blog_id = os.getenv("NAVER_BLOG_ID", naver_id)

    if not naver_id or not naver_pw:
        return {"success": False, "url": "", "error": "NAVER_ID 또는 NAVER_PW가 설정되지 않았습니다."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # 진행 상황을 볼 수 있도록 headless=False
            args=["--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()

        try:
            # 쿠키로 로그인 시도
            await _load_cookies(context)
            logged_in = await _is_logged_in(page)

            if not logged_in:
                print("로그인 중...")
                await _login_naver(page, naver_id, naver_pw)
                await _save_cookies(context)
                print("로그인 완료, 쿠키 저장됨")

            # 블로그 글쓰기 페이지 이동
            write_url = f"https://blog.naver.com/{blog_id}/postwrite"
            await page.goto(write_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # SmartEditor ONE이 iframe 안에 있을 수 있음
            # 제목 입력
            try:
                title_selector = "input.se-title-input, input[placeholder*='제목'], .se-title-text"
                await page.wait_for_selector(title_selector, timeout=10000)
                await page.click(title_selector)
                await page.keyboard.press("Control+a")
                await page.type(title_selector, title, delay=50)
            except PlaywrightTimeout:
                # iframe 내부 시도
                frame = None
                for f in page.frames:
                    if "postwrite" in f.url or "editor" in f.url:
                        frame = f
                        break
                if frame:
                    await frame.click("input.se-title-input")
                    await frame.type("input.se-title-input", title, delay=50)

            await asyncio.sleep(1)

            # 본문 입력
            formatted_content = await _format_content_for_blog(content)
            body_selector = ".se-content, .se-editable, div[contenteditable='true']"
            try:
                await page.wait_for_selector(body_selector, timeout=10000)
                await page.click(body_selector)
                await asyncio.sleep(0.5)
                # 줄별로 입력 (한 번에 입력 시 깨지는 경우 방지)
                for line in formatted_content.split("\n"):
                    await page.keyboard.type(line, delay=10)
                    await page.keyboard.press("Enter")
            except PlaywrightTimeout:
                print("본문 입력 영역을 찾지 못했습니다. 수동으로 확인해주세요.")

            await asyncio.sleep(1)

            # 이미지 업로드
            if image_path and os.path.exists(image_path):
                try:
                    # 이미지 첨부 버튼 클릭
                    img_btn = ".se-toolbar-item-image, button[data-testid='image'], .se-image-toolbar-btn"
                    await page.click(img_btn)
                    await asyncio.sleep(1)

                    # 파일 선택 다이얼로그
                    async with page.expect_file_chooser() as fc_info:
                        await page.click(img_btn)
                    file_chooser = await fc_info.value
                    abs_path = str(Path(image_path).resolve())
                    await file_chooser.set_files(abs_path)
                    await asyncio.sleep(2)
                    print("이미지 업로드 완료")
                except Exception as e:
                    print(f"이미지 업로드 실패 (수동으로 추가 가능): {e}")

            # 태그 입력
            if tags:
                try:
                    tag_selector = "input.tag_input, input[placeholder*='태그']"
                    await page.wait_for_selector(tag_selector, timeout=5000)
                    for tag in tags[:5]:  # 최대 5개
                        await page.click(tag_selector)
                        await page.type(tag_selector, tag, delay=30)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(0.3)
                except PlaywrightTimeout:
                    print("태그 입력 영역을 찾지 못했습니다.")

            # 발행 버튼 클릭
            publish_selector = (
                "button.publish_btn, "
                "button[data-testid='publishButton'], "
                "button:has-text('발행'), "
                ".btn_publish"
            )
            await page.wait_for_selector(publish_selector, timeout=10000)
            await page.click(publish_selector)
            await asyncio.sleep(2)

            # 발행 확인 팝업 처리
            try:
                confirm_selector = "button:has-text('확인'), button:has-text('발행하기'), .btn_confirm"
                await page.wait_for_selector(confirm_selector, timeout=5000)
                await page.click(confirm_selector)
                await asyncio.sleep(3)
            except PlaywrightTimeout:
                pass  # 팝업 없는 경우

            # 발행 완료 후 URL 수집
            current_url = page.url
            print(f"발행 완료: {current_url}")

            await _save_cookies(context)
            await browser.close()

            return {"success": True, "url": current_url, "error": ""}

        except Exception as e:
            await browser.close()
            return {"success": False, "url": "", "error": str(e)}


def publish_sync(title: str, content: str, image_path: str, tags: list[str]) -> dict:
    """동기 래퍼 함수 (Flask에서 호출용)"""
    return asyncio.run(publish_to_naver(title, content, image_path, tags))
