import csv
from collections import defaultdict

with open("sample.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# 合計金額
total = sum(int(row["金額"]) for row in rows)
print(f"【合計金額】{total:,}円")

# 一番売れた商品（金額合計が最大）
product_total = defaultdict(int)
for row in rows:
    product_total[row["商品名"]] += int(row["金額"])

best_product = max(product_total, key=product_total.get)
print(f"【一番売れた商品】{best_product}（合計 {product_total[best_product]:,}円）")

# 月別集計
monthly = defaultdict(int)
for row in rows:
    month = row["日付"][:7]  # "YYYY-MM"
    monthly[month] += int(row["金額"])

print("【月別集計】")
for month in sorted(monthly):
    print(f"  {month}：{monthly[month]:,}円")
