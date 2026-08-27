import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime
import re
import urllib3
import os

# SSL警告を抑制
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def scrape_nli_reports():
    """ニッセイ基礎研究所の中国経済レポート一覧をスクレイピング"""
    
    url = "https://www.nli-research.co.jp/report_tag/tag_id=87?site=nli"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print("📡 レポートページにアクセス中...")
    
    try:
        response = requests.get(
            url, 
            headers=headers, 
            timeout=30,
            verify=False
        )
        response.raise_for_status()
        response.encoding = 'utf-8'
        print("✅ ページ取得成功！")
    except Exception as e:
        print(f"❌ ページ取得エラー: {e}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    articles = []
    
    # 日付パターン
    date_pattern = re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日')
    
    print("🔍 レポート一覧を解析中...")
    
    # ★★★ ページ構造に合わせた抽出 ★★★
    # レポートアイテムは 'li' タグで class="item" になっている
    report_items = soup.select('ul.two-col li.item')
    
    if not report_items:
        print("⚠️ レポートアイテムが見つかりません。別のセレクタを試します...")
        # 代替：cont_top 内の li
        report_items = soup.select('.cont_top ul li')
    
    print(f"📋 {len(report_items)}件のレポートアイテムを検出")
    
    for item in report_items:
        try:
            # 日付を抽出
            date_elem = item.find('div', class_='date')
            date_text = ""
            if date_elem:
                date_text = date_elem.get_text(strip=True)
            else:
                # クラスが pagetop_report の場合もある
                date_elem = item.find('div', class_='pagetop_report')
                if date_elem:
                    date_elem_inner = date_elem.find('div', class_='date')
                    if date_elem_inner:
                        date_text = date_elem_inner.get_text(strip=True)
            
            # タイトルとリンクを抽出
            title_elem = item.find('h2')
            if not title_elem:
                # h3 の場合もある
                title_elem = item.find('h3')
            
            if not title_elem:
                continue
                
            link_elem = title_elem.find('a')
            if not link_elem:
                continue
            
            title = link_elem.get_text(strip=True)
            href = link_elem.get('href')
            
            if not href:
                continue
            
            # 絶対URLに変換
            if href.startswith('/'):
                href = 'https://www.nli-research.co.jp' + href
            elif not href.startswith('http'):
                href = 'https://www.nli-research.co.jp/' + href
            
            # 日付をフォーマット（YYYY-MM-DD）
            date_formatted = ""
            if date_text:
                date_match = date_pattern.search(date_text)
                if date_match:
                    year = int(date_match.group(1))
                    month = int(date_match.group(2))
                    day = int(date_match.group(3))
                    # 日付の妥当性を簡単にチェック（2000年以降）
                    if year >= 2000 and 1 <= month <= 12 and 1 <= day <= 31:
                        date_formatted = f"{year}-{month:02d}-{day:02d}"
                    else:
                        # 異常な日付は空にする
                        date_formatted = ""
            
            # 説明文を抽出（first_sentence）
            desc_elem = item.find('div', class_='first_sentence')
            description = ""
            if desc_elem:
                description = desc_elem.get_text(strip=True)
            else:
                # 簡易説明
                description = f"ニッセイ基礎研究所: {title}"
            
            # 重複を防ぐ
            if not any(a['link'] == href for a in articles):
                articles.append({
                    'title': title,
                    'link': href,
                    'date': date_formatted,
                    'description': description[:200] + "..." if len(description) > 200 else description
                })
                
        except Exception as e:
            print(f"⚠️ アイテム解析中にエラー: {e}")
            continue
    
    # 日付でソート（新しい順）
    articles.sort(key=lambda x: x['date'], reverse=True)
    
    print(f"📝 {len(articles)}件のレポートが見つかりました")
    
    # デバッグ：最初の5件を表示
    for i, article in enumerate(articles[:5], 1):
        print(f"  {i}. {article['title'][:40]}... ({article['date']})")
    
    return articles

def generate_rss(articles):
    """RSSフィードを生成"""
    
    if not articles:
        print("⚠️ レポートが見つからないため、RSSを生成しません")
        return
    
    fg = FeedGenerator()
    fg.title('ニッセイ基礎研究所 中国経済レポートRSS')
    fg.description('ニッセイ基礎研究所の「中国経済」タグが付けられたレポートのRSSフィード')
    fg.link(href='https://www.nli-research.co.jp/report_tag/tag_id=87?site=nli', rel='alternate')
    fg.language('ja')
    
    # 現在の日時を最終更新日時に設定（JST）
    now_jst = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0900')
    fg.lastBuildDate(now_jst)
    
    # 最新30件までをRSSに追加
    for article in articles[:30]:
        fe = fg.add_entry()
        fe.title(article['title'])
        fe.link(href=article['link'])
        fe.description(article['description'])
        
        # 日付があれば設定
        if article['date']:
            try:
                pub_date = datetime.strptime(article['date'], '%Y-%m-%d')
                fe.pubDate(pub_date.strftime('%a, %d %b %Y %H:%M:%S +0900'))
            except:
                fe.pubDate(now_jst)
        else:
            fe.pubDate(now_jst)
        
        fe.guid(article['link'], permalink=True)
    
    rss_path = 'rss.xml'
    fg.rss_file(rss_path)
    print(f"✅ RSSフィードを生成しました: {rss_path}")
    
    file_size = os.path.getsize(rss_path)
    print(f"📊 ファイルサイズ: {file_size} bytes")

def main():
    print("=" * 50)
    print("🚀 RSSフィード生成を開始します...")
    print("=" * 50)
    
    articles = scrape_nli_reports()
    
    if articles:
        generate_rss(articles)
        print("\n✅ RSS生成が完了しました！")
        print(f"📡 RSSフィードURL: https://raw.githubusercontent.com/あなたのユーザー名/リポジトリ名/main/rss.xml")
    else:
        print("⚠️ レポートが見つかりませんでした。")
        print("💡 ヒント: ウェブページのHTML構造が変更されている可能性があります。")
    
    print("=" * 50)
    print("🏁 処理が完了しました！")

if __name__ == "__main__":
    main()