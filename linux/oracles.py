"""Ground-truth oracles for the Chimera transpiler (--verify-fn)."""

def rule110_step(tape):
    """One zero-padded Rule 110 step. tape: list[int] -> list[int]"""
    n = len(tape)
    out = []
    for i in range(n):
        v = (tape[i - 1], tape[i], tape[i + 1] if i + 1 < n else 0)
        out.append({(1, 1, 1): 0, (1, 1, 0): 1, (1, 0, 1): 1, (1, 0, 0): 0,
                    (0, 1, 1): 1, (0, 1, 0): 1, (0, 0, 1): 1, (0, 0, 0): 0}[v])
    return out

TAG_RULES = {"a": ["d", "b", "d"], "b": ["a", "d"], "c": ["b", "d", "c", "c"], "d": ["a"]}

def tag_step(word):
    """One Post 2-tag step under the Act XII-A rules. word: list[str]"""
    if len(word) < 2:
        return word
    return word[2:] + TAG_RULES[word[0]]
