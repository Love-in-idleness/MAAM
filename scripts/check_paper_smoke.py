#!/usr/bin/env python3
import json
from pathlib import Path
import sys

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
nodes = {r['name']:r for r in rows if r['record']=='node'}
assert nodes['Demo.andRight']['source']['status'] == 'named_source', nodes['Demo.andRight']
assert nodes['Demo.andRight']['source']['tokens'] > 0
assert sum(nodes['Demo.andRight']['signature'].values()) == 3
assert sum(nodes['Demo.andRight']['body'].values()) == 4
for row in nodes.values():
    for dep in set(row.get('signature',{})) | set(row.get('body') or {}):
        assert dep in nodes, dep
print('Streaming export, closed references, and named source-token coverage checked.')
