"""Operator-only maintenance, consistent backups and isolated restore rehearsals."""
import argparse
import asyncio
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid

from .backup import backup_database


def connect(path, *, readonly=False):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Database does not exist; refusing to create an empty one.')
    con = sqlite3.connect(path.as_uri() + ('?mode=ro' if readonly else '?mode=rw'), uri=True, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=15000')
    return con


def inspect_database(path):
    """Return integrity evidence without returning account or message content."""
    digest = hashlib.sha256()
    with closing(connect(path, readonly=True)) as con:
        if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Database integrity check failed.')
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        if not {'users','sessions','messages','profile_photos'}.issubset(tables):
            raise ValueError('This is not a CampusLink database.')
        counts = {}
        for table in tables:
            quoted = '"' + table.replace('"','""') + '"'
            digest.update(table.encode() + b'\0')
            count = 0
            for row in con.execute('SELECT * FROM ' + quoted + ' ORDER BY rowid'):
                count += 1
                for value in row:
                    if value is None:
                        encoded, kind = b'', b'N'
                    elif isinstance(value, bytes):
                        encoded, kind = value, b'B'
                    else:
                        encoded, kind = str(value).encode('utf-8'), type(value).__name__.encode()
                    digest.update(kind + b':' + str(len(encoded)).encode() + b':' + encoded)
            counts[table] = count
        return {'integrity':'ok','schema_version':con.execute('PRAGMA user_version').fetchone()[0],
                'counts':counts,'content_sha256':digest.hexdigest()}


def restore_rehearsal(source):
    """Restore into a disposable database; never overwrite the active database."""
    original = inspect_database(source)
    with tempfile.TemporaryDirectory(prefix='campuslink-restore-') as temp:
        restored = backup_database(source, Path(temp)/'restored.sqlite3')
        result = inspect_database(restored)
        if result != original:
            raise ValueError('Restored data does not match the backup.')
    return {**result,'restore_verified':True,'active_database_overwritten':False}


def env_number(name, default, low, high):
    try:
        value = int(os.getenv(name, str(default)))
        if not low <= value <= high:
            raise ValueError()
        return value
    except ValueError:
        raise RuntimeError(f'{name} must be an integer from {low} to {high}.') from None


@dataclass(frozen=True)
class OperationSettings:
    enabled: bool
    directory: Path
    interval_hours: int
    keep: int

    @classmethod
    def load(cls, deployment):
        enabled = os.getenv('CAMPUSLINK_BACKUPS_ENABLED', 'true' if deployment.mode=='staging' else 'false')
        if enabled not in ('true','false'):
            raise RuntimeError('CAMPUSLINK_BACKUPS_ENABLED must be true or false.')
        directory = Path(os.getenv('CAMPUSLINK_BACKUP_DIR',str(deployment.database.parent/'backups'))).expanduser().resolve()
        if directory == deployment.database or directory.is_relative_to(Path(__file__).resolve().parent.parent/'web'):
            raise RuntimeError('Backups must be outside the web assets directory.')
        return cls(enabled=='true',directory,
            env_number('CAMPUSLINK_BACKUP_INTERVAL_HOURS',24,1,168),
            env_number('CAMPUSLINK_BACKUP_KEEP',3,1,30))


class Operations:
    def __init__(self, database, settings, mailbox=None):
        self.database, self.settings = Path(database), settings
        self.mailbox = mailbox
        self.lock = threading.Lock()

    def record(self, operation, status, summary=None):
        now = int(time.time())
        with closing(connect(self.database)) as con:
            if status=='running':
                con.execute('INSERT INTO operation_runs(operation,status,started_at,completed_at,summary) VALUES (?,?,?,NULL,?) '
                    'ON CONFLICT(operation) DO UPDATE SET status=excluded.status,started_at=excluded.started_at,completed_at=NULL,summary=excluded.summary',
                    (operation,status,now,'{}'))
            else:
                con.execute('UPDATE operation_runs SET status=?,completed_at=?,summary=? WHERE operation=?',
                    (status,now,json.dumps(summary or {}),operation))
            con.commit()

    def perform(self, operation, action):
        if not self.lock.acquire(blocking=False):
            raise ValueError('Another maintenance operation is in progress. Try again shortly.')
        try:
            self.record(operation,'running')
            try:
                result = action()
            except Exception:
                self.record(operation,'failed',{'error':'Operation failed. Check storage and operator configuration.'})
                logging.getLogger('campuslink.operations').error('maintenance operation=%s status=failed',operation)
                raise
            self.record(operation,'ok',result)
            return result
        finally:
            self.lock.release()

    def manifests(self):
        results = []
        for path in self.settings.directory.glob('campuslink-auto-*.json'):
            try:
                if path.stat().st_size > 65536:
                    continue
                entry = json.loads(path.read_text())
                name = entry['filename']
                if (entry.get('kind')!='campuslink-automatic-backup'
                        or type(entry.get('created_at')) is not int
                        or not re.fullmatch(r'campuslink-auto-[0-9T_-]+-[a-f0-9]{12}\.sqlite3',name)
                        or path.stem != Path(name).stem
                        or not (path.parent/name).is_file()):
                    continue
                results.append(entry)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        return sorted(results,key=lambda item:(item['created_at'],item.get('created_at_ns',0)),reverse=True)

    def backup(self):
        def action():
            folder = self.settings.directory
            folder.mkdir(parents=True,exist_ok=True,mode=0o700)
            wal = Path(str(self.database)+'-wal')
            required = self.database.stat().st_size + (wal.stat().st_size if wal.is_file() else 0) + 16*1024*1024
            if shutil.disk_usage(folder).free < required:
                raise ValueError('Not enough free storage for a new backup. Existing backups were retained.')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
            name = f'campuslink-auto-{stamp}-{uuid.uuid4().hex[:12]}.sqlite3'
            final, partial = folder/name, folder/(name+'.partial')
            try:
                backup_database(self.database,partial)
                evidence = inspect_database(partial)
                os.link(partial,final)  # Atomic publication, without overwriting.
            finally:
                partial.unlink(missing_ok=True)
            with final.open('rb') as stream:
                checksum = hashlib.file_digest(stream,'sha256').hexdigest()
            entry = {**evidence,'kind':'campuslink-automatic-backup','filename':name,
                     'created_at':int(time.time()),'created_at_ns':time.time_ns(),'bytes':final.stat().st_size,
                     'sha256':checksum,
                     'offsite_copy_verified':False}
            manifest = final.with_suffix('.json')
            fd = os.open(manifest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as out:
                json.dump(entry,out)
                out.flush()
                os.fsync(out.fileno())
            for old in self.manifests()[self.settings.keep:]:
                (folder/old['filename']).unlink(missing_ok=True)
                (folder/old['filename']).with_suffix('.json').unlink(missing_ok=True)
            return entry
        return self.perform('backup',action)

    def verify_restore(self):
        def action():
            entries = self.manifests()
            if not entries:
                raise ValueError('Create a backup before running the restore check.')
            entry = entries[0]
            source = self.settings.directory/entry['filename']
            with source.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest() != entry['sha256']:
                    raise ValueError('Backup checksum does not match its manifest.')
            result = restore_rehearsal(source)
            if result['content_sha256'] != entry['content_sha256']:
                raise ValueError('Backup contents do not match its manifest.')
            return {**result,'filename':entry['filename'],'backup_created_at':entry['created_at']}
        return self.perform('restore',action)

    def downloadable_backup(self):
        entries=self.manifests()
        if not entries:raise ValueError('Create a backup before downloading one.')
        entry=entries[0];path=self.settings.directory/entry['filename']
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']:
                raise ValueError('Backup checksum failed. Create and verify a new backup.')
        return path,entry

    def cleanup(self):
        def action():
            now, result = int(time.time()), {}
            with closing(connect(self.database)) as con:
                for name, query, params in [
                    ('expired_sessions','DELETE FROM sessions WHERE expires_at<=?',(now,)),
                    ('expired_recovery_tokens','DELETE FROM recovery_tokens WHERE expires_at<=?',(now,)),
                    ('expired_email_tokens','DELETE FROM email_verification_tokens WHERE expires_at<=?',(now,)),
                    ('old_live_events','DELETE FROM events WHERE created_at<?',(now-86400,)),
                    ('old_read_notifications','DELETE FROM notifications WHERE read=1 AND created_at<?',(now-30*86400,)),
                    ('abandoned_post_photos','DELETE FROM post_photos WHERE created_at<? AND NOT EXISTS(SELECT 1 FROM posts WHERE photo_id=post_photos.id)',(now-86400,)),
                    ('old_mail_metadata','DELETE FROM mail_outbox WHERE status IN ("used","sent","cancelled","failed") AND created_at<?',(now-7*86400,)),
                ]:
                    result[name] = con.execute(query,params).rowcount
                con.commit()
            return result
        return self.perform('cleanup',action)

    def status(self):
        with closing(connect(self.database,readonly=True)) as con:
            runs = {row['operation']:{'status':row['status'],'started_at':row['started_at'],
                    'completed_at':row['completed_at'],'summary':json.loads(row['summary'])}
                    for row in con.execute('SELECT * FROM operation_runs')}
        return {'backups_enabled':self.settings.enabled,'backup_interval_hours':self.settings.interval_hours,
                'backup_keep':self.settings.keep,'offsite_copy_verified':False,
                'disk_free_bytes':shutil.disk_usage(self.database.parent).free,'runs':runs}

    async def run(self, stop):
        last_cleanup = 0
        while not stop.is_set():
            if self.mailbox and self.mailbox.configured:
                try:
                    await asyncio.to_thread(self.mailbox.process)
                except Exception:
                    logging.getLogger('campuslink.operations').error('Email queue needs operator attention.')
            try:
                if time.time()-last_cleanup >= 3600:
                    await asyncio.to_thread(self.cleanup)
                    last_cleanup = time.time()
                if self.settings.enabled:
                    entries = self.manifests()
                    if not entries or time.time()-entries[0]['created_at'] >= self.settings.interval_hours*3600:
                        await asyncio.to_thread(self.backup)
                        entries = self.manifests()
                    with closing(connect(self.database,readonly=True)) as con:
                        restored=con.execute('SELECT status,summary FROM operation_runs WHERE operation="restore"').fetchone()
                    if entries and (not restored or restored['status']!='ok' or json.loads(restored['summary']).get('filename')!=entries[0]['filename']):
                        await asyncio.to_thread(self.verify_restore)
            except Exception:
                logging.getLogger('campuslink.operations').error('Scheduled maintenance needs operator attention.')
            try:
                await asyncio.wait_for(stop.wait(),timeout=10)
            except TimeoutError:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('status','backup','restore-check','cleanup','inspect'))
    parser.add_argument('--db',default=os.getenv('CAMPUSLINK_DB',str(Path(__file__).resolve().parent.parent/'data'/'campuslink.sqlite3')))
    args = parser.parse_args()
    from .deployment import Deployment
    deployment = Deployment.load(Path(__file__).resolve().parent.parent,args.db)
    operations = Operations(deployment.database,OperationSettings.load(deployment))
    actions = {'status':operations.status,'backup':operations.backup,'restore-check':operations.verify_restore,
               'cleanup':operations.cleanup,'inspect':lambda:inspect_database(deployment.database)}
    try:
        print(json.dumps(actions[args.command](),indent=2))
    except (ValueError,OSError,sqlite3.Error) as exc:
        parser.exit(1,'Operation failed: '+type(exc).__name__+'. Check database/storage settings.\n')


if __name__=='__main__':
    main()
