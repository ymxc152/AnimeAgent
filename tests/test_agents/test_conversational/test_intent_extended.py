"""Extended tests for intent parser — all action types and extractors."""

from anime_agent.agents.conversational.intent import (
    ParsedIntent,
    _extract_episode_number,
    _extract_selection,
    _extract_title,
    parse_intent,
)

# ── Subscribe intent ────────────────────────────────────────────────────


class TestSubscribeIntent:
    def test_subscribe_keyword(self):
        intent = parse_intent("葬送的芙莉莲订阅")
        assert intent.action == "subscribe"
        assert intent.title == "葬送的芙莉莲"

    def test_subscribe_keyword_prefix(self):
        intent = parse_intent("订阅 葬送的芙莉莲")
        assert intent.action == "subscribe"

    def test追番_keyword(self):
        intent = parse_intent("追番 葬送的芙莉莲")
        assert intent.action == "subscribe"

    def test_subscribe_english(self):
        intent = parse_intent("subscribe Frieren")
        assert intent.action == "subscribe"

    def test_帮我追_keyword(self):
        intent = parse_intent("帮我追 葬送的芙莉莲")
        assert intent.action == "subscribe"

    def test_我想看_keyword(self):
        intent = parse_intent("我想看 葬送的芙莉莲")
        assert intent.action == "subscribe"

    def test_想追_keyword(self):
        intent = parse_intent("想追 葬送的芙莉莲")
        assert intent.action == "subscribe"

    def test_帮我找_keyword(self):
        intent = parse_intent("帮我找 葬送的芙莉莲")
        assert intent.action == "subscribe"


# ── Retry intent ────────────────────────────────────────────────────────


class TestRetryIntent:
    def test_重试_keyword(self):
        intent = parse_intent("重试葬送的芙莉莲")
        assert intent.action == "retry_episode"

    def test_retry_english(self):
        intent = parse_intent("retry Frieren")
        assert intent.action == "retry_episode"

    def test_再试一次(self):
        intent = parse_intent("再试一次葬送的芙莉莲")
        assert intent.action == "retry_episode"

    def test_重新下载(self):
        intent = parse_intent("重新下载葬送的芙莉莲")
        assert intent.action == "retry_episode"

    def test_再下载(self):
        intent = parse_intent("再下载葬送的芙莉莲")
        assert intent.action == "retry_episode"

    def test_with_episode_number(self):
        intent = parse_intent("重试葬送的芙莉莲第5集")
        assert intent.action == "retry_episode"
        assert intent.episode_number == 5


# ── Help intent ─────────────────────────────────────────────────────────


class TestHelpIntent:
    def test_帮助(self):
        intent = parse_intent("帮助")
        assert intent.action == "help"

    def test_help_english(self):
        intent = parse_intent("help")
        assert intent.action == "help"

    def test_你能做什么(self):
        intent = parse_intent("你能做什么")
        assert intent.action == "help"

    def test_你会什么(self):
        intent = parse_intent("你会什么")
        assert intent.action == "help"

    def test_有什么功能(self):
        intent = parse_intent("有什么功能")
        assert intent.action == "help"

    def test_怎么用(self):
        intent = parse_intent("怎么用")
        assert intent.action == "help"


# ── Select intent ───────────────────────────────────────────────────────


class TestSelectIntent:
    def test_diyige(self):
        intent = parse_intent("第1个")
        assert intent.action == "select_candidate"
        assert intent.selection_index == 1

    def test_di2ge(self):
        intent = parse_intent("第2个")
        assert intent.action == "select_candidate"
        assert intent.selection_index == 2

    def test_第三个_with_spaces(self):
        intent = parse_intent("第 3 个")
        assert intent.action == "select_candidate"
        assert intent.selection_index == 3

    def test_bare_number(self):
        intent = parse_intent("2")
        assert intent.action == "select_candidate"
        assert intent.selection_index == 2

    def test_选3(self):
        intent = parse_intent("选 3")
        assert intent.action == "select_candidate"
        assert intent.selection_index == 3


