import feedparser
import google.generativeai as genai
import pymysql
import requests
import json
import os
import sys
import html
import time
from datetime import datetime
from bs4 import BeautifulSoup
import newspaper

# ==========================================
# [사용자 설정]
# ==========================================

# 1. API 키 설정
GEMINI_API_KEY = ""
TELEGRAM_TOKEN = ""
CHAT_ID = ""

# 2. MySQL 데이터베이스 접속 정보
DB_CONFIG = {
    'host': 'localhost',
    'port': ,
    'user': '',
    'password': '',
    'db': '',
    'charset': 'utf8',
}

# 3. 기타 설정
HISTORY_FILE = "seen_posts.json"
MAX_HISTORY = 1000

# ==========================================
# [시스템 로직]
# ==========================================

genai.configure(api_key=GEMINI_API_KEY)

try:
    model = genai.GenerativeModel('gemini-2.5-flash') 
except Exception as e:
    print(f"⚠️ 모델 초기화 경고: {e}")

# --- 1. DB에서 RSS 목록 가져오기 ---
def get_rss_list_from_db():
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:
            cursor.execute("SELECT url, created_at FROM rss_feeds")
            result = cursor.fetchall()
            return result
    except Exception as e:
        print(f"❌ DB 접속/조회 오류: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- 2. 기록 관리 ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history_list):
    if len(history_list) > MAX_HISTORY:
        history_list = history_list[-MAX_HISTORY:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_list, f, ensure_ascii=False, indent=4)

# --- 3. 기사 본문 추출 (import newspaper 방식 적용) ---
def get_article_content(url, entry=None):
    text = ""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"      ⚠️ [접속 실패] Status Code: {response.status_code} -> RSS 요약본 시도")
        else:
            # 1차: Newspaper4k
            try:
                # [수정] 공식 문서에 따라 input_html을 인자로 전달하여 다운로드 생략 및 자동 파싱
                article = newspaper.article(url, language='ko', input_html=response.text)
                text = article.text.strip()
                print(f"      👉 [1차 파싱(Newspaper4k)] 본문 길이: {len(text)}자")
            except Exception as e:
                print(f"      ⚠️ Newspaper4k 파싱 에러: {e}")
            
            # 2차: BS4
            if len(text) < 100:
                print("      🔧 [2차 파싱(BS4)] Newspaper4k 실패 -> BeautifulSoup 시도")
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
                    tag.decompose()
                
                main_content = soup.find('article') or soup.find('main') or soup
                paragraphs = main_content.find_all('p')
                bs_text = ' '.join([p.get_text().strip() for p in paragraphs])
                
                if len(bs_text) < 100:
                    bs_text = soup.get_text(separator=' ', strip=True)
                
                text = bs_text
                print(f"      👉 [2차 파싱 결과] 본문 길이: {len(text)}자")

    except Exception as e:
        print(f"      ⚠️ 크롤링 에러: {e}")

    # 3차: RSS 요약본
    if (not text or len(text) < 50) and entry:
        print("      🔄 [대체] 파싱 실패/차단됨 -> RSS 요약본 사용")
        if hasattr(entry, 'summary'): text = entry.summary
        elif hasattr(entry, 'description'): text = entry.description
        if len(text) < 10: text = None

    return text

# --- 4. AI 요약 ---
def summarize_article(text, original_title):
    if not text:
        print("      ⚠️ [요약] 본문 없음 (Skip)")
        return None
    
    print("      ✨ [요약] AI 분석 및 번역 중...")
    
    prompt = f"""
    Analyze the following news article and provide the output in strict JSON format.
    
    [Original Title]: {original_title}
    [Text]: {text[:3500]}
    
    Output JSON with these keys:
    1. "original_summary": A 3-sentence summary in the **original language**.
       - **Important**: Summarize the content directly as objective facts or narrative. 
       - **Avoid** phrases like "The author argues...", "The article discusses...", or "According to the text...".
       
    2. "korean_title": The title translated into **Korean**.
    
    3. "korean_summary": The summary translated into **Korean**.
       - **Important**: Use the same direct style as above (no "필자는...", "기사는...").
       - End sentences with a noun form or completed style (e.g., "~함", "~했음" or polite "~니다").
    
    Do not use markdown code blocks. Just output the raw JSON string.
    """
    try:
        response = model.generate_content(prompt)
        response_text = response.text
        
        # JSON 추출 로직
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = response_text[start_idx : end_idx + 1]
            return json.loads(json_str)
        else:
            cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_text)
            
    except Exception as e:
        print(f"      ❌ [AI 에러] : {e}")
        return None

# --- 5. 텔레그램 전송 ---
def send_telegram(title, summary_data, link, source_name, pub_date):
    title = html.unescape(title)
    source_name = html.unescape(source_name)

    if summary_data and isinstance(summary_data, dict):
        orig_summary = html.unescape(summary_data.get('original_summary', '요약 없음'))
        kr_title = html.unescape(summary_data.get('korean_title', '제목 번역 불가'))
        kr_summary = html.unescape(summary_data.get('korean_summary', '내용 번역 불가'))

        message = (
            f"📢 {title}\n"
            f"✅ summary:{orig_summary}\n\n"
            f"📢 {kr_title}\n"
            f"✅ 주요내용:{kr_summary}\n\n"
            f"⭕️ {source_name}\n"
            f"📅 발행일 : {pub_date}\n"
            f"🔗 {link}"
        )
    else:
        message = (
            f"📢 {title}\n"
            f"⭕️ {source_name}\n"
            f"📅 발행일 : {pub_date}\n"
            f"🔗 {link}"
        )
    
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print(f"❌ 전송 실패: {e}")

# --- 메인 실행 ---
def main():
    print(f"\n======== 뉴스 클리핑 시작 ({datetime.now()}) ========")
    
    rss_data_list = get_rss_list_from_db()
    
    if not rss_data_list:
        print("⚠️ DB에 등록된 RSS가 없습니다.")
        return

    print(f"✅ 구독 중인 채널: {len(rss_data_list)}개")

    seen_links = load_history()
    new_links_count = 0

    for rss_url, feed_created_at in rss_data_list:
        print(f"\n📡 검색 중: {rss_url}")
        try:
            feed = feedparser.parse(rss_url)
            source_title = feed.feed.title if 'title' in feed.feed else "News"
            
            # 모든 글을 순회 (최신순 필터링은 내부 로직에서 처리)
            for entry in feed.entries:
                link = entry.link
                
                if link in seen_links:
                    continue

                # 글 작성 시간 파악
                entry_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    entry_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    entry_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                
                # RSS DB 등록일 필터링 (등록일 이전 글 무시)
                if entry_date and feed_created_at:
                    if entry_date < feed_created_at:
                        continue

                print(f"   🆕 새 글 발견! : {entry.title}")
                
                pub_date_str = entry_date.strftime('%Y년 %m월 %d일') if entry_date else "날짜 정보 없음"

                content = get_article_content(link, entry)
                
                summary_data = None
                if content:
                    summary_data = summarize_article(content, entry.title)
                
                send_telegram(entry.title, summary_data, link, source_title, pub_date_str)
                
                seen_links.append(link)
                new_links_count += 1
                
        except Exception as e:
            print(f"   ❌ RSS 파싱 오류: {e}")
    
    if new_links_count > 0:
        save_history(seen_links)
        print(f"\n✅ 총 {new_links_count}개의 뉴스를 전송했습니다.")
    else:
        print("\n💤 새로 업데이트된 뉴스가 없습니다.")

if __name__ == "__main__":
    main()
