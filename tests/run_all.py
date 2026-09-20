from tests.test_core import test_core
from tests.test_dev_manager import test_dev_manager
from tests.test_logger import test_logger
from tests.test_model_security import test_model_security
from tests.test_hermes_bridge import test_hermes_bridge_lock


def run_all():
    print("\nKAZEN TESTLERI BASLIYOR...\n")

    test_core()
    test_dev_manager()
    test_logger()
    test_model_security()
    test_hermes_bridge_lock()

    print("\n==============================")
    print("TUM KAZEN TESTLERI: BASARILI")
    print("==============================")


if __name__ == "__main__":
    run_all()