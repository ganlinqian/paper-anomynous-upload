"""R1: contract-family coverage of tool calls in public agent trajectories.  Exploratory, descriptive,
rule-based (no model labels); rules below are fixed in this file, the version tag is written into the output.
Datasets (HuggingFace, parquet conversion): nebius/SWE-agent-trajectories shard 0000 (SWE-agent, Llama 8B/70B/405B),
SWE-Gym/OpenHands-SFT-Trajectories train.success.oss (OpenHands CodeAct).  Sample: 200 trajectories per dataset,
seed 2026111501 (SWE-agent: one random trajectory per instance, then 200 instances); full sets as sensitivity.
Classes per tool call (compound commands take the highest-precedence class of their segments):
  ORDER    explicit verify-then-act / build-then-test chains        -> order contract (phase order)
  NET      downloads / package installs / remote VCS                -> needs a declared-activity contract (C33: alarms)
  PRESENCE runs tests, builds, scripts, linters, interpreters       -> 'required phase occurred' (anti-skip only, A3)
  OTHER    anything the rules do not recognise                      -> not expressible
  WAIT     sleep / wait / poll                                      -> E=0 contract, current detector applies
  LIGHT    read / search / list / navigate / edit files, local VCS  -> E=0 with a small declared allowance
Each assistant turn is also one model-wait window (host should be idle while the model generates) -> counted separately.
Usage: python -I r1_coverage.py <data_dir> <out_dir> [v2]
v2 (added after reading v1's unrecognised-token list; v1 output kept): (a) INVALID = actions the shell rejects without
doing work (known command glued to a dot such as 'cd..', 'find.'; source code pasted as the action) -> excluded from the
denominator and counted; (b) shell control keywords (if/then/for/do/done...) are stripped; (c) programs invoked by path
or not in any lexicon -> PRES_UNLISTED (runs a program; phase-type), so OTHER keeps only unparseable remainders."""
import collections, csv, json, pathlib, random, re, sys
import numpy as np, pyarrow.parquet as pq
V2 = len(sys.argv) > 3 and sys.argv[3] == 'v2'
VERSION = 'r1-rules-v2' if V2 else 'r1-rules-v1'; SEED = 2026111501; NSAMP = 200; NBOOT = 2000
PREC = ['ORDER', 'NET', 'PRESENCE', 'PRES_UNLISTED', 'OTHER', 'WAIT', 'LIGHT', 'INVALID'] if V2 else ['ORDER', 'NET', 'PRESENCE', 'OTHER', 'WAIT', 'LIGHT']
CTRL = set('if then else elif fi while until do done esac { } ( )'.split())
PYKW = set('from import def class return print( if elif else for while try except with @ #'.split())
TYPO = re.compile(r'(cd|ls|find|mkdir|open|rm|cat|grep|touch|python|pip)\.\S*')
LIGHT = set('ls cat head tail grep egrep fgrep rg ag find cd pwd echo printf wc sed awk sort uniq diff tree which whereis '
            'file stat cp mv rm mkdir rmdir touch chmod chown ln nl less more true false export env set unset source . cut '
            'tr xargs basename dirname realpath readlink type command history clear test [ [[ du df id whoami date hostname '
            'uname ps kill pkill pgrep lsof jq patch vim vi nano'.split())
PRES = set('pytest py.test tox nox make cmake ctest gcc g++ cc clang c++ javac java mvn gradle node tsc mypy flake8 pylint '
           'black ruff isort coverage sphinx-build bash sh zsh pre-commit pyright yapf autopep8 cython rustc ipython'.split())
NETW = set('curl wget apt apt-get yum dnf brew ssh scp rsync'.split())
SWE_SPECIAL = set('open goto scroll_down scroll_up create edit search_dir search_file find_file'.split())
ORDER_RX = [re.compile(r'(sha\d*sum|md5sum|shasum|gpg\s+--verify|cosign\s+verify|openssl\s+dgst)[^\n]*?(&&|;|\n)[\s\S]*?\b(tar|unzip|gunzip|dpkg|rpm|install|bash|sh|python[\d.]*\s+setup\.py)\b'),
            re.compile(r'git\s+apply\s+--check[\s\S]*?(&&|;|\n)\s*git\s+apply'),
            re.compile(r'\bpatch\b[^\n]*--dry-run[\s\S]*?(&&|;|\n)\s*patch\b'),
            re.compile(r'\b(make(?!\s+test)|cmake\s+--build|pip[\d.]*\s+install\s+(-e\s+)?\.|python[\d.]*\s+setup\.py\s+(build|develop|install))[^;&|\n]*&&[\s\S]*?\b(pytest|py\.test|make\s+test|ctest|tox|python[\d.]*\s+-m\s+(pytest|unittest)|npm\s+test)\b')]
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n[\s\S]*?\n\s*\1\b")
WRAP = {'timeout', 'sudo', 'time', 'nohup', 'env', 'nice', 'stdbuf', 'xvfb-run', 'exec', 'command'}
unknown = collections.Counter()


