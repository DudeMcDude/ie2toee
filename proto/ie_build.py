"""Stage a complete preview conversion before replacing its work and install folders."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile


@contextmanager
def preview_build(out, inputs=()):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # The OS releases this lock even if the converter is interrupted.
    with (out / '.ie2toee.lock').open('a+b') as lock:
        try:
            if os.name == 'nt':
                import msvcrt
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise SystemExit('Cannot lock conversion output folder %s: %s' % (out, exc)) from exc

        targets = [out / 'work', out / 'install']
        for target in targets:
            if target.resolve() != target or (target.exists() and not target.is_dir()):
                raise SystemExit('Expected a regular output directory at %s' % target)
            if any(Path(src).resolve().is_relative_to(target) for src in inputs if src):
                raise SystemExit('Output directory %s contains a conversion input' % target)

        with tempfile.TemporaryDirectory(dir=out, prefix='.ie2toee-build-') as tmp:
            stage = Path(tmp)
            for target in targets:
                (stage / target.name).mkdir()
            marker = Path('work', '.ie2toee-generated')
            (stage / marker).touch()
            yield stage

            # Keep both previous directories until both replacements are in place.
            # Older previews shared work/ with anything the user put there. Keep this
            # first, unmarked output as a backup when migrating to owned directories.
            previous = stage
            if not (out / marker).is_file() and any(target.exists() for target in targets):
                previous = Path(tempfile.mkdtemp(dir=out, prefix='previous-output-'))
            moved = []
            try:
                for target in targets:
                    if target.exists():
                        backup = previous / (target.name + '.previous')
                        target.rename(backup)
                        moved.append((backup, target))
                    fresh = stage / target.name
                    fresh.rename(target)
                    moved.append((target, fresh))
            except OSError:
                for current, original in reversed(moved):
                    current.rename(original)
                if previous != stage:
                    previous.rmdir()
                raise
            if previous != stage:
                print('Previous conversion output saved in %s' % previous, flush=True)