# ── Query status intents ────────────────────────────────────────────────


class TestQueryStatusIntents:
    def test_pending_torrents(self):
        for kw in ["等种子", "还在等", "pending", "waiting", "没种子", "需要人工", "人工审核"]:
            intent = parse_intent(kw)
            assert intent.action == "query_status", f"Failed for keyword: {kw}"
            assert intent.query_type == "pending_torrents", f"Failed for keyword: {kw}"

    def test_failed_tasks(self):
        for kw in ["失败", "failed", "报错", "出错"]:
            intent = parse_intent(kw)
            assert intent.action == "query_status", f"Failed for keyword: {kw}"
            assert intent.query_type == "failed_tasks", f"Failed for keyword: {kw}"

    def test_subscription_detail(self):
        for kw in ["下完了吗", "下载完了吗", "进度", "progress", "status"]:
            intent = parse_intent(kw)
            assert intent.action == "query_status", f"Failed for keyword: {kw}"
            assert intent.query_type == "subscription_detail", f"Failed for keyword: {kw}"

    def test_anime_info(self):
        for kw in ["多少集", "有几集", "total", "episodes", "信息", "info"]:
            intent = parse_intent(kw)
            assert intent.action == "query_status", f"Failed for keyword: {kw}"
            assert intent.query_type == "anime_info", f"Failed for keyword: {kw}"

    def test_list_active(self):
        for kw in ["我在下载哪些", "我在追哪些", "有哪些番", "追了哪些", "list", "active"]:
            intent = parse_intent(kw)
            assert intent.action == "query_status", f"Failed for keyword: {kw}"
            assert intent.query_type == "list_active", f"Failed for keyword: {kw}"


# ── Unknown intent ──────────────────────────────────────────────────────


class TestUnknownIntent:
    def test_random_text(self):
        intent = parse_intent("今天天气怎么样")
        assert intent.action == "unknown"

    def test_empty_string(self):
        intent = parse_intent("")
        assert intent.action == "unknown"


# ── _extract_selection ──────────────────────────────────────────────────


class TestExtractSelection:
    def test_diyige(self):
        assert _extract_selection("第1个") == 1
        assert _extract_selection("第2个") == 2
        assert _extract_selection("第 3 个") == 3

    def test_bare_number(self):
        assert _extract_selection("1") == 1
        assert _extract_selection("5") == 5

    def test_xuan_n(self):
        assert _extract_selection("选 3") == 3

    def test_returns_none_for_no_match(self):
        assert _extract_selection("hello") is None
        assert _extract_selection("第一个番") is None


# ── _extract_episode_number ─────────────────────────────────────────────


class TestExtractEpisodeNumber:
    def test_第n集(self):
        assert _extract_episode_number("第5集") == 5
        assert _extract_episode_number("第 12 集") == 12

    def test_ep_n(self):
        assert _extract_episode_number("ep 3") == 3
        assert _extract_episode_number("EP5") == 5

    def test_episode_n(self):
        assert _extract_episode_number("episode 7") == 7

    def test_returns_none_for_no_match(self):
        assert _extract_episode_number("hello") is None


# ── _extract_title ──────────────────────────────────────────────────────


class TestExtractTitle:
    def test_quoted_title(self):
        assert _extract_title("订阅《葬送的芙莉莲》") == "葬送的芙莉莲"
        assert _extract_title('订阅"Frieren"') == "Frieren"

    def test_suffix_removal(self):
        assert _extract_title("葬送的芙莉莲订阅") == "葬送的芙莉莲"
        assert _extract_title("葬送的芙莉莲重试") == "葬送的芙莉莲"

    def test_returns_none_for_empty(self):
        assert _extract_title("订阅") is None


# ── ParsedIntent.to_dict ────────────────────────────────────────────────


class TestParsedIntent:
    def test_to_dict(self):
        intent = ParsedIntent("subscribe", title="Frieren")
        d = intent.to_dict()
        assert d["action"] == "subscribe"
        assert d["title"] == "Frieren"
        assert d["query_type"] is None
        assert d["episode_number"] is None
