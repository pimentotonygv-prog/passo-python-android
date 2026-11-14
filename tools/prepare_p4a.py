"""Work around p4a reusing a venv across ABIs and overlaying two pip versions."""
import sys
from pathlib import Path

source = Path(sys.argv[1])/'pythonforandroid'/'build.py'
text = source.read_text()
old = "shprint(host_python, '-m', 'venv', 'venv')"
new = "shprint(host_python, '-m', 'venv', '--clear', 'venv')"
if old in text:
    if text.count(old) != 1:
        raise RuntimeError('Unexpected p4a venv setup. Review before applying patch.')
    source.write_text(text.replace(old, new))
elif new not in text:
    raise RuntimeError('Expected p4a venv setup was not found.')
print('p4a: clean packaging virtualenv for each ABI')
