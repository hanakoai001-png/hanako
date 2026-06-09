import os
import re
from datetime import datetime
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ===== FAQ パターン（花屋はなとく専用） =====
FAQ_PATTERNS = [
    (
        r"営業時間",
        "営業時間は10:00〜19:00です。年始休暇以外は年中無休で営業しております。お気軽にお越しください。",
    ),
    (
        r"定休日|休み|お休み",
        "年始休暇以外は年中無休で営業しております。営業時間は10:00〜19:00です。",
    ),
    (
        r"料金|値段|いくら",
        "仏花・墓花は480円〜、季節のミニ花束は330円〜ご用意しております。花束やアレンジメントはご予算に応じてお作りいたします。お気軽にご相談ください。",
    ),
    (
        r"予約|よやく",
        "ご予約はお電話（072-437-7687）またはご来店にて承っております。お気軽にどうぞ。",
    ),
    (
        r"アクセス|場所|どこ",
        "南海春木駅より徒歩圏内にございます。詳しくはお電話（072-437-7687）にてご確認ください。",
    ),
    (
        r"電話|連絡先",
        "お電話番号は 072-437-7687 です。営業時間（10:00〜19:00）内にお気軽にお電話ください。",
    ),
    (
        r"仏花|墓花",
        "仏花・墓花は480円〜ご用意しております。各種サイズ取り揃えておりますので、ご来店またはお電話でご相談ください。",
    ),
    (
        r"花束|アレンジ",
        "花束・アレンジメントはご予算に応じてお作りいたします。プレゼントやギフトなど、お気軽にご相談ください。",
    ),
]

# ===== システムプロンプト（花屋はなとく専用） =====
SYSTEM_PROMPT = """あなたは花屋はなとくの受付スタッフです。
お客様に対して丁寧な敬語で、温かみのある接客口調で返答してください。

【お店の基本情報】
- 店名：花屋はなとく
- 営業時間：10:00〜19:00
- 定休日：年始休暇のみ（ほぼ年中無休）
- 最寄り駅：南海春木駅
- 電話番号：072-437-7687
- 予約方法：お電話またはご来店にて承ります

【料金・メニュー】
- 仏花・墓花：480円〜
- 季節のミニ花束：330円〜
- 花束・アレンジメント：ご予算に応じてお作りします

【話し方のルール】
- 丁寧な敬語（です・ます調）
- 温かく親しみやすい接客トーン
- 返答は2〜3文程度、簡潔に
- 絵文字は使わない
- お花に関する質問には具体的に答える

【情報が不明な場合】
「詳しくはお電話（072-437-7687）またはご来店にてご確認ください。」と案内する

【NG表現】
- 友達口調
- 箇条書きや長文
- 「お問い合わせください」だけで終わる返答"""


def is_business_hours() -> bool:
    now = datetime.now()
    return 10 <= now.hour < 19


def get_faq_reply(text: str) -> str | None:
    for pattern, reply in FAQ_PATTERNS:
        if re.search(pattern, text):
            return reply
    return None


def get_claude_reply(text: str) -> str:
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return message.content[0].text


def handle_message(text: str) -> str:
    if not is_business_hours():
        return "現在営業時間外です。営業時間は10:00〜19:00となっております。翌営業日にあらためてご連絡いただくか、お電話（072-437-7687）にてご確認ください。"

    faq_reply = get_faq_reply(text)
    if faq_reply:
        return faq_reply

    return get_claude_reply(text)
