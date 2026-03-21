from pathlib import Path

from mc_foreman.execution.bridge import ExecutionBridge
from mc_foreman.execution.zone_allocator import (
    BuildZone,
    ZONE_PITCH_X,
    ZONE_PITCH_Z,
    preflight_check,
    reset_zone_counter,
)
from mc_foreman.infra.db import get_connection, init_db, reset_db_files
from mc_foreman.repositories.event_repo import EventRepo
from mc_foreman.repositories.queue_repo import QueueRepo
from mc_foreman.repositories.task_repo import TaskRepo
from mc_foreman.services.task_service import TaskService


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "zone_allocator_test.sqlite3"


class MockConfig:
    execution_mode = "mock"
    execution_tmp_dir = Path(__file__).resolve().parents[1] / "data" / "zone_allocator_exec"


def test_unique_zone_assignment_per_task():
    reset_db_files(DB_PATH)
    reset_zone_counter()
    conn = get_connection(DB_PATH)
    init_db(conn)
    task_service = TaskService(conn, TaskRepo(), EventRepo(), QueueRepo())

    t1 = task_service.submit_task(theme="凉亭", submitter_id="u1")
    t2 = task_service.submit_task(theme="石桥", submitter_id="u2")

    assert t1.zone_assignment
    assert t2.zone_assignment
    assert t1.zone_assignment != t2.zone_assignment
    print("  unique_zone_assignment_per_task ok")


def test_zone_assignment_roundtrip_and_prompt_uses_zone():
    reset_db_files(DB_PATH)
    reset_zone_counter()
    conn = get_connection(DB_PATH)
    init_db(conn)
    task_service = TaskService(conn, TaskRepo(), EventRepo(), QueueRepo())
    task = task_service.submit_task(theme="瞭望塔", submitter_id="u3")

    zone = BuildZone.from_assignment_str(task.zone_assignment)
    assert zone is not None

    bridge = ExecutionBridge(MockConfig())
    prompt = bridge._build_prompt(task)
    assert str(zone.origin_x) in prompt
    assert str(zone.origin_z) in prompt
    print("  zone_assignment_roundtrip_and_prompt_uses_zone ok")



def test_sparse_zone_spacing_keeps_successive_builds_far_apart():
    reset_db_files(DB_PATH)
    reset_zone_counter()
    conn = get_connection(DB_PATH)
    init_db(conn)
    task_service = TaskService(conn, TaskRepo(), EventRepo(), QueueRepo())

    tasks = [task_service.submit_task(theme=f"build-{i}", submitter_id=f"u{i}") for i in range(3)]
    zones = [BuildZone.from_assignment_str(task.zone_assignment) for task in tasks]
    assert all(zone is not None for zone in zones)

    dx01 = zones[1].origin_x - zones[0].origin_x
    dz01 = zones[1].origin_z - zones[0].origin_z
    dx12 = zones[2].origin_x - zones[1].origin_x
    dz12 = zones[2].origin_z - zones[1].origin_z

    assert abs(dx01) >= ZONE_PITCH_X or abs(dz01) >= ZONE_PITCH_Z
    assert abs(dx12) >= ZONE_PITCH_X or abs(dz12) >= ZONE_PITCH_Z
    assert dx01 == ZONE_PITCH_X
    assert dz01 == 0
    print("  sparse_zone_spacing_keeps_successive_builds_far_apart ok")



def test_zone_assignment_persists_across_fresh_task_service_instances():
    reset_db_files(DB_PATH)
    reset_zone_counter()

    conn1 = get_connection(DB_PATH)
    init_db(conn1)
    service1 = TaskService(conn1, TaskRepo(), EventRepo(), QueueRepo())
    task1 = service1.submit_task(theme="亭子", submitter_id="u1")
    zone1 = BuildZone.from_assignment_str(task1.zone_assignment)
    assert zone1 is not None
    conn1.close()

    reset_zone_counter()
    conn2 = get_connection(DB_PATH)
    init_db(conn2)
    service2 = TaskService(conn2, TaskRepo(), EventRepo(), QueueRepo())
    task2 = service2.submit_task(theme="石桥", submitter_id="u2")
    zone2 = BuildZone.from_assignment_str(task2.zone_assignment)
    assert zone2 is not None

    assert zone2.zone_index == zone1.zone_index + 1
    assert zone2.origin_x == zone1.origin_x + ZONE_PITCH_X
    assert zone2.origin_z == zone1.origin_z
    print("  zone_assignment_persists_across_fresh_task_service_instances ok")


def test_preflight_check_rejects_spawn_overlap():
    zone = BuildZone(origin_x=0, origin_z=0, y=64, size_x=64, size_z=64, zone_index=99)
    ok, issues = preflight_check(zone)
    assert ok is False
    assert "zone_overlaps_spawn" in issues
    print("  preflight_check_rejects_spawn_overlap ok")


def main():
    tests = [
        test_unique_zone_assignment_per_task,
        test_zone_assignment_roundtrip_and_prompt_uses_zone,
        test_sparse_zone_spacing_keeps_successive_builds_far_apart,
        test_zone_assignment_persists_across_fresh_task_service_instances,
        test_preflight_check_rejects_spawn_overlap,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print("  FAIL %s: %s" % (t.__name__, e))
            failed += 1
    print("\nzone allocator: %d passed, %d failed" % (passed, failed))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
