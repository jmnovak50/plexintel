from unittest.mock import Mock
import pytest
from scripts import restart_backend_safely as deploy


@pytest.mark.parametrize('locked,workers,check_only,allowed',[
    (True,[],False,False),(False,[123],False,False),
    (False,[],True,True),(False,[],False,True),
])
def test_restart_requires_exclusive_lock_and_no_active_worker(monkeypatch,locked,workers,check_only,allowed):
    lock=Mock();monkeypatch.setattr(deploy,'try_acquire_pipeline_lock',lambda **kwargs:None if locked else lock)
    monkeypatch.setattr(deploy,'active_workers',lambda:workers)
    restart=Mock();monkeypatch.setattr(deploy.subprocess,'run',restart)
    if allowed:deploy.guarded_restart(check_only=check_only)
    else:
        with pytest.raises(RuntimeError,match='restart refused'):deploy.guarded_restart(check_only=check_only)
    assert restart.called==(allowed and not check_only)
    if restart.called:
        restart.assert_called_once_with(['sudo','-n','systemctl','restart','plexintel-backend.service'],check=True)
    assert lock.release.called==(not locked)
