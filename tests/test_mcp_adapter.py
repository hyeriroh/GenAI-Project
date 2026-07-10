from english_news_agent.mcp_adapter import _filename_and_folder, _parse_search_paths


def test_filename_and_folder_splits_vault_relative_paths():
    assert _filename_and_folder("40 Resources/English News/Test/a.md") == (
        "a.md",
        "40 Resources/English News/Test",
    )
    assert _filename_and_folder("root.md") == ("root.md", "")


def test_parse_search_paths_extracts_markdown_paths():
    text = """Search results:
file: 40 Resources/English News/a.md
- Filename match: 40 Resources/English News/Test/old-test.md
"""

    assert set(_parse_search_paths(text)) == {
        "40 Resources/English News/Test/old-test.md",
        "40 Resources/English News/a.md",
    }