def first_tokens(seg):
    t = seg.strip().lstrip('({!').split()
    while t:
        x = t[0]
        if re.fullmatch(r'\w+=\S*', x) or x in ('-n', '-k', '-s') or re.fullmatch(r'-?[\d.]+[smh]?', x) or x.startswith('--') and t and x != t[-1]:
            t = t[1:]; continue
        if x in WRAP and len(t) > 1:
            t = t[1:]; continue
        break
    return t


def seg_class(seg):
    t = first_tokens(seg)
    if V2:
        while t and t[0] in CTRL:
            t = t[1:]
        if t and t[0] in ('for', 'case', 'function', 'select'):
            return None
    if not t:
        return None
    c = t[0].strip('()'); a = t[1:]; a1 = a[0] if a else ''
    if V2 and (TYPO.fullmatch(c) or c.startswith('#')):
        return 'INVALID'
    if c in ('sleep', 'wait', 'watch') or (c == 'tail' and '-f' in a):
        return 'WAIT'
    if re.fullmatch(r'(python|pip)[\d.]*', c) and len(a) >= 2 and a[0] == '-m' and a[1] == 'pip':
        c, a = 'pip', a[2:]; a1 = a[0] if a else ''
    if re.fullmatch(r'pip[\d.]*|uv', c):
        if a1 in ('install', 'download', 'wheel', 'sync', 'add'):
            return 'PRESENCE' if ('-e' in a or '.' in a or '--editable' in a) and '-r' not in a else 'NET'
        return 'LIGHT'
    if c in ('conda', 'mamba'):
        return 'NET' if a1 in ('install', 'create', 'update', 'env') else 'LIGHT'
    if c in ('npm', 'yarn', 'pnpm'):
        return 'NET' if a1 in ('install', 'i', 'ci', 'add', 'update') or not a1 else 'PRESENCE'
    if c in ('cargo', 'go'):
        return 'NET' if a1 in ('install', 'fetch', 'get', 'mod') else 'PRESENCE'
    if c == 'git':
        return 'NET' if a1 in ('clone', 'fetch', 'pull', 'push', 'submodule', 'ls-remote') else 'LIGHT'
    if re.fullmatch(r'python[\d.]*m?', c) or c in PRES or c.startswith('./') or c.endswith('.sh') or c.endswith('.py'):
        return 'PRESENCE'
    if c in NETW:
        return 'NET'
    if c in LIGHT or c in SWE_SPECIAL:
        return 'LIGHT'
    unknown[c[:30]] += 1
    if V2 and (c.startswith('/') or c.startswith('~/') or re.fullmatch(r'[A-Za-z][\w.+-]*', c)):
        return 'PRES_UNLISTED'
    return 'OTHER'


def bash_class(cmd):
    if not cmd.strip():
        return 'WAIT'                                   # OpenHands: empty command polls a running process
    if cmd.strip() in ('ctrl+c', 'C-c'):
        return 'LIGHT'
    if any(r.search(cmd) for r in ORDER_RX):
        return 'ORDER'
    s = HEREDOC.sub('<<H', cmd)
    s = re.sub(r'"(?:\\.|[^"\\])*"', 'Q', s); s = re.sub(r"'[^']*'", 'Q', s)
    s = re.sub(r'\d*>&\d+|&>', ' ', s)
    cl = [seg_class(x) for x in re.split(r'\|\||&&|;|\||\n|&', s)]
    cl = [x for x in cl if x]
    return min(cl, key=PREC.index) if cl else 'LIGHT'


def swe_agent_calls(traj):
    out = []; turns = 0
    for m in traj:
        if m['role'] != 'ai':
            continue
        turns += 1
        b = re.findall(r'```[^\n]*\n([\s\S]*?)```', m['text'] or '')
        if not b:
            out.append(('NOACT', '')); continue
        act = b[-1].strip(); head = act.split(None, 1)[0] if act else ''
        if head == 'submit':
            out.append(('TERMINAL', act[:80]))
        elif V2 and (head in PYKW or head.startswith('#') or head.startswith('print(')):
            out.append(('INVALID', act[:80]))
        elif head in SWE_SPECIAL:
            out.append(('LIGHT', act[:80]))
        else:
            out.append((bash_class(act), act[:160]))
    return turns, out


def openhands_calls(msgs):
    out = []; turns = 0
    for m in msgs:
        if m['role'] != 'assistant':
            continue
        turns += 1
        f = re.findall(r'<function=([\w\-]+)>([\s\S]*?)</function>', m['content'] or '')
        if not f:
            out.append(('NOACT', '')); continue
        name, body = f[-1]; p = dict(re.findall(r'<parameter=(\w+)>\n?([\s\S]*?)\n?</parameter>', body))
        if name == 'finish':
            out.append(('TERMINAL', ''))
        elif name == 'execute_bash':
            c = p.get('command', ''); out.append((bash_class(c), c[:160]))
        elif name == 'str_replace_editor':
            out.append(('LIGHT', 'editor ' + p.get('command', '') + ' ' + p.get('path', '')[:80]))
        elif name == 'execute_ipython_cell':
            out.append(('PRESENCE', 'ipython ' + p.get('code', '')[:120].replace('\n', ' ')))
        elif name.startswith('browser') or name == 'web_read':
            out.append(('NET', name))
        else:
            unknown['fn:' + name] += 1; out.append(('OTHER', name))
    return turns, out


