#!/usr/bin/env python3
"""Test that the CSV data loads correctly"""

import csv
from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "alignment-forum-posts.csv"

def test_csv():
    print("=" * 70)
    print("TESTING REAL CSV DATA")
    print("=" * 70)
    print()

    posts = []
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        posts = list(reader)

    print(f"✅ Loaded {len(posts)} posts from CSV")
    print(f"   File: {CSV_PATH}")
    print(f"   Size: {CSV_PATH.stat().st_size / 1024:.1f} KB")
    print()

    # Check fields
    if posts:
        print("CSV Fields:")
        for field in posts[0].keys():
            print(f"  - {field}")
        print()

    # Show top 10 by karma
    print("Top 10 posts by karma:")
    sorted_posts = sorted(posts, key=lambda p: int(p.get("karma", 0)), reverse=True)
    for i, post in enumerate(sorted_posts[:10], 1):
        print(f"{i:2d}. [{post['karma']:>4s} karma] {post['title'][:55]}")
        print(f"     Author: {post['author']}, Comments: {post['commentsCount']}")
        print(f"     {post['pageUrl']}")
        print()

    # Check for alignment keywords
    alignment_keywords = ["alignment", "ai safety", "interpretability", "mesa", "reward hacking"]
    keyword_counts = {kw: 0 for kw in alignment_keywords}

    for post in posts:
        text = f"{post['title']} {post['summary']}".lower()
        for kw in alignment_keywords:
            if kw in text:
                keyword_counts[kw] += 1

    print("\nAlignment keyword frequency:")
    for kw, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {kw:20s}: {count:3d} posts ({count/len(posts)*100:.1f}%)")

    print()
    print("=" * 70)
    print("✅ CSV DATA IS VALID AND READY!")
    print("=" * 70)

if __name__ == "__main__":
    test_csv()
