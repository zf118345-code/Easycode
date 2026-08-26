from core.graph.builder import GraphBuilder


class FakeNode:
    def __init__(self, node_id, node_type='log', params=None):
        self.node_id = node_id
        self.node_type = node_type
        self.params = params or {}


class FakeTask:
    def __init__(self, task_id, nodes):
        self.task_id = task_id
        self.nodes = nodes


class FakeEdge:
    canvas = 'workflow'

    def __init__(self, source_node, target_node, port='success'):
        self.source_node = source_node
        self.target_node = target_node
        self.source_port = port

    def to_dict(self):
        return {'source_port': self.source_port, 'source_port_id': self.source_port}


class FakeProject:
    def __init__(self, tasks, edges):
        self.tasks = {task.task_id: task for task in tasks}
        self.edges = edges
        self.topology = None


def test_builds_independent_main_and_function_graphs_from_source_ownership():
    main = FakeTask('main', [FakeNode('main_a'), FakeNode('main_b')])
    function = FakeTask('function_login', [FakeNode('fn_entry'), FakeNode('fn_return')])
    project = FakeProject([main, function], [
        FakeEdge('main_a', 'main_b'),
        FakeEdge('fn_entry', 'fn_return'),
    ])

    graphs = GraphBuilder.build_from_project(project)

    assert graphs['main'].get_out_edges('main_a')[0][0] == 'main_b'
    assert graphs['main'].get_out_edges('fn_entry') == []
    assert graphs['function_login'].get_out_edges('fn_entry')[0][0] == 'fn_return'
    assert graphs['function_login'].get_out_edges('main_a') == []


def test_popup_identity_belongs_only_to_page_state_node_property():
    popup = FakeNode('popup', 'page_state', {'is_random_popup': True})
    normal = FakeNode('normal', 'page_state', {'is_random_popup': False})
    action = FakeNode('action', 'image_recognition', {'is_random_popup': True})
    assert GraphBuilder.is_popup_node(popup) is True
    assert GraphBuilder.is_popup_node(normal) is False
    assert GraphBuilder.is_popup_node(action) is False
