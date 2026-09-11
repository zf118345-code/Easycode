import concurrent.futures
import threading

from core.services.capture_target_pool import CaptureTargetPool


def test_capture_target_pool_reuses_exact_target_and_closes_on_change(monkeypatch, tmp_path):
    created = []

    class Driver:
        def __init__(self, target):
            self.target = dict(target)
            self.closed = False

        def close(self):
            self.closed = True

    def create_driver(_project_path, target):
        driver = Driver(target)
        created.append(driver)
        return driver

    monkeypatch.setattr('core.vnext.target_runtime.create_target_driver', create_driver)
    pool = CaptureTargetPool()
    target = {'target_id': 'phone', 'type': 'android_adb', 'device_serial': 'serial-1'}

    first, reused_first = pool.acquire('ide', str(tmp_path), target)
    second, reused_second = pool.acquire('ide', str(tmp_path), dict(target))
    changed, reused_changed = pool.acquire('ide', str(tmp_path), {**target, 'device_serial': 'serial-2'})

    assert first is second
    assert reused_first is False
    assert reused_second is True
    assert reused_changed is False
    assert first.driver.closed is True
    assert changed.driver.closed is False
    pool.close_owner('ide')
    assert changed.driver.closed is True


def test_capture_target_pool_keeps_owners_isolated(monkeypatch, tmp_path):
    created = []

    class Driver:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    def create_driver(*_args):
        driver = Driver()
        created.append(driver)
        return driver

    monkeypatch.setattr('core.vnext.target_runtime.create_target_driver', create_driver)
    pool = CaptureTargetPool()
    target = {'target_id': 'desktop', 'type': 'windows'}
    ide, _ = pool.acquire('ide', str(tmp_path), target)
    player, _ = pool.acquire('player', str(tmp_path), target)

    pool.close_owner('ide')

    assert ide.driver.closed is True
    assert player.driver.closed is False
    assert pool.stats() == {'count': 1, 'owners': ['player']}
    pool.close_all()


def test_capture_target_pool_coalesces_prewarm_and_immediate_click(monkeypatch, tmp_path):
    pool = CaptureTargetPool()
    entered = threading.Event()
    release = threading.Event()
    created = []

    class Driver:
        def close(self):
            pass

    def create_driver(*_args):
        entered.set()
        assert release.wait(2)
        driver = Driver()
        created.append(driver)
        return driver

    monkeypatch.setattr('core.vnext.target_runtime.create_target_driver', create_driver)
    target = {'target_id': 'phone', 'type': 'android_adb', 'device_serial': 'device-1'}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        prewarm = executor.submit(pool.acquire, 'ide', str(tmp_path), target)
        assert entered.wait(1)
        click = executor.submit(pool.acquire, 'ide', str(tmp_path), target)
        release.set()
        prewarm_entry, prewarm_reused = prewarm.result(timeout=2)
        click_entry, click_reused = click.result(timeout=2)

    assert len(created) == 1
    assert prewarm_reused is False
    assert click_reused is True
    assert prewarm_entry.driver is click_entry.driver
