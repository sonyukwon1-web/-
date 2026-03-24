# 노무법인 유영 - 자동 블로그 발행 시스템

AI가 노무 관련 블로그 글과 이미지를 자동 생성하고, 검토 후 네이버 블로그에 발행하는 시스템입니다.

## 사용 방법

### 1. 설치

```bash
cd auto-blog
pip install -r requirements.txt
playwright install chromium
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 API 키와 네이버 계정 정보 입력
```

### 3. 실행

```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

### 4. 사용 흐름

1. 주제 선택 (또는 자동 순서)
2. "AI 글 생성하기" 클릭 → 1~2분 대기
3. 생성된 글과 이미지 검토/수정
4. "네이버 블로그에 발행하기" 클릭 → 브라우저 자동 실행

## 주제 추가/수정

`topics.json` 파일에서 직접 편집하세요.

## 주의사항

- 첫 로그인 시 네이버 2단계 인증이 필요할 수 있습니다. 브라우저 창에서 직접 인증 후 자동 진행됩니다.
- 로그인 후 쿠키가 `naver_cookies.json`에 저장되어 다음 실행 시 재사용됩니다.
- `.env` 파일은 절대 GitHub에 올리지 마세요.
