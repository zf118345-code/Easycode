"""page_state 执行器特征归一化测试：新条件结构（condition_type）与旧结构（feature_type）兼容"""

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
        assert cond['type'] == 'text_contains'
        assert cond['target_text'] == '今日特惠'
        # 组合/取反由执行器在特征层消费（_evaluate_features 读 feature.negate / combine_mode），不进条件参数
        assert 'negate' not in cond
        assert 'combine_mode' not in cond

    def test_new_image_feature_structure(self):
        feature = {'condition_type': 'image_exists', 'image_source': 'shop_btn', 'threshold': 85}
        cond = PageStateNodeExecutor._build_condition(feature)
        assert cond['type'] == 'image_exists'
        assert cond['image_source'] == 'shop_btn'
        assert cond['threshold'] == 85

    def test_legacy_structure_with_params(self):
        """旧结构：feature_type + params 嵌套（迁移前的存量数据）"""
        feature = {'feature_type': 'image_exists', 'params': {'template': 'shop_btn', 'threshold': 0.8}}
        cond = PageStateNodeExecutor._build_condition(feature)
        assert cond['type'] == 'image_exists'
        assert cond['template'] == 'shop_btn'
        assert cond['threshold'] == 0.8

    def test_legacy_flat_structure(self):
        """旧结构平铺形态（无 params 嵌套）"""
        feature = {'type': 'text_contains', 'text': '充值'}
        cond = PageStateNodeExecutor._build_condition(feature)
        assert cond['type'] == 'text_contains'
        assert cond['text'] == '充值'

    def test_default_type_fallback(self):
        cond = PageStateNodeExecutor._build_condition({})
        assert cond['type'] == 'image_exists'


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
    """特征组合模式：全局 and/or 与逐特征 combine_mode 的聚合逻辑"""

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

    def test_explicit_combine_overrides_global(self):
        """特征显式设置 combine_mode 时覆盖全局模式（首条特征的组合方式不生效，从第 2 条起）"""
        # 全局 or，但第 2 条显式 and → 两条都必须满足
        ok, detail = self._combine([True, False], [{}, {'combine_mode': 'and'}], 'or')
        assert ok is False
        assert '(and)#2' in detail
        # 全局 and，第 2 条显式 or → or 生效
        ok, _ = self._combine([False, True], [{}, {'combine_mode': 'or'}], 'and')
        assert ok is True

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
