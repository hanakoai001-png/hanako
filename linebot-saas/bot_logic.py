import os
import re
from datetime import datetime
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

FAQ_PATTERNS = [
    (r"営業時間", "営業時間は10時〜19時です。"),
    (r"料金|価格|費用|いくら", "料金はメニューによって異なります。カウンセリング後にご案内いたしますので、まずはお気軽にご相談ください。"),
    (r"予約|よやく", "ご予約はこちらから承ります。希望日時をお知らせください。"),
    (r"アクセス|住所|場所|どこ", "住所は〇〇です。最寄り駅は〇〇駅です。"),
]

SYSTEM_PROMPT = """あなたはサロンの受付スタッフです。
お客様に対して丁寧な敬語を使いながら、
温かみのある自然な接客口調で返答してください。

【話し方のルール】
- 丁寧な敬語を使う（です・ます調）
- 温かみがあり、親しみやすい接客トーン
- 絵文字は使わない
- 返答は2〜3文程度、簡潔に
- LINEらしい自然な文体で

【良い返答の例】
- 「ありがとうございます。〇〇についてご案内いたします。」
- 「はい、承っております。お気軽にご相談ください。」
- 「詳しくはスタッフが確認してご連絡いたします。」
- 「ご不明な点がございましたら、いつでもお声がけください。」

【NG表現】
- フレンドリーすぎる口調（「〜ですよ！」「〜ですね〜」）
- 箇条書きや長文
- 「詳細はお問い合わせください」だけで終わる冷たい返答
- 過剰な敬語（「〜でございましょうか」など堅すぎるもの）

【情報が不明な場合】
推測せず「確認してご連絡いたします。少々お待ちください。」
と返答すること。"""


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
        return "現在営業時間外です。翌営業日にご連絡いたします。"

    faq_reply = get_faq_reply(text)
    if faq_reply:
        return faq_reply

    return get_claude_reply(text)
