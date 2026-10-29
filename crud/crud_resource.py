from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.common.model import Base
from backend.plugin.ai_buddy_group.model import AIBuddyGroupResource
from backend.utils.timezone import timezone


class CRUDAIBuddyGroupResource(CRUDPlus[AIBuddyGroupResource]):
    """AI 分组资源数据库操作类"""

    @staticmethod
    async def count_existing_resources(db: AsyncSession, model: type[Base], resource_ids: list[int]) -> int:
        """
        统计指定类型中仍有效的资源

        :param db: 数据库会话
        :param model: 资源模型
        :param resource_ids: 资源 ID 列表
        :return:
        """
        stmt = select(func.count()).select_from(model).where(model.id.in_(resource_ids), model.deleted == 0)
        return (await db.execute(stmt)).scalar_one()

    async def get_by_group_id(self, db: AsyncSession, group_id: int) -> Sequence[AIBuddyGroupResource]:
        """
        获取分组资源

        :param db: 数据库会话
        :param group_id: 分组 ID
        :return:
        """
        return await self.select_models(db, group_id=group_id, deleted=0)

    async def get_by_group_ids(self, db: AsyncSession, group_ids: list[int]) -> Sequence[AIBuddyGroupResource]:
        """
        批量获取分组资源

        :param db: 数据库会话
        :param group_ids: 分组 ID 列表
        :return:
        """
        return await self.select_models(db, group_id__in=group_ids, deleted=0)

    async def bulk_create(self, db: AsyncSession, objs: list[dict[str, Any]]) -> int:
        """
        批量创建分组资源

        :param db: 数据库会话
        :param objs: 分组资源列表
        :return:
        """
        now = timezone.now()
        await self.bulk_create_models(db, [{**obj, 'created_time': now} for obj in objs])
        return len(objs)

    async def delete_by_group_id(self, db: AsyncSession, group_id: int) -> int:
        """
        删除分组资源

        :param db: 数据库会话
        :param group_id: 分组 ID
        :return:
        """
        return await self.delete_model_by_column(
            db,
            allow_multiple=True,
            logical_deletion=True,
            deleted_flag_column='deleted',
            deleted_flag_value=self.model.id,
            deleted_at_column='deleted_time',
            deleted_at_factory=timezone.now(),
            group_id=group_id,
            deleted=0,
        )

    async def delete_by_group_ids(self, db: AsyncSession, group_ids: list[int]) -> int:
        """
        批量删除分组资源

        :param db: 数据库会话
        :param group_ids: 分组 ID 列表
        :return:
        """
        return await self.delete_model_by_column(
            db,
            allow_multiple=True,
            logical_deletion=True,
            deleted_flag_column='deleted',
            deleted_flag_value=self.model.id,
            deleted_at_column='deleted_time',
            deleted_at_factory=timezone.now(),
            group_id__in=group_ids,
            deleted=0,
        )


ai_buddy_group_resource_dao: CRUDAIBuddyGroupResource = CRUDAIBuddyGroupResource(AIBuddyGroupResource)
