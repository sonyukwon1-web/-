import json
import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

load_dotenv()

from generator import generate_blog_post
from image_gen import generate_image
from publisher import publish_sync

app = Flask(__name__)

TOPICS_FILE = os.path.join(os.path.dirname(__file__), "topics.json")
DRAFT_FILE = os.path.join(os.path.dirname(__file__), "current_draft.json")


def load_topics() -> list:
    with open(TOPICS_FILE, encoding="utf-8") as f:
        return json.load(f)["topics"]


def get_next_topic_id() -> int:
    """마지막으로 발행한 주제 다음 ID 반환"""
    history_file = os.path.join(os.path.dirname(__file__), "publish_history.json")
    if os.path.exists(history_file):
        with open(history_file, encoding="utf-8") as f:
            history = json.load(f)
        used_ids = {item["topic_id"] for item in history}
        topics = load_topics()
        for topic in topics:
            if topic["id"] not in used_ids:
                return topic["id"]
        # 모든 주제 사용 시 처음부터
        return topics[0]["id"]
    return load_topics()[0]["id"]


def save_publish_history(draft: dict, naver_url: str):
    history_file = os.path.join(os.path.dirname(__file__), "publish_history.json")
    history = []
    if os.path.exists(history_file):
        with open(history_file, encoding="utf-8") as f:
            history = json.load(f)
    history.append(
        {
            "topic_id": draft.get("topic_id"),
            "topic_title": draft.get("topic_title"),
            "title": draft.get("title"),
            "naver_url": naver_url,
            "published_at": draft.get("created_at"),
        }
    )
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# 생성 작업 상태 관리
generation_status = {"status": "idle", "message": "", "draft": None}


@app.route("/")
def index():
    topics = load_topics()
    history = []
    history_file = os.path.join(os.path.dirname(__file__), "publish_history.json")
    if os.path.exists(history_file):
        with open(history_file, encoding="utf-8") as f:
            history = json.load(f)
    return render_template("index.html", topics=topics, history=history[-10:])


@app.route("/static/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "static", "images"), filename
    )


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.json
    topic_id = data.get("topic_id")

    if not topic_id:
        topic_id = get_next_topic_id()

    topics = load_topics()
    topic = next((t for t in topics if t["id"] == int(topic_id)), None)
    if not topic:
        return jsonify({"error": "주제를 찾을 수 없습니다."}), 404

    generation_status["status"] = "generating"
    generation_status["message"] = f"'{topic['title']}' 글 생성 중..."
    generation_status["draft"] = None

    def generate_async():
        try:
            # 1. 글 생성
            generation_status["message"] = "Claude AI로 글 작성 중... (30~60초 소요)"
            draft = generate_blog_post(topic)

            # 2. 이미지 생성
            generation_status["message"] = "DALL-E로 이미지 생성 중... (20~30초 소요)"
            image_path = generate_image(draft["image_prompt"], topic["title"])
            draft["image_path"] = image_path

            # 3. 드래프트 저장
            with open(DRAFT_FILE, "w", encoding="utf-8") as f:
                json.dump(draft, f, ensure_ascii=False, indent=2)

            generation_status["status"] = "done"
            generation_status["message"] = "생성 완료!"
            generation_status["draft"] = draft

        except Exception as e:
            generation_status["status"] = "error"
            generation_status["message"] = f"오류: {str(e)}"

    thread = threading.Thread(target=generate_async)
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started", "topic": topic["title"]})


@app.route("/api/status")
def api_status():
    return jsonify(generation_status)


@app.route("/api/draft")
def api_draft():
    if os.path.exists(DRAFT_FILE):
        with open(DRAFT_FILE, encoding="utf-8") as f:
            draft = json.load(f)
        return jsonify(draft)
    return jsonify({}), 404


@app.route("/api/publish", methods=["POST"])
def api_publish():
    data = request.json
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    image_path = data.get("image_path", "")
    tags = data.get("tags", [])

    if not title or not content:
        return jsonify({"error": "제목과 내용이 필요합니다."}), 400

    # 발행 실행 (브라우저가 열림)
    result = publish_sync(title, content, image_path, tags)

    if result["success"]:
        # 히스토리 저장
        draft = {"title": title, "topic_id": data.get("topic_id"), "topic_title": data.get("topic_title"), "created_at": data.get("created_at")}
        save_publish_history(draft, result["url"])
        return jsonify({"success": True, "url": result["url"]})
    else:
        return jsonify({"success": False, "error": result["error"]}), 500


@app.route("/api/topics")
def api_topics():
    return jsonify(load_topics())


if __name__ == "__main__":
    print("=" * 50)
    print("노무법인 유영 - 자동 블로그 발행 시스템")
    print("브라우저에서 http://localhost:5000 을 열어주세요")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
