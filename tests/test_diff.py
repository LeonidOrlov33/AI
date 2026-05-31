from autocoder_agent.core.diff import apply_diff_blocks, parse_diff_blocks


def test_parse_and_apply_diff_block():
    text = """<<<<<<< ORIGINAL
old = 1
=======
old = 2
>>>>>>> FIXED"""
    blocks = parse_diff_blocks(text)
    assert len(blocks) == 1
    assert apply_diff_blocks("old = 1\nprint(old)\n", blocks) == "old = 2\nprint(old)\n"
