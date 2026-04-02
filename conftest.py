import sys


def pytest_configure() -> None:
    if sys.platform != "win32":
        return

    import _pytest.pathlib as pytest_pathlib
    import _pytest.tmpdir as pytest_tmpdir

    original = pytest_pathlib.cleanup_dead_symlinks

    def safe_cleanup_dead_symlinks(root):
        try:
            return original(root)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 448:
                return None
            raise

    pytest_pathlib.cleanup_dead_symlinks = safe_cleanup_dead_symlinks
    pytest_tmpdir.cleanup_dead_symlinks = safe_cleanup_dead_symlinks
