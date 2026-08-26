"""page_state 执行器的当前条件结构测试。"""

from core.node_executors.base.page_state import PageStateNodeExecutor


class TestPageStateFeatureNormalization:
    def test_new_condition_structure(self):
        """新结构：condition_type + 平铺字段（条件列表编辑器产出）"""
        feature = {
            'condition_type': 'text_contains',
            'target_text': '今日特惠',
            'region_type': 'fullwindow',
            'negate': True,
            'combine_mode': 'or',
        }
        cond = PageStateNodeExecutor._build_condition(feature)
        assert cond['condition_type'] == 'text_contains'
        assert cond['target_text'] == '今日特惠'
        # 取反由执行器在特征层消费；组合方式只由页面节点的 feature_mode 决定。
        assert 'negate' not in cond
        assert 'combine_mode' not in cond

    def test_new_image_feature_structure(self):
        feature = {'condition_type': 'image_exists', 'image_source': 'shop_btn', 'threshold': 85}
        cond = PageStateNodeExecutor._build_condition(feature)
        assert cond['condition_type'] == 'image_exists'
        assert cond['image_source'] == 'shop_btn'
        assert cond['threshold'] == 85

    def test_default_type_fallback(self):
        cond = PageStateNodeExecutor._build_condition({})
        assert cond['condition_type'] == 'image_exists'

    def test_captured_image_region_is_not_silently_expanded_to_full_window(self):
        """捕获生成的图片即使误带 fullwindow，也必须使用已录制的局部区域。"""
        cond = PageStateNodeExecutor._build_condition({
            'condition_type': 'image_exists',
            'image_source': 'asset://page-button',
            'region_type': 'fullwindow',
            'region_value': [12, 18, 80, 36],
            'crop_rect': [12, 18, 80, 36],
        })
        assert cond['region_type'] == 'recorded'

    def test_manual_full_window_feature_remains_full_window(self):
        """没有捕获元数据的手工全窗口条件不应被擅自改写。"""
        cond = PageStateNodeExecutor._build_condition({
            'condition_type': 'image_exists',
            'image_source': 'asset://page-background',
            'region_type': 'fullwindow',
            'region_value': [12, 18, 80, 36],
        })
        assert cond['region_type'] == 'fullwindow'


class TestPageStateParamsSchema:
    """page_state 参数 schema：详情面板精简后的形态"""

    def test_schema_simplified(self):
        from core.params import ALL_PARAMS

        cfg = ALL_PARAMS['page_state']
        assert cfg['modes'] == ['topology']
        # 只保留 页面标识(隐藏) / 特征列表 / 组合模式：page_name、exits 均已移除
        assert set(cfg['params'].keys()) == {'page_id', 'features', 'feature_mode'}
        # page_id 为内部标识：表单隐藏
        assert cfg['params']['page_id'].get('hidden') is True
        # 特征列表：条件列表编辑器（逻辑判断同款交互），页面特征专属
        assert cfg['params']['features']['type'] == 'condition_list_editor'
        assert cfg['params']['features'].get('pageFeatures') is True
        assert cfg['params']['features'].get('addLabel') == '添加特征'
        assert cfg['params']['feature_mode']['default'] == 'and'


class TestSmartJumpParamsSchema:
    """smart_jump 参数 schema：主流程专属 + 精简表单"""

    def test_schema_simplified(self):
        from core.params import ALL_PARAMS

        cfg = ALL_PARAMS['smart_jump']
        # 主流程专属：拓扑画布不可用
        assert cfg['modes'] == ['workflow']
        # 只保留 目标页面(下拉) + 超时：其余 5 个参数全部移除
        assert set(cfg['params'].keys()) == {'target_page_id', 'timeout'}
        assert cfg['params']['target_page_id']['type'] == 'page_select'
        assert cfg['params']['timeout']['default'] == 3000


class TestFeatureCombinationMode:
    """特征组合模式：页面级 feature_mode 是唯一的 AND/OR 语义来源。"""

    def _combine(self, results, features, mode):
        return PageStateNodeExecutor._combine_results(results, features, mode)

    def test_global_or_with_default_combine(self):
        """全局 or + 特征未显式设置 combine_mode（空串/缺失）→ 按 or 聚合（and/or 切换生效）"""
        ok, _ = self._combine([False, True], [{'combine_mode': ''}, {'combine_mode': ''}], 'or')
        assert ok is True
        ok, _ = self._combine([False, True], [{}, {}], 'or')
        assert ok is True
        # and 全局下全部满足才通过
        ok, _ = self._combine([True, False], [{'combine_mode': ''}, {'combine_mode': ''}], 'and')
        assert ok is False

    def test_legacy_per_feature_combine_is_ignored(self):
        """即使旧数据残留 combine_mode，也不能覆盖页面节点的统一组合模式。"""
        # 全局 or：旧的逐特征 and 不再改变语义。
        ok, detail = self._combine([True, False], [{}, {'combine_mode': 'and'}], 'or')
        assert ok is True
        assert detail == '#1:True or #2:False'
        # 全局 and：旧的逐特征 or 同样不再改变语义。
        ok, _ = self._combine([False, True], [{}, {'combine_mode': 'or'}], 'and')
        assert ok is False

    def test_negate_flag(self, monkeypatch):
        """结果取反（在 _evaluate_features 层处理）：描述不存在某特征"""
        import core.node_executors.base.page_state as ps_module

        # mock 条件评估：_ok 字段决定匹配结果；假 context 只提供 log
        monkeypatch.setattr(ps_module, 'evaluate_condition', lambda cond, ctx: bool(cond.get('_ok', True)))

        class _FakeCtx:
            def log(self, *args, **kwargs):
                pass

        # 匹配成功 + 取反 → 不匹配
        ok, _ = PageStateNodeExecutor()._evaluate_features(
            [{'condition_type': 'image_exists', 'image_source': 'x', '_ok': True, 'negate': True, 'combine_mode': ''}],
            'and', _FakeCtx())
        assert ok is False
        # 匹配失败 + 取反 → 匹配（页面不存在该图）
        ok, _ = PageStateNodeExecutor()._evaluate_features(
            [{'condition_type': 'image_exists', 'image_source': 'x', '_ok': False, 'negate': True, 'combine_mode': ''}],
            'and', _FakeCtx())
        assert ok is True

    def test_page_features_short_circuit_unless_diagnostics_enabled(self, monkeypatch):
        import core.node_executors.base.page_state as ps_module

        calls = []
        monkeypatch.setattr(ps_module, 'evaluate_condition', lambda cond, _ctx: calls.append(cond['_ok']) or cond['_ok'])

        class _Context:
            def __init__(self, diagnostics=False):
                self.diagnostics = diagnostics
            def log(self, *_args, **_kwargs):
                pass
            def get_setting(self, name, default=None):
                return self.diagnostics if name == 'diagnostic_full_page_evaluation' else default

        features = [
            {'condition_type': 'image_exists', '_ok': False},
            {'condition_type': 'image_exists', '_ok': True},
        ]
        ok, _ = PageStateNodeExecutor()._evaluate_features(features, 'and', _Context())
        assert ok is False
        assert calls == [False]

        calls.clear()
        PageStateNodeExecutor()._evaluate_features(features, 'and', _Context(True))
        assert calls == [False, True]
