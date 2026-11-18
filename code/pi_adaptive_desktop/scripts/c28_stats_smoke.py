"""Smoke test of c28_stats.py on C27 data (code check only; C27 conditions stand in for the C28 ones; output discarded)."""
import pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import c28_stats as S
S.SPEC = {'gzip3_d19': (0.1875, 3.0, 'fixed'), 'gzip4_d25': (0.25, 4.0, 'fixed'), 'gzip6_d37': (0.375, 6.0, 'fixed'),
          'json8': (1.0, 8.0, 'fixed'), 'gzip16': (1.0, 16.0, 'fixed'), 'bzip2_r': (1.0, 4.0, 'fixed')}
S.PAIRS = [('gzip6_d37', 'gzip3_d19'), ('json8', 'gzip3_d19')]
S.OUT = pathlib.Path(tempfile.mkdtemp())
S.main(stage='s1b', out_name='smoke.json')
print('SMOKE OK', S.OUT)
