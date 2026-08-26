from __future__ import annotations

from core.capabilities.registry import register_capability


@register_capability(
    'platform.state.get', name='读取持久状态', permissions=['platform.state.read'], idempotent=True,
    inputs=[
        {'name': 'key', 'type': 'str', 'required': True},
        {'name': 'namespace', 'type': 'str', 'default': 'default'},
        {'name': 'default', 'type': 'any', 'default': None},
    ],
    outputs=[{'name': 'value', 'type': 'any'}],
)
def state_get(context, **inputs):
    value = context.platform_store('platform.state.read').get_state(
        inputs['key'], inputs.get('namespace') or 'default', inputs.get('default')
    )
    return {'success': True, 'data': {'value': value}}


@register_capability(
    'platform.state.set', name='写入持久状态', permissions=['platform.state.write'], idempotent=True,
    inputs=[
        {'name': 'key', 'type': 'str', 'required': True},
        {'name': 'value', 'type': 'any', 'required': True},
        {'name': 'namespace', 'type': 'str', 'default': 'default'},
    ],
    outputs=[{'name': 'updated_at', 'type': 'float'}],
)
def state_set(context, **inputs):
    result = context.platform_store('platform.state.write').set_state(
        inputs['key'], inputs.get('value'), inputs.get('namespace') or 'default'
    )
    return {'success': True, 'data': result}


@register_capability(
    'platform.message.publish', name='发布本地协同消息', permissions=['platform.message'], idempotent=False,
    inputs=[
        {'name': 'channel', 'type': 'str', 'required': True},
        {'name': 'payload', 'type': 'any', 'required': True},
        {'name': 'sender', 'type': 'str', 'default': ''},
        {'name': 'ttl_seconds', 'type': 'int', 'default': 86400},
    ],
    outputs=[{'name': 'id', 'type': 'str'}],
)
def message_publish(context, **inputs):
    result = context.platform_store('platform.message').publish_message(
        inputs['channel'], inputs.get('payload'), sender=inputs.get('sender') or '',
        ttl_seconds=inputs.get('ttl_seconds') or 86400,
    )
    return {'success': True, 'data': result}


@register_capability(
    'platform.message.claim', name='领取协同消息', permissions=['platform.message'], idempotent=False,
    inputs=[
        {'name': 'channel', 'type': 'str', 'required': True},
        {'name': 'consumer', 'type': 'str', 'required': True},
        {'name': 'limit', 'type': 'int', 'default': 20},
        {'name': 'lease_seconds', 'type': 'int', 'default': 30},
    ],
    outputs=[{'name': 'messages', 'type': 'list'}],
)
def message_claim(context, **inputs):
    messages = context.platform_store('platform.message').claim_messages(
        inputs['channel'], inputs['consumer'], limit=inputs.get('limit') or 20,
        lease_seconds=inputs.get('lease_seconds') or 30,
    )
    return {'success': True, 'data': {'messages': messages}}


@register_capability(
    'platform.message.ack', name='确认协同消息', permissions=['platform.message'], idempotent=True,
    inputs=[
        {'name': 'message_id', 'type': 'str', 'required': True},
        {'name': 'consumer', 'type': 'str', 'required': True},
    ],
    outputs=[{'name': 'acked', 'type': 'bool'}],
)
def message_ack(context, **inputs):
    acked = context.platform_store('platform.message').ack_message(inputs['message_id'], inputs['consumer'])
    return {'success': acked, 'code': 'OK' if acked else 'NOT_CLAIMED', 'data': {'acked': acked}}


