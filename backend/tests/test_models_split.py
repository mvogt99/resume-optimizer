import sqlite3
import os
import models
import models_classes
import models_journey
from models_schema1 import _init_schema_part1
from models_schema2 import _init_schema_part2, _init_schema_final, _run_migrations, _init_schema_part3

def test_shim_imports_work():
    assert callable(models.User)
    assert callable(models.get_latest_watermarks)

def test_direct_submodule_import_same_object():
    models_User = models.User
    models_classes_User = models_classes.User
    assert models_User is models_classes_User

    models_get_latest_watermarks = models.get_latest_watermarks
    models_journey_get_latest_watermarks = models_journey.get_latest_watermarks
    assert models_get_latest_watermarks is models_journey_get_latest_watermarks

def test_init_db_creates_all_tables():
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    _init_schema_part1(cursor)
    _run_migrations(cursor)
    _init_schema_part2(cursor)
    _init_schema_part3(cursor)
    _init_schema_final(cursor)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert len(tables) >= 30

def test_all_split_files_under_500_lines():
    test_dir = os.path.dirname(__file__)
    model_files = [
        os.path.join(test_dir, '..', 'models.py'),
        os.path.join(test_dir, '..', 'models_schema1.py'),
        os.path.join(test_dir, '..', 'models_schema2.py'),
        os.path.join(test_dir, '..', 'models_classes.py'),
        os.path.join(test_dir, '..', 'models_journey.py')
    ]
    for file_path in model_files:
        with open(file_path, 'r') as file:
            assert len(file.readlines()) < 500
