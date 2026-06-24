#!/usr/bin/env python3
"""
AI Trend Tracker — Daily News Fetcher
Fetches latest AI news from RSS feeds and Hacker News API.
Run daily (or manually) to update articles_data.js for the dashboard.

Usage: python3 fetch_ai_news.py
"""

import json
import sys
import os
import hashlib
import subprocess
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Auto-install dependencies ───────────────────────────────────────────────

def pip_install(package):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", package, "--break-system-packages", "-q"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

try:
    import feedparser
except ImportError:
    print("📦 Installing feedparser...")
    pip_install("feedparser")
    import feedparser

try:
    import requests
except ImportError:
    print("📦 Installing requests...")
    pip_install("requests")
    import requests

# ─── Configuration ───────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
OUTPUT_FILE = SCRIPT_DIR / "articles_data.js"
RETENTION_DAYS = 7          # Keep articles for 7 days
MAX_PER_FEED = 12           # Max articles per RSS feed
HN_SCAN = 80                # How many HN top stories to scan
HN_MAX = 12                 # Max HN articles to keep
REQUEST_TIMEOUT = 15        # HTTP timeout in seconds

RSS_FEEDS = [
    # ── Company / Lab Blogs (verified working) ──────────────────────────────
    {"url": "https://openai.com/news/rss.xml",                              "source": "OpenAI",          "type": "company"},
    {"url": "https://blog.google/technology/ai/rss/",                       "source": "Google AI",       "type": "company"},
    {"url": "https://deepmind.google/blog/rss.xml",                         "source": "Google DeepMind", "type": "company"},
    {"url": "https://engineering.fb.com/feed/",                             "source": "Meta AI",         "type": "company"},
    {"url": "https://aws.amazon.com/blogs/machine-learning/feed/",          "source": "AWS ML",          "type": "company"},
    {"url": "https://huggingface.co/blog/feed.xml",                         "source": "Hugging Face",    "type": "company"},
    # ── Google News feeds (for labs without public RSS) ──────────────────────
    {"url": "https://news.google.com/rss/search?q=anthropic+claude&hl=en-US&gl=US&ceid=US:en",  "source": "Anthropic",   "type": "company"},
    {"url": "https://news.google.com/rss/search?q=xAI+grok+llm&hl=en-US&gl=US&ceid=US:en",     "source": "xAI / Grok",  "type": "company"},
    {"url": "https://news.google.com/rss/search?q=deepseek+ai+model&hl=en-US&gl=US&ceid=US:en", "source": "DeepSeek",    "type": "company"},
    {"url": "https://news.google.com/rss/search?q=mistral+ai+model&hl=en-US&gl=US&ceid=US:en",  "source": "Mistral AI",  "type": "company"},
    {"url": "https://news.google.com/rss/search?q=google+gemini+AI&hl=en-US&gl=US&ceid=US:en",  "source": "Gemini News", "type": "company"},
    {"url": "https://news.google.com/rss/search?q=openai+chatgpt&hl=en-US&gl=US&ceid=US:en",    "source": "ChatGPT News","type": "company"},
    # ── Tech News ───────────────────────────────────────────────────────────
    {"url": "https://techcrunch.com/category/artificial-intelligence/feed/","source": "TechCrunch",      "type": "news"},
    {"url": "https://venturebeat.com/category/ai/feed/",                    "source": "VentureBeat",     "type": "news"},
    {"url": "https://www.theverge.com/rss/index.xml",                       "source": "The Verge",       "type": "news"},
    {"url": "https://www.wired.com/feed/tag/ai/latest/rss",                 "source": "Wired",           "type": "news"},
    {"url": "https://feeds.arstechnica.com/arstechnica/technology-lab",     "source": "Ars Technica",    "type": "news"},
    {"url": "https://www.technologyreview.com/feed/",                       "source": "MIT Tech Review", "type": "news"},
]

