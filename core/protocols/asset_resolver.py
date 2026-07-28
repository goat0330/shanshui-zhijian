"""
RS-01A.2 — AssetRegistry (可注册、重复拒绝)

asset_id → AssetRef 的注册/解析/反向查询。
"""

from core.schemas.contracts.asset import AssetRef


class AssetRegistry:
    """可注册的 Asset 仓库。重复 asset_id 拒绝（不静默覆盖）。"""

    def __init__(self, assets: list[AssetRef] | None = None):
        self._map: dict[str, AssetRef] = {}
        if assets:
            for ref in assets:
                self.register(ref)

    def register(self, ref: AssetRef):
        if not ref.asset_id:
            raise ValueError("asset_id 不能为空")
        if ref.asset_id in self._map:
            raise ValueError(
                f"Asset ID 已存在: {ref.asset_id}。"
                f" 使用不同的 asset_id 注册。"
            )
        self._map[ref.asset_id] = ref

    def resolve(self, asset_id: str) -> AssetRef:
        if asset_id not in self._map:
            raise KeyError(f"Asset 未注册: {asset_id}")
        return self._map[asset_id]

    def contains(self, asset_id: str) -> bool:
        return asset_id in self._map

    @property
    def count(self) -> int:
        return len(self._map)

    def __repr__(self) -> str:
        return f"AssetRegistry({len(self._map)} assets)"