@register_capability(
    'platform.lease.acquire', name='获取分布式资源锁', permissions=['platform.lease'], idempotent=False,
    inputs=[
        {'name': 'resource_key', 'type': 'str', 'required': True},
        {'name': 'owner', 'type': 'str', 'required': True},
        {'name': 'ttl_seconds', 'type': 'int', 'default': 30},
    ],
    outputs=[{'name': 'lease', 'type': 'dict'}],
)
def lease_acquire(context, **inputs):
    lease = context.platform_store('platform.lease').acquire_lease(
        inputs['resource_key'], inputs['owner'], inputs.get('ttl_seconds') or 30
    )
    return {
        'success': lease is not None,
        'code': 'OK' if lease is not None else 'LEASE_BUSY',
        'message': '' if lease is not None else '资源正被其他实例占用',
        'data': {'lease': lease},
    }


@register_capability(
    'platform.lease.renew', name='续租分布式资源锁', permissions=['platform.lease'], idempotent=True,
    inputs=[
        {'name': 'resource_key', 'type': 'str', 'required': True},
        {'name': 'owner', 'type': 'str', 'required': True},
        {'name': 'token', 'type': 'str', 'required': True},
        {'name': 'ttl_seconds', 'type': 'int', 'default': 30},
    ],
    outputs=[{'name': 'renewed', 'type': 'bool'}],
)
def lease_renew(context, **inputs):
    renewed = context.platform_store('platform.lease').renew_lease(
        inputs['resource_key'], inputs['owner'], inputs['token'], inputs.get('ttl_seconds') or 30
    )
    return {'success': renewed, 'code': 'OK' if renewed else 'LEASE_LOST', 'data': {'renewed': renewed}}


@register_capability(
    'platform.lease.release', name='释放分布式资源锁', permissions=['platform.lease'], idempotent=True,
    inputs=[
        {'name': 'resource_key', 'type': 'str', 'required': True},
        {'name': 'owner', 'type': 'str', 'required': True},
        {'name': 'token', 'type': 'str', 'required': True},
    ],
    outputs=[{'name': 'released', 'type': 'bool'}],
)
def lease_release(context, **inputs):
    released = context.platform_store('platform.lease').release_lease(
        inputs['resource_key'], inputs['owner'], inputs['token']
    )
    return {'success': released, 'data': {'released': released}}


@register_capability(
    'platform.remote.publish', name='发送跨电脑消息', permissions=['network.coordinator'], idempotent=False,
    inputs=[
        {'name': 'endpoint', 'type': 'str', 'required': True},
        {'name': 'token', 'type': 'str', 'required': True},
        {'name': 'channel', 'type': 'str', 'required': True},
        {'name': 'payload', 'type': 'any', 'required': True},
        {'name': 'sender', 'type': 'str', 'default': ''},
        {'name': 'ttl_seconds', 'type': 'int', 'default': 86400},
    ],
    outputs=[
        {'name': 'queued', 'type': 'bool'},
        {'name': 'message_id', 'type': 'str'},
        {'name': 'outbox_id', 'type': 'str'},
    ],
)
def remote_publish(context, **inputs):
    result = context.send_remote_message(
        inputs['endpoint'], inputs['token'], inputs['channel'], inputs.get('payload'),
        sender=inputs.get('sender') or '', ttl_seconds=inputs.get('ttl_seconds') or 86400,
    )
    return {'success': True, 'code': 'QUEUED' if result.get('queued') else 'SENT', 'data': result}


@register_capability(
    'platform.remote.claim', name='领取跨电脑消息', permissions=['network.coordinator'], idempotent=False,
    inputs=[
        {'name': 'endpoint', 'type': 'str', 'required': True},
        {'name': 'token', 'type': 'str', 'required': True},
        {'name': 'channel', 'type': 'str', 'required': True},
        {'name': 'consumer', 'type': 'str', 'required': True},
        {'name': 'limit', 'type': 'int', 'default': 20},
        {'name': 'lease_seconds', 'type': 'int', 'default': 30},
    ],
    outputs=[{'name': 'messages', 'type': 'list'}],
)
def remote_claim(context, **inputs):
    messages = context.claim_remote_messages(
        inputs['endpoint'], inputs['token'], inputs['channel'], inputs['consumer'],
        limit=inputs.get('limit') or 20, lease_seconds=inputs.get('lease_seconds') or 30,
    )
    return {'success': True, 'data': {'messages': messages}}


