from core.models import Edge


def test_edge_manual_routing_round_trip():
    raw = {
        'edge_id': 'edge_a_b',
        'source_node': 'a',
        'target_node': 'b',
        'source_port': 'success',
        'source_port_id': 'success',
        'canvas': 'workflow',
        'routing': {
            'mode': 'manual',
            'waypoints': [{'id': 'waypoint_1', 'x': 240, 'y': 160}],
        },
    }

    restored = Edge.from_dict(raw).to_dict()

    assert restored['routing'] == raw['routing']


def test_edge_without_manual_routing_stays_compact():
    edge = Edge(
        edge_id='edge_a_b',
        source_node='a',
        target_node='b',
        source_port='success',
        source_port_id='success',
    )

    assert 'routing' not in edge.to_dict()
