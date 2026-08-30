from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/repository/publish-authoritative-bundle.sh'


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


def test_publish_script_restores_main_and_bootstrap_and_preserves_backup(tmp_path):
    source = tmp_path / 'source'
    remote = tmp_path / 'remote.git'
    bundle = tmp_path / 'source.bundle'

    run('git', 'init', '-b', 'bootstrap/v0.1', str(source))
    run('git', 'config', 'user.name', 'Test User', cwd=source)
    run('git', 'config', 'user.email', 'test@example.invalid', cwd=source)
    required = [
        'README.md',
        'LICENSE',
        'AGENTS.md',
        'MANUAL-ACTIONS-CHECKLIST.md',
        'docs/10-spec-development/execution-state.yaml',
        'docs/10-spec-development/open-cycling-workshop-platform-agent-master-loop-v0.2.md',
        '.github/workflows/ci.yml',
        '.github/workflows/security.yml',
    ]
    for rel in required:
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'{rel}\n')
    run('git', 'add', '.', cwd=source)
    run('git', 'commit', '-m', 'authoritative', cwd=source)
    authoritative = run('git', 'rev-parse', 'HEAD', cwd=source).stdout.strip()
    run('git', 'bundle', 'create', str(bundle), 'HEAD', 'refs/heads/bootstrap/v0.1', cwd=source)

    run('git', 'init', '--bare', str(remote))
    seed = tmp_path / 'seed'
    run('git', 'clone', str(remote), str(seed))
    run('git', 'config', 'user.name', 'Seed User', cwd=seed)
    run('git', 'config', 'user.email', 'seed@example.invalid', cwd=seed)
    (seed / 'README.md').write_text('partial\n')
    run('git', 'add', 'README.md', cwd=seed)
    run('git', 'commit', '-m', 'partial', cwd=seed)
    partial = run('git', 'rev-parse', 'HEAD', cwd=seed).stdout.strip()
    run('git', 'push', 'origin', 'HEAD:main', cwd=seed)

    result = run('bash', str(SCRIPT), str(bundle), str(remote))
    assert 'Repository restore verified' in result.stdout

    main = run('git', '--git-dir', str(remote), 'rev-parse', 'refs/heads/main').stdout.strip()
    bootstrap = run('git', '--git-dir', str(remote), 'rev-parse', 'refs/heads/bootstrap/v0.1').stdout.strip()
    assert main == authoritative
    assert bootstrap == authoritative

    refs = run('git', '--git-dir', str(remote), 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads/pre-consolidation').stdout
    assert partial in refs
