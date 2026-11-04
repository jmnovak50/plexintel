#!/usr/bin/env python3
"""Read-only verification of documented migration commands against the real CLI."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import shlex
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.embeddinggemma2_migration import argument_parser


def check(path=ROOT/'docs/embeddinggemma2-multimodal-migration.md'):
    operations=[];gates=set();commands=[]
    for block in re.findall(r'```bash\n(.*?)```',Path(path).read_text(),re.S):
        for line in block.replace('\\\n',' ').splitlines():
            tokens=shlex.split(line,comments=True)
            indices=[i for i,token in enumerate(tokens) if token.endswith('scripts/embeddinggemma2_migration.py')]
            if not indices:continue
            arguments=tokens[indices[0]+1:]
            arguments=[re.sub(r'\$\{?MISSING_ART_LIMIT\}?','0',token) for token in arguments]
            with redirect_stdout(io.StringIO()):
                try:namespace=argument_parser().parse_args(arguments)
                except SystemExit as exc:
                    if exc.code==0 and arguments==['--help']:commands.append(line);continue
                    raise ValueError('Invalid documented CLI command: '+line) from exc
            operations.append(namespace.operation);commands.append(line)
            if namespace.operation not in {'preflight','coverage','status','inspect','export','verify','smoke','daily','active'} and not namespace.approved_production_change:
                raise ValueError('Documented mutation omits operator authorization: '+line)
            if namespace.operation=='review':
                if not namespace.gate or not namespace.reason:raise ValueError('Review requires gate/reason')
                if namespace.gate=='quality' and not namespace.quality_go:raise ValueError('Quality review lacks explicit GO')
                gates.add(namespace.gate)
            if namespace.operation=='recover-metadata' and not namespace.reason:
                raise ValueError('Historical metadata recovery requires an explicit source-policy reason')
            if namespace.num_thread is not None and namespace.operation!='media-poster':
                raise ValueError('Thread overrides are restricted to poster inference')
    required={'preflight','coverage','install','create','metadata','posters','media-text','media-poster','watch','users',
        'benchmark-threads','recover-metadata','refresh-source','train','score','validate','promote','verify','rollback','recover-transition','status','inspect','export'}
    if required-set(operations):raise ValueError('Runbook lacks stages: '+str(sorted(required-set(operations))))
    if gates!={'text','poster','profiles','quality'}:raise ValueError('Runbook lacks required human review gates')
    if 'media' in operations:raise ValueError('Combined media operation must not be documented')
    return dict(commands_checked=len(commands),operations=sorted(set(operations)),review_gates=sorted(gates),valid=True,
        method='Actual argparse parsing; no documented migration commands executed')


if __name__=='__main__':print(json.dumps(check(),indent=2))
