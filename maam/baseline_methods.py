"""Two deterministic source-pattern candidates; Lean still decides correctness."""
import re

from .corpus import CorpusError
from .theory import digest


METHODS = {
    "simpa_local_hypothesis":
        "Replace the first supported have/rw-at/exact block with simpa only using its expression; "
        "keep all other proof text and the existing imports, definitions and goal unchanged.",
    "simpa_rewrite_exact":
        "Replace the first supported reverse-rw/exact block with simpa only using its value; "
        "keep all other proof text and the existing imports, definitions and goal unchanged.",
}

_PATTERNS = {
    "simpa_local_hypothesis": (re.compile(
        r"^(?P<indent> *)have (?P<name>[A-Za-z_][A-Za-z0-9_']*) := (?P<expression>[^\r\n]+)\r?\n"
        r"(?P=indent)rw \[(?P<rules>[^\[\]\r\n]+)\] at (?P=name) *\r?\n"
        r"(?P=indent)exact (?P=name) *(?P<ending>\r?\n|$)", re.MULTILINE), 3),
    "simpa_rewrite_exact": (re.compile(
        r"^(?P<indent> *)rw \[← (?P<expression>[^\[\]\r\n]+)\] *\r?\n"
        r"(?P=indent)exact (?P<value>[^\r\n]+)(?P<ending>\r?\n|$)", re.MULTILINE), 2),
}


def _single_line(text, *, single_rule=False):
    if not text.strip() or any(token in text for token in ('--', '/-', '-/', ';', '"')):
        return False
    stack = []
    pairs = {')': '(', ']': '[', '}': '{', '⟩': '⟨'}
    for char in text:
        if char in '([{⟨':
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
        elif single_rule and char == ',' and not stack:
            return False
    return not stack


def generate(request):
    """Return one controller response and reproducible, non-verification evidence."""
    if (not isinstance(request, dict) or not isinstance(request.get('method'), dict)
            or not isinstance(request.get('incumbent'), dict)
            or not isinstance(request['incumbent'].get('proof'), str)
            or not request['incumbent']['proof'].strip()
            or not isinstance(request.get('request_sha256'), str)
            or not re.fullmatch(r'[0-9a-f]{64}', request['request_sha256'])):
        raise CorpusError('invalid deterministic baseline request')
    method = request['method'].get('name')
    if not isinstance(method, str) or method not in METHODS:
        raise CorpusError('unsupported deterministic baseline method')
    before = request['incumbent']['proof']
    after, span = before, None
    pattern, line_count = _PATTERNS[method]
    # shortcut: scan only comment-free physical lines; use a Lean parser for broader rewrites.
    if not any(token in before for token in ('--', '/-', '-/', '"')):
        for match in pattern.finditer(before):
            expression = match['expression'].strip()
            rules = (match['rules'].strip() if method == 'simpa_local_hypothesis'
                     else expression)
            value = (expression if method == 'simpa_local_hypothesis'
                     else match['value'].strip())
            if (not _single_line(expression, single_rule=method == 'simpa_rewrite_exact')
                    or not _single_line(rules) or not _single_line(value)):
                continue
            replacement = (match['indent'] + 'simpa only [' + rules + '] using (' + value + ')'
                           + match['ending'])
            after = before[:match.start()] + replacement + before[match.end():]
            first = before.count('\n', 0, match.start()) + 1
            span = [first, first + line_count - 1]
            break
    if span is None:
        response = {'action': 'retain', 'request_sha256': request['request_sha256'],
            'reason': method + ' scanner found no matching supported source pattern; '
                      'this is not evidence of search exhaustion.'}
    else:
        response = {'action': 'candidate', 'request_sha256': request['request_sha256'],
            'proof': after, 'bridge': 'Deterministic ' + method + ' source-pattern candidate; '
                                    'Lean must check correctness before any strict-shorter replacement.'}
    evidence = {'schema_version': 1, 'method': method, 'matched': span is not None,
        'line_span': span, 'before_proof_sha256': digest(before.encode()),
        'after_proof_sha256': digest(after.encode()), 'before_proof_bytes': len(before.encode()),
        'after_proof_bytes': len(after.encode()),
        'source_size_note': 'UTF-8 proof text bytes only; not verified validity or the charged '
                            'full-proof-module source-token metric.'}
    return response, evidence
