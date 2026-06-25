from src.web_app import CRAWLER_ROBOTS_TXT, NOINDEX_HEADER_VALUE, is_blocked_crawler_user_agent


def test_robots_txt_disallows_all_crawlers():
    assert "User-agent: *" in CRAWLER_ROBOTS_TXT
    assert "Disallow: /" in CRAWLER_ROBOTS_TXT
    assert "GPTBot" in CRAWLER_ROBOTS_TXT
    assert "ClaudeBot" in CRAWLER_ROBOTS_TXT


def test_noindex_header_blocks_indexing_and_snippets():
    assert "noindex" in NOINDEX_HEADER_VALUE
    assert "nofollow" in NOINDEX_HEADER_VALUE
    assert "nosnippet" in NOINDEX_HEADER_VALUE


def test_known_ai_and_search_user_agents_are_blocked():
    assert is_blocked_crawler_user_agent("Mozilla/5.0 Applebot/0.1")
    assert is_blocked_crawler_user_agent("GPTBot/1.2")
    assert is_blocked_crawler_user_agent("ClaudeBot")
    assert is_blocked_crawler_user_agent("PerplexityBot/1.0")


def test_normal_browser_user_agent_is_not_blocked():
    assert not is_blocked_crawler_user_agent(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"
    )