@register_capability(
    'platform.remote.ack', name='确认跨电脑消息', permissions=['network.coordinator'], idempotent=True,
    inputs=[
        {'name': 'endpoint', 'type': 'str', 'required': True},
        {'name': 'token', 'type': 'str', 'required': True},
        {'name': 'message_id', 'type': 'str', 'required': True},
        {'name': 'consumer', 'type': 'str', 'required': True},
    ],
    outputs=[{'name': 'acked', 'type': 'bool'}],
)
def remote_ack(context, **inputs):
    acked = context.ack_remote_message(
        inputs['endpoint'], inputs['token'], inputs['message_id'], inputs['consumer'],
    )
    return {'success': acked, 'code': 'OK' if acked else 'NOT_CLAIMED', 'data': {'acked': acked}}


@register_capability(
    'platform.remote.lease.acquire', name='获取跨电脑资源锁', permissions=['network.coordinator'], idempotent=False,
    inputs=[
        {'name': 'endpoint', 'type': 'str', 'required': True},
        {'name': 'token', 'type': 'str', 'required': True},
        {'name': 'resource_key', 'type': 'str', 'required': True},
        {'name': 'owner', 'type': 'str', 'required': True},
        {'name': 'ttl_seconds', 'type': 'int', 'default': 30},
    ],
    outputs=[{'name': 'lease', 'type': 'dict'}],
)
def remote_lease_acquire(context, **inputs):
    lease = context.acquire_remote_lease(
        inputs['endpoint'], inputs['token'], inputs['resource_key'], inputs['owner'],
        ttl_seconds=inputs.get('ttl_seconds') or 30,
    )
    return {
        'success': lease is not None,
        'code': 'OK' if lease is not None else 'LEASE_BUSY',
        'data': {'lease': lease},
    }


@register_capability(
    'platform.remote.lease.renew', name='续租跨电脑资源锁', permissions=['network.coordinator'], idempotent=True,
    inputs=[
        {'name': 'endpoint', 'type': 'str', 'required': True},
        {'name': 'token', 'type': 'str', 'required': True},
        {'name': 'resource_key', 'type': 'str', 'required': True},
        {'name': 'owner', 'type': 'str', 'required': True},
        {'name': 'lease_token', 'type': 'str', 'required': True},
        {'name': 'ttl_seconds', 'type': 'int', 'default': 30},
    ],
    outputs=[{'name': 'renewed', 'type': 'bool'}],
)
def remote_lease_renew(context, **inputs):
    renewed = context.renew_remote_lease(
        inputs['endpoint'], inputs['token'], inputs['resource_key'], inputs['owner'], inputs['lease_token'],
        ttl_seconds=inputs.get('ttl_seconds') or 30,
    )
    return {'success': renewed, 'code': 'OK' if renewed else 'LEASE_LOST', 'data': {'renewed': renewed}}


@register_capability(
    'platform.remote.lease.release', name='释放跨电脑资源锁', permissions=['network.coordinator'], idempotent=True,
    inputs=[
        {'name': 'endpoint', 'type': 'str', 'required': True},
        {'name': 'token', 'type': 'str', 'required': True},
        {'name': 'resource_key', 'type': 'str', 'required': True},
        {'name': 'owner', 'type': 'str', 'required': True},
        {'name': 'lease_token', 'type': 'str', 'required': True},
    ],
    outputs=[{'name': 'released', 'type': 'bool'}],
)
def remote_lease_release(context, **inputs):
    released = context.release_remote_lease(
        inputs['endpoint'], inputs['token'], inputs['resource_key'], inputs['owner'], inputs['lease_token'],
    )
    return {'success': released, 'data': {'released': released}}
