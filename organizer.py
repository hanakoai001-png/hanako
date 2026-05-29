import sys
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 分類ルール
CATEGORIES = {
    "画像": [".jpg", ".jpeg", ".png", ".gif"],
    "文書": [".pdf", ".docx", ".txt"],
    "データ": [".xlsx", ".csv"],
    "動画": [".mp4", ".mov"],
}

TEST_FOLDER = Path(__file__).parent / "test"

TEST_FILES = [
    "photo1.jpg",
    "photo2.png",
    "animation.gif",
    "report.pdf",
    "memo.txt",
    "document.docx",
    "sales.xlsx",
    "data.csv",
    "movie.mp4",
    "clip.mov",
    "unknown.zip",
]


def create_test_files():
    TEST_FOLDER.mkdir(exist_ok=True)
    for filename in TEST_FILES:
        filepath = TEST_FOLDER / filename
        if not filepath.exists():
            filepath.touch()
    print(f"テストファイルを作成しました: {TEST_FOLDER}\n")


def get_category(extension: str) -> str | None:
    ext = extension.lower()
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return None


def organize_files():
    if not TEST_FOLDER.exists():
        print(f"フォルダが見つかりません: {TEST_FOLDER}")
        return

    files = [f for f in TEST_FOLDER.iterdir() if f.is_file()]
    if not files:
        print("ファイルが見つかりませんでした。")
        return

    results = {"移動済み": [], "未分類": []}

    for file in files:
        category = get_category(file.suffix)
        if category:
            dest_dir = TEST_FOLDER / category
            dest_dir.mkdir(exist_ok=True)
            dest_path = dest_dir / file.name
            shutil.move(str(file), str(dest_path))
            results["移動済み"].append((file.name, category))
        else:
            results["未分類"].append(file.name)

    print("=" * 40)
    print("　　ファイル整理結果")
    print("=" * 40)

    if results["移動済み"]:
        print("\n【移動済みファイル】")
        current_category = None
        for filename, category in sorted(results["移動済み"], key=lambda x: x[1]):
            if category != current_category:
                print(f"\n  [{category}/]")
                current_category = category
            print(f"     -> {filename}")

    if results["未分類"]:
        print("\n【未分類ファイル（移動なし）】")
        for filename in results["未分類"]:
            print(f"  (未分類) {filename}")

    print("\n" + "=" * 40)
    print(f"合計: {len(results['移動済み'])} ファイル移動 / {len(results['未分類'])} ファイル未分類")
    print("=" * 40)


if __name__ == "__main__":
    print("【ステップ1】テストファイルを作成中...")
    create_test_files()

    print("【ステップ2】ファイルを整理中...\n")
    organize_files()

    print(f"\n整理後のフォルダ: {TEST_FOLDER}")
