"""
RS-01A.1 — AssetResolver Protocol + InMemoryAssetResolver

将 asset_id 解析为 AssetRef.uri，不破坏冻结的资产引用设计。
"""

from typing import Protocol, runtime_checkable
from core.schemas.contracts.asset import AssetRef


@runtime_checkable
class AssetResolver(Protocol):
    """将 asset_id 解析为 AssetRef。"""

    def resolve(self, asset_id: str) -> AssetRef:
        ...

    def contains(self, asset_id: str) -> bool:
        ...


class InMemoryAssetResolver:
    """基于 AssetRef[] 的内存解析器。"""

    def __init__(self, assets: list[AssetRef]):
        self._map = {a.asset_id: a for a in assets}

    def resolve(self, asset_id: str) -> AssetRef:
        if asset_id not in self._map:
            raise KeyError(f"Asset 未注册: {asset_id}")
        return self._map[asset_id]

    def contains(self, asset_id: str) -> bool:
        return asset_id in self._map