SOURCE_COLORS = {
    "OpenAI":           "#10a37f",
    "Anthropic":        "#d4845a",
    "Google AI":        "#4285f4",
    "Google DeepMind":  "#4285f4",
    "Meta AI":          "#0081fb",
    "Microsoft AI":     "#00a4ef",
    "NVIDIA":           "#76b900",
    "AWS ML":           "#ff9900",
    "Hugging Face":     "#e9a800",
    "Apple Research":   "#555555",
    "xAI / Grok":       "#1a1a1a",
    "DeepSeek":         "#4f46e5",
    "Mistral AI":       "#f97316",
    "Gemini News":      "#4285f4",
    "ChatGPT News":     "#10a37f",
    "Cohere":           "#0ea5e9",
    "Perplexity":       "#20b2aa",
    "TechCrunch":       "#0d9488",
    "VentureBeat":      "#7c3aed",
    "The Verge":        "#e11d48",
    "Wired":            "#6b7280",
    "Ars Technica":     "#ff6600",
    "MIT Tech Review":  "#b91c1c",
    "Hacker News":      "#ff6600",
}

CATEGORIES = {
    "Models & Research": [
        # model families
        "gpt", "chatgpt", "llm", "model", "training", "benchmark",
        "gemini", "gemma", "claude", "fable", "mythos", "opus", "sonnet", "haiku",
        "mistral", "mixtral", "codestral",
        "llama", "llama 3", "llama 4",
        "deepseek", "deepseek-r", "deepseek-v",
        "grok", "grok-", "xai",
        "phi-", "phi 4", "copilot",
        "perplexity", "sonar",
        "diffusion", "transformer", "parameter", "fine-tun", "pretrain",
        "multimodal", "vision model", "language model", "reasoning model", "foundation model",
        "o1", "o3", "o4", "sora", "dall-e", "stable diffusion", "midjourney",
        "agentic", "agent framework", "computer use",
    ],
    "Big Tech News": [
        "openai announces", "openai launches", "openai releases",
        "google announces", "google launches",
        "microsoft launches", "microsoft releases",
        "meta releases", "meta launches",
        "nvidia unveils", "nvidia launches",
        "apple introduces", "apple launches",
        "amazon launches", "amazon releases",
        "anthropic releases", "anthropic launches", "anthropic announces",
        "deepseek releases", "deepseek launches",
        "xai releases", "xai launches",
        "mistral releases", "mistral launches",
        "google deepmind",
        "sam altman", "sundar pichai", "satya nadella",
        "mark zuckerberg", "jensen huang", "dario amodei",
    ],
    "Real-world AI Use": [
        "deploy", "production", "enterprise", "healthcare", "hospital", "clinic",
        "finance", "banking", "customer service", "automat", "workflow", "manufacturing",
        "retail", "supply chain", "drug discovery", "climate", "education", "legal",
        "agriculture", "logistics", "real estate", "insurance", "used in", "powered by ai",
        "ai-powered", "in the wild",
    ],
    "Tools & Stack": [
        " api", "sdk", "framework", "library", " tool", "plugin", "integration",
        "developer", "open source", "open-source", "inference", "platform",
        "infrastructure", "langchain", "llamaindex", "rag", "vector db", "embedding",
        "mlops", "dataset", "fine-tune", "quantiz",
    ],
    "Funding & Business": [
        "funding", "raises", "investment", "billion", "million", "acquisition",
        "ipo", "startup", "valuation", "series a", "series b", "series c",
        "venture capital", "backed by", "valued at",
    ],
    "Policy & Safety": [
        "regulation", "safety", "alignment", "ethics", "policy", "law", "ban",
        "eu ai act", "copyright", "govern", "risk", "bias", "responsible ai",
        "deepfake", "misinformation", "congress", "senate", "white house", "eu",
    ],
}

HN_AI_KEYWORDS = [
    "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "machine learning", "neural network", "chatgpt", "deepmind", "nvidia",
    "artificial intelligence", "stable diffusion", "mistral", "llama",
    "robotics", "language model", "deep learning", "agi", "transformer",
    "hugging face", "midjourney", "sora", "copilot",
    # additional agents & labs
    "deepseek", "grok", "xai", "x.ai", "perplexity",
    "mistral", "mixtral", "cohere",
    "fable", "opus", "sonnet", "claude 4",
    "gemma", "phi-", "qwen",
    "agentic", "agent", "mcp", "computer use",
    "o3", "o4", "reasoning model",
]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]

def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 280:
        text = text[:277] + "..."
    return text

def categorize(title: str, summary: str = "") -> str:
    text = (title + " " + (summary or "")).lower()
    for category, keywords in CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return category
    return "Big Tech News"

def parse_date(entry) -> str:
    for attr in ('published_parsed', 'updated_parsed'):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()

