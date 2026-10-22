"""Owner-only local configuration, without secret values in error messages."""
import os
from pathlib import Path
import stat

from dotenv import dotenv_values


class PrivateConfigError(RuntimeError):
    pass


def read_private_file(path, *, max_bytes=32768):
    try:
        fd = os.open(Path(path).expanduser(), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'r', encoding='utf-8') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise PrivateConfigError('Credential file must be a regular, owner-only file (0600 or 0400)')
            value = handle.read(max_bytes + 1)
            if len(value) > max_bytes:
                raise PrivateConfigError('Credential file exceeds allowed size')
            return value
    except PrivateConfigError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise PrivateConfigError('Credential file cannot be read; verify location, ownership and permissions') from None


def read_private_token(path):
    value = read_private_file(path).strip()
    if len(value) < 32 or any(c.isspace() for c in value):
        raise PrivateConfigError('Service credential must contain at least 32 characters and no whitespace')
    return value


def load_session_credentials():
    configured = os.getenv('WATCH_SESSIONS_CREDENTIALS_FILE')
    path = Path(configured).expanduser() if configured else Path.home()/'.config/plexintel/watch-sessions.env'
    if configured or path.exists():
        from io import StringIO
        values = dotenv_values(stream=StringIO(read_private_file(path)), interpolate=False)
        allowed = {'WATCH_SESSIONS_DATABASE_URL', 'WATCH_SESSIONS_RECONCILIATION_DAYS',
                   'WATCH_SESSIONS_RETRIES', 'TAUTULLI_API_URL', 'TAUTULLI_API_KEY'}
        if set(values) - allowed or any(v is None or '\n' in v or '\r' in v for v in values.values()):
            raise PrivateConfigError('Session credential file contains unsupported keys or invalid values')
        for key, value in values.items():
            os.environ[key] = value
    if not os.getenv('WATCH_SESSIONS_DATABASE_URL'):
        raise PrivateConfigError('Configure WATCH_SESSIONS_DATABASE_URL in the private session credential file')
