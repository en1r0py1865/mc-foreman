from pathlib import Path

from mc_foreman.infra.db import reset_db_files
from mc_foreman.runtime.bootstrap import bootstrap_runtime_hook, reset_runtime_hook_cache


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "runtime_cache_test.sqlite3"


def main():
    reset_db_files(DB_PATH)
    reset_runtime_hook_cache()

    hook1 = bootstrap_runtime_hook(db_path=DB_PATH)
    hook2 = bootstrap_runtime_hook(db_path=DB_PATH)
    assert hook1 is hook2

    reset_runtime_hook_cache()
    hook3 = bootstrap_runtime_hook(db_path=DB_PATH)
    assert hook3 is not hook1

    other_db = DB_PATH.with_name("runtime_cache_test_other.sqlite3")
    reset_db_files(other_db)
    hook4 = bootstrap_runtime_hook(db_path=other_db)
    assert hook4 is not hook3

    print("runtime cache ok")

def test_main():
    main()


if __name__ == "__main__":
    main()