def load_existing() -> dict:
    """Load existing articles from articles_data.js, indexed by id."""
    if not OUTPUT_FILE.exists():
        return {}
    try:
        content = OUTPUT_FILE.read_text(encoding="utf-8")
        match = re.search(r'const ARTICLES_DATA\s*=\s*(\{.*\});', content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            return {a["id"]: a for a in data.get("articles", [])}
    except Exception:
        pass
    return {}

# ─── Fetchers ────────────────────────────────────────────────────────────────

def fetch_rss(feed_cfg: dict) -> list:
    articles = []
    try:
        resp = requests.get(
            feed_cfg["url"], timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AITrendTracker/1.0)"}
        )
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:MAX_PER_FEED]:
            url = entry.get("link", "").strip()
            if not url:
                continue
            title = clean_html(entry.get("title", ""))
            summary = clean_html(
                entry.get("summary", entry.get("description", entry.get("content", [{}])[0].get("value", "")))
            )
            articles.append({
                "id":          make_id(url),
                "title":       title,
                "url":         url,
                "source":      feed_cfg["source"],
                "source_type": feed_cfg["type"],
                "published":   parse_date(entry),
                "summary":     summary,
                "category":    categorize(title, summary),
                "color":       SOURCE_COLORS.get(feed_cfg["source"], "#6b7280"),
            })
    except Exception as e:
        print(f"     ✗ {feed_cfg['source']}: {e}")
    return articles

def fetch_hackernews() -> list:
    articles = []
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=REQUEST_TIMEOUT
        )
        story_ids = resp.json()[:HN_SCAN]
        for sid in story_ids:
            if len(articles) >= HN_MAX:
                break
            try:
                sr = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=8
                )
                story = sr.json()
                if not story or story.get("type") != "story":
                    continue
                title = story.get("title", "")
                if not any(kw in title.lower() for kw in HN_AI_KEYWORDS):
                    continue
                url = story.get("url") or f"https://news.ycombinator.com/item?id={sid}"
                score = story.get("score", 0)
                published = datetime.fromtimestamp(
                    story.get("time", 0), tz=timezone.utc
                ).isoformat()
                articles.append({
                    "id":          make_id(url),
                    "title":       title,
                    "url":         url,
                    "source":      "Hacker News",
                    "source_type": "community",
                    "published":   published,
                    "summary":     f"⬆ {score} points · {story.get('descendants', 0)} comments on Hacker News",
                    "category":    categorize(title),
                    "color":       SOURCE_COLORS["Hacker News"],
                })
            except Exception:
                pass
    except Exception as e:
        print(f"     ✗ Hacker News: {e}")
    return articles

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n🤖 AI Trend Tracker — fetching news ({now_str})")
    print("─" * 52)

    existing = load_existing()
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)

    all_articles: dict = {}

    # RSS feeds
    print("\n📡 RSS feeds:")
    for feed in RSS_FEEDS:
        label = f"  {feed['source']}"
        print(f"{label:<28}", end="", flush=True)
        items = fetch_rss(feed)
        for a in items:
            all_articles[a["id"]] = a
        print(f"  {len(items)} articles")

    # Hacker News
    print("\n🔥 Hacker News (top AI stories):", end="", flush=True)
    hn_items = fetch_hackernews()
    for a in hn_items:
        all_articles[a["id"]] = a
    print(f"  {len(hn_items)} articles")

    # Merge with retained existing articles
    retained = 0
    for art_id, art in existing.items():
        if art_id in all_articles:
            continue
        try:
            pub = datetime.fromisoformat(art["published"].replace("Z", "+00:00"))
            if pub > cutoff:
                all_articles[art_id] = art
                retained += 1
        except Exception:
            pass
    if retained:
        print(f"\n♻️  Retained {retained} articles from previous fetch (within {RETENTION_DAYS} days)")

    # Sort newest first
    articles = sorted(all_articles.values(), key=lambda x: x.get("published", ""), reverse=True)

    data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total":        len(articles),
        "articles":     articles,
    }

    js = (
        f"// AI Trend Tracker — auto-generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"// DO NOT edit manually — re-run fetch_ai_news.py to refresh\n"
        f"const ARTICLES_DATA = {json.dumps(data, indent=2, ensure_ascii=False)};\n"
    )
    OUTPUT_FILE.write_text(js, encoding="utf-8")

    print(f"\n✅ {len(articles)} articles saved → articles_data.js")
    print(f"   Open index.html in your browser to view the dashboard.\n")

if __name__ == "__main__":
    main()
