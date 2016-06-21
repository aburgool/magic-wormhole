from __future__ import unicode_literals
import os, sys
import sqlite3
from pkg_resources import resource_string

class DBError(Exception):
    pass

def get_schema(version):
    schema_bytes = resource_string("wormhole.server",
                                   "db-schemas/v%d.sql" % version)
    return schema_bytes.decode("utf-8")

def get_upgrader(new_version):
    schema_bytes = resource_string("wormhole.server",
                                   "db-schemas/upgrade-to-v%d.sql" % new_version)
    return schema_bytes.decode("utf-8")

TARGET_VERSION = 2

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db(dbfile, target_version=TARGET_VERSION, stderr=sys.stderr):
    """Open or create the given db file. The parent directory must exist.
    Returns the db connection object, or raises DBError.
    """

    must_create = (dbfile == ":memory:") or not os.path.exists(dbfile)
    try:
        db = sqlite3.connect(dbfile)
    except (EnvironmentError, sqlite3.OperationalError) as e:
        raise DBError("Unable to create/open db file %s: %s" % (dbfile, e))
    db.row_factory = dict_factory

    if must_create:
        schema = get_schema(target_version)
        db.executescript(schema)
        db.execute("INSERT INTO version (version) VALUES (?)",
                   (target_version,))
        db.commit()

    try:
        version = db.execute("SELECT version FROM version").fetchone()["version"]
    except sqlite3.DatabaseError as e:
        # this indicates that the file is not a compatible database format.
        # Perhaps it was created with an old version, or it might be junk.
        raise DBError("db file is unusable: %s" % e)

    while version < target_version:
        try:
            upgrader = get_upgrader(version+1)
        except ValueError: # ResourceError??
            raise DBError("Unable to upgrade %s to version %s, left at %s"
                          % (dbfile, version+1, version))
        db.executescript(upgrader)
        db.commit()
        version = version+1

    if version != target_version:
        raise DBError("Unable to handle db version %s" % version)

    return db
