"""Consistent SQLite backup while the app is running; never overwrite a file."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3


def backup_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError('The backup must use a different path from the database.')
    # mode=ro prevents accidentally creating an empty source database.
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=15)) as src:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with closing(sqlite3.connect(destination)) as target:
                src.backup(target, pages=256, sleep=.05)
                if target.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Backup integrity check failed.')
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', help='New backup file; existing files are never overwritten')
    parser.add_argument('--db', default=os.getenv('CAMPUSLINK_DB', str(Path(__file__).resolve().parent.parent / 'data' / 'campuslink.sqlite3')))
    args = parser.parse_args()
    print('Backup created:', backup_database(args.db, args.destination))


if __name__ == '__main__':
    main()
