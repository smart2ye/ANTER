from types import SimpleNamespace
from unittest.mock import Mock

from app.services.startup_maintenance import should_run_schema_upgrades


def test_existing_postgres_schema_skips_heavy_startup_upgrades_by_default():
    app = SimpleNamespace(config={'STARTUP_SCHEMA_UPGRADES_ENABLED': False})
    inspector = Mock()
    inspector.has_table.return_value = True

    assert should_run_schema_upgrades(app, inspector) is False
    inspector.has_table.assert_called_once_with('users')


def test_missing_schema_or_explicit_flag_runs_startup_upgrades():
    missing_schema_app = SimpleNamespace(config={'STARTUP_SCHEMA_UPGRADES_ENABLED': False})
    missing_schema_inspector = Mock()
    missing_schema_inspector.has_table.return_value = False
    assert should_run_schema_upgrades(missing_schema_app, missing_schema_inspector) is True

    forced_upgrade_app = SimpleNamespace(config={'STARTUP_SCHEMA_UPGRADES_ENABLED': True})
    forced_upgrade_inspector = Mock()
    assert should_run_schema_upgrades(forced_upgrade_app, forced_upgrade_inspector) is True
    forced_upgrade_inspector.has_table.assert_not_called()