def summarise(trajs):
    invalid = sum(1 for _, o in trajs for c, _ in o if c == 'INVALID')
    calls = [[c for c, _ in o if c not in ('NOACT', 'TERMINAL', 'INVALID')] for _, o in trajs]
    n = sum(len(c) for c in calls); cnt = collections.Counter(x for c in calls for x in c)
    rng = np.random.default_rng(SEED); mat = np.array([[c.count(k) for k in PREC] for c in calls])
    boot = []
    for _ in range(NBOOT):
        s = mat[rng.integers(0, len(mat), len(mat))].sum(0); boot.append(s / max(s.sum(), 1))
    lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)
    groups = {'E0_type (WAIT+LIGHT)': ['WAIT', 'LIGHT'], 'phase_type (ORDER+PRESENCE)': ['ORDER', 'PRESENCE'] + (['PRES_UNLISTED'] if V2 else []),
              'not_covered (NET+OTHER)': ['NET', 'OTHER']}
    gb = {}
    for g, ks in groups.items():
        idx = [PREC.index(k) for k in ks]; v = [b[idx].sum() for b in boot]
        gb[g] = {'share': sum(cnt[k] for k in ks) / n, 'ci95': [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]}
    turns = [t for t, _ in trajs]
    return {'trajectories': len(trajs), 'tool_calls': n, 'model_wait_windows': int(sum(turns)),
            'model_wait_windows_per_traj_median': float(np.median(turns)),
            'classes': {k: {'n': cnt[k], 'share': cnt[k] / n, 'ci95_cluster_boot': [float(lo[i]), float(hi[i])]} for i, k in enumerate(PREC)},
            'groups': gb,
            'traj_with_at_least_one': {k: sum(k in c for c in calls) / len(calls) for k in PREC},
            'noact_turns': sum(1 for _, o in trajs for c, _ in o if c == 'NOACT'), 'invalid_actions_excluded': invalid}


def main():
    D = pathlib.Path(sys.argv[1]); O = pathlib.Path(sys.argv[2]); O.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(SEED)
    sw = pq.read_table(D / 'sweagent_0000.parquet', columns=['instance_id', 'model_name', 'target', 'trajectory']).to_pylist()
    by = collections.defaultdict(list)
    for i, r in enumerate(sw):
        by[r['instance_id']].append(i)
    inst = sorted(by); pick = [rnd.choice(by[k]) for k in inst]; sw_s = [sw[i] for i in sorted(rnd.sample(pick, NSAMP))]
    oh = pq.read_table(D / 'openhands_swegym.parquet').to_pylist(); oh_s = [oh[i] for i in sorted(rnd.sample(range(len(oh)), NSAMP))]
    res = {'version': VERSION, 'seed': SEED, 'datasets': {}}
    examples = []
    for name, rows, fn, key in [('swe-agent sample', sw_s, swe_agent_calls, 'trajectory'), ('openhands sample', oh_s, openhands_calls, 'messages'),
                                ('swe-agent full shard', sw, swe_agent_calls, 'trajectory'), ('openhands full', oh, openhands_calls, 'messages')]:
        unknown.clear(); trajs = [fn(r[key]) for r in rows]
        res['datasets'][name] = summarise(trajs); res['datasets'][name]['top_unrecognised'] = unknown.most_common(25)
        if 'sample' in name:
            for ti, (_, o) in enumerate(trajs):
                for c, cmd in o:
                    if c not in ('NOACT', 'TERMINAL', 'INVALID'):
                        examples.append((name, ti, c, cmd.replace('\n', ' \\n ')))
    if True:
        res['models_in_swe_agent_sample'] = dict(collections.Counter(r['model_name'] for r in sw_s))
        res['resolved_in_swe_agent_sample'] = sum(bool(r['target']) for r in sw_s)
    O = O / VERSION; O.mkdir(exist_ok=True)
    (O / 'r1_coverage.json').write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    spot = random.Random(SEED + 1).sample(examples, 80)
    with (O / 'r1_spotcheck_80.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['dataset', 'traj', 'rule_class', 'command_head', 'author_check'])
        for e in spot:
            w.writerow(list(e) + [''])
    for name, d in res['datasets'].items():
        print('==', name, d['trajectories'], 'traj', d['tool_calls'], 'calls', d['model_wait_windows'], 'turns, median/traj', d['model_wait_windows_per_traj_median'])
        print('  ', {k: '%d %.3f [%.3f,%.3f]' % (v['n'], v['share'], *v['ci95_cluster_boot']) for k, v in d['classes'].items()})
        print('  ', {k: '%.3f [%.3f,%.3f]' % (v['share'], *v['ci95']) for k, v in d['groups'].items()})
        print('   traj>=1:', {k: round(v, 3) for k, v in d['traj_with_at_least_one'].items()}, 'noact', d['noact_turns'], 'invalid', d['invalid_actions_excluded'])
        print('   unrecognised:', d['top_unrecognised'][:15])


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8'); main()
