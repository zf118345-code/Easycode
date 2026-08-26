from collections import OrderedDict

from core.services import execution_service as service


def _restore_registry(status_before, logs_before):
    with service._status_lock:
        service.execution_status.clear()
        service.execution_status.update(status_before)
    with service._logs_lock:
        service.execution_logs.clear()
        service.execution_logs.update(logs_before)


def test_record_execution_caps_status_and_logs_together():
    status_before = OrderedDict(service.execution_status)
    logs_before = OrderedDict(service.execution_logs)
    try:
        with service._status_lock:
            service.execution_status.clear()
        with service._logs_lock:
            service.execution_logs.clear()

        for index in range(service.MAX_LOG_ENTRIES + 7):
            service.record_execution(
                f'execution-{index}',
                {'status': 'running', 'index': index},
                [{'message': str(index)}],
            )

        assert len(service.execution_status) == service.MAX_LOG_ENTRIES
        assert len(service.execution_logs) == service.MAX_LOG_ENTRIES
        assert 'execution-0' not in service.execution_status
        assert 'execution-0' not in service.execution_logs
        assert next(iter(service.execution_status)) == 'execution-7'
        assert next(iter(service.execution_logs)) == 'execution-7'
    finally:
        _restore_registry(status_before, logs_before)


def test_execution_status_response_does_not_expose_mutable_registry_containers():
    status_before = OrderedDict(service.execution_status)
    logs_before = OrderedDict(service.execution_logs)
    try:
        service.record_execution('copy-test', {'status': 'success'}, [{'message': 'done'}])

        result = service.ExecutionService.get_execution_status('copy-test')
        result['status']['status'] = 'tampered'
        result['logs'].append({'message': 'tampered'})

        second = service.ExecutionService.get_execution_status('copy-test')
        assert second['status']['status'] == 'success'
        assert second['logs'] == [{'message': 'done'}]
    finally:
        _restore_registry(status_before, logs_before)
