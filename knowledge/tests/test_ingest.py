import pytest

from knowledge.ingest import extract_text, split_chunks


@pytest.mark.unit
class TestSplitChunks:
    def test_empty_text_returns_empty_list(self):
        assert split_chunks("") == []
        assert split_chunks("   ") == []

    def test_short_text_returns_single_chunk(self):
        assert split_chunks("短い文章です。") == ["短い文章です。"]

    def test_large_single_paragraph_is_force_split(self):
        text = "あ" * 2000
        chunks = split_chunks(text, max_chars=800, overlap=200)
        assert len(chunks) >= 3
        assert all(len(c) <= 800 for c in chunks)

    def test_overlap_included_between_chunks(self):
        para1 = "あ" * 700
        para2 = "い" * 700
        text = f"{para1}\n\n{para2}"
        chunks = split_chunks(text, max_chars=800, overlap=200)
        assert len(chunks) == 2
        assert chunks[1].startswith("あ" * 200)


@pytest.mark.unit
class TestExtractText:
    def test_unsupported_extension_raises(self, tmp_path):
        path = tmp_path / "file.xyz"
        path.write_text("data")
        with pytest.raises(ValueError):
            extract_text(str(path))

    def test_txt_file_reads_content(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("こんにちは", encoding="utf-8")
        assert extract_text(str(path)) == "こんにちは"

    def test_md_file_reads_content(self, tmp_path):
        path = tmp_path / "file.md"
        path.write_text("# 見出し", encoding="utf-8")
        assert extract_text(str(path)) == "# 見出し"
