from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.ai_buddy.model import (
    AIBuddyExpert,
    AIBuddyKnowledgeBase,
    AIBuddyMcp,
    AIBuddyModel,
    AIBuddyProvider,
    AIBuddySkill,
)
from backend.plugin.ai_buddy_group.crud.crud_group import ai_buddy_group_dao
from backend.plugin.ai_buddy_group.crud.crud_resource import ai_buddy_group_resource_dao
from backend.plugin.ai_buddy_group.crud.crud_user import ai_buddy_group_user_dao
from backend.plugin.ai_buddy_group.enums import AIBuddyResourceScopeType, AIBuddyResourceType
from backend.plugin.ai_buddy_group.model import AIBuddyGroup
from backend.plugin.ai_buddy_group.schema.group import (
    AIBuddyGroupUserParam,
    CreateAIBuddyGroupParam,
    DeleteAIBuddyGroupParam,
    GetAIBuddyGroupDetail,
    GetAIBuddyGroupUserDetail,
    GetAIBuddyGroupWithResourceDetail,
    UpdateAIBuddyGroupParam,
    UpdateAIBuddyGroupResourceParam,
)


class AIBuddyGroupService:
    """AI 分组服务类"""

    @staticmethod
    async def _validate_user_ids(*, db: AsyncSession, user_ids: list[int]) -> None:
        """
        校验指定用户是否存在

        :param db: 数据库会话
        :param user_ids: 用户 ID 列表
        :return:
        """
        if not user_ids:
            raise errors.RequestError(msg='用户 ID 列表不能为空')
        count = await ai_buddy_group_user_dao.count_existing_users(db, user_ids)
        if count != len(user_ids):
            raise errors.NotFoundError(msg='用户不存在')

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[AIBuddyGroup]:
        """
        获取所有分组

        :param db: 数据库会话
        :return:
        """
        return await ai_buddy_group_dao.get_all(db)

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GetAIBuddyGroupWithResourceDetail:
        """
        获取分组详情

        :param db: 数据库会话
        :param pk: 分组 ID
        :return:
        """
        ai_buddy_group = await ai_buddy_group_dao.get(db, pk)
        if not ai_buddy_group:
            raise errors.NotFoundError(msg='分组不存在')
        resources = await ai_buddy_group_resource_dao.get_by_group_id(db, pk)
        resource_ids = {
            'provider_ids': None,
            'model_ids': None,
            'mcp_ids': None,
            'expert_ids': None,
            'knowledge_ids': None,
            'skill_ids': None,
        }
        for resource in resources:
            field = f'{AIBuddyResourceType(resource.resource_type).name}_ids'
            scope_type = AIBuddyResourceScopeType(resource.scope_type)
            if scope_type == AIBuddyResourceScopeType.none:
                resource_ids[field] = []
            elif scope_type == AIBuddyResourceScopeType.specified:
                resource_ids[field] = resource_ids[field] or []
                resource_ids[field].append(resource.resource_id)
        data = GetAIBuddyGroupDetail.model_validate(ai_buddy_group).model_dump()
        data.update(resource_ids)
        return GetAIBuddyGroupWithResourceDetail(**data)

    @staticmethod
    async def get_list(*, db: AsyncSession, name: str | None) -> dict[str, Any]:
        """
        获取分组列表

        :param db: 数据库会话
        :param name: 分组名称
        :return:
        """
        ai_buddy_group_select = await ai_buddy_group_dao.get_select(name)
        return await paging_data(db, ai_buddy_group_select)

    async def get_user_groups(self, *, db: AsyncSession, user_id: int) -> Sequence[AIBuddyGroup]:
        """
        获取用户所属分组

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        await self._validate_user_ids(db=db, user_ids=[user_id])
        group_ids = await ai_buddy_group_user_dao.get_group_ids_by_user(db, user_id)
        return await ai_buddy_group_dao.get_by_ids(db, group_ids)

    @staticmethod
    async def get_group_users(*, db: AsyncSession, pk: int) -> list[GetAIBuddyGroupUserDetail]:
        """
        获取分组用户

        :param db: 数据库会话
        :param pk: 分组 ID
        :return:
        """
        ai_buddy_group = await ai_buddy_group_dao.get(db, pk)
        if not ai_buddy_group:
            raise errors.NotFoundError(msg='分组不存在')
        users = await ai_buddy_group_user_dao.get_by_group_id(db, pk)
        return [GetAIBuddyGroupUserDetail.model_validate(user) for user in users]

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateAIBuddyGroupParam) -> None:
        """
        创建分组

        :param db: 数据库会话
        :param obj: 创建分组参数
        :return:
        """
        payload = obj.model_dump(mode='json')
        name = payload['name'].strip()
        if not name:
            raise errors.RequestError(msg='分组名称不能为空')
        description = payload['description'].strip() if payload['description'] else None
        payload.update(name=name, description=description)
        if await ai_buddy_group_dao.get_by_name(db, payload['name']):
            raise errors.ConflictError(msg='分组已存在')
        ai_buddy_group = await ai_buddy_group_dao.create(db, CreateAIBuddyGroupParam(**payload))
        await ai_buddy_group_resource_dao.bulk_create(
            db,
            [
                {
                    'group_id': ai_buddy_group.id,
                    'resource_type': AIBuddyResourceType.provider.value,
                    'scope_type': AIBuddyResourceScopeType.all.value,
                    'resource_id': 0,
                },
                {
                    'group_id': ai_buddy_group.id,
                    'resource_type': AIBuddyResourceType.model.value,
                    'scope_type': AIBuddyResourceScopeType.all.value,
                    'resource_id': 0,
                },
                {
                    'group_id': ai_buddy_group.id,
                    'resource_type': AIBuddyResourceType.mcp.value,
                    'scope_type': AIBuddyResourceScopeType.all.value,
                    'resource_id': 0,
                },
                {
                    'group_id': ai_buddy_group.id,
                    'resource_type': AIBuddyResourceType.expert.value,
                    'scope_type': AIBuddyResourceScopeType.all.value,
                    'resource_id': 0,
                },
                {
                    'group_id': ai_buddy_group.id,
                    'resource_type': AIBuddyResourceType.knowledge.value,
                    'scope_type': AIBuddyResourceScopeType.all.value,
                    'resource_id': 0,
                },
                {
                    'group_id': ai_buddy_group.id,
                    'resource_type': AIBuddyResourceType.skill.value,
                    'scope_type': AIBuddyResourceScopeType.all.value,
                    'resource_id': 0,
                },
            ],
        )

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateAIBuddyGroupParam) -> int:
        """
        更新分组

        :param db: 数据库会话
        :param pk: 分组 ID
        :param obj: 更新分组参数
        :return:
        """
        ai_buddy_group = await ai_buddy_group_dao.get(db, pk)
        if not ai_buddy_group:
            raise errors.NotFoundError(msg='分组不存在')
        payload = obj.model_dump(mode='json', exclude_unset=True)
        if 'name' in payload:
            name = payload['name'].strip() if payload['name'] else ''
            if not name:
                raise errors.RequestError(msg='分组名称不能为空')
            payload['name'] = name
        if 'description' in payload:
            payload['description'] = payload['description'].strip() if payload['description'] else None
        if not payload:
            raise errors.RequestError(msg='更新内容不能为空')
        name = payload.get('name')
        if name is not None and ai_buddy_group.name != name and await ai_buddy_group_dao.get_by_name(db, name):
            raise errors.ConflictError(msg='分组已存在')
        return await ai_buddy_group_dao.update(db, pk, payload)

    @staticmethod
    async def update_resources(*, db: AsyncSession, pk: int, obj: UpdateAIBuddyGroupResourceParam) -> int:
        """
        更新分组资源

        :param db: 数据库会话
        :param pk: 分组 ID
        :param obj: 更新分组资源参数
        :return:
        """
        ai_buddy_group = await ai_buddy_group_dao.get(db, pk)
        if not ai_buddy_group:
            raise errors.NotFoundError(msg='分组不存在')

        provider_ids = None if obj.provider_ids is None else list(dict.fromkeys(obj.provider_ids))
        model_ids = None if obj.model_ids is None else list(dict.fromkeys(obj.model_ids))
        mcp_ids = None if obj.mcp_ids is None else list(dict.fromkeys(obj.mcp_ids))
        expert_ids = None if obj.expert_ids is None else list(dict.fromkeys(obj.expert_ids))
        knowledge_ids = None if obj.knowledge_ids is None else list(dict.fromkeys(obj.knowledge_ids))
        skill_ids = None if obj.skill_ids is None else list(dict.fromkeys(obj.skill_ids))
        for resource_ids, model, error_msg in (
            (provider_ids, AIBuddyProvider, '服务商不存在'),
            (model_ids, AIBuddyModel, '模型不存在'),
            (mcp_ids, AIBuddyMcp, 'MCP不存在'),
            (expert_ids, AIBuddyExpert, '专家不存在'),
            (knowledge_ids, AIBuddyKnowledgeBase, '知识库不存在'),
            (skill_ids, AIBuddySkill, '技能不存在'),
        ):
            if not resource_ids:
                continue
            resource_count = await ai_buddy_group_resource_dao.count_existing_resources(db, model, resource_ids)
            if resource_count != len(resource_ids):
                raise errors.NotFoundError(msg=error_msg)

        await ai_buddy_group_resource_dao.delete_by_group_id(db, pk)
        resource_payloads = []
        for resource_type, resource_ids in (
            (AIBuddyResourceType.provider, provider_ids),
            (AIBuddyResourceType.model, model_ids),
            (AIBuddyResourceType.mcp, mcp_ids),
            (AIBuddyResourceType.expert, expert_ids),
            (AIBuddyResourceType.knowledge, knowledge_ids),
            (AIBuddyResourceType.skill, skill_ids),
        ):
            if resource_ids is None:
                resource_payloads.append({
                    'group_id': pk,
                    'resource_type': resource_type.value,
                    'scope_type': AIBuddyResourceScopeType.all.value,
                    'resource_id': 0,
                })
            elif not resource_ids:
                resource_payloads.append({
                    'group_id': pk,
                    'resource_type': resource_type.value,
                    'scope_type': AIBuddyResourceScopeType.none.value,
                    'resource_id': 0,
                })
            else:
                resource_payloads.extend(
                    {
                        'group_id': pk,
                        'resource_type': resource_type.value,
                        'scope_type': AIBuddyResourceScopeType.specified.value,
                        'resource_id': resource_id,
                    }
                    for resource_id in resource_ids
                )
        return await ai_buddy_group_resource_dao.bulk_create(db, resource_payloads)

    async def bind_users(self, *, db: AsyncSession, pk: int, obj: AIBuddyGroupUserParam) -> None:
        """
        绑定分组用户

        :param db: 数据库会话
        :param pk: 分组 ID
        :param obj: 用户 ID 列表
        :return:
        """
        ai_buddy_group = await ai_buddy_group_dao.get(db, pk)
        if not ai_buddy_group:
            raise errors.NotFoundError(msg='分组不存在')
        user_ids = list(dict.fromkeys(obj.user_ids))
        await self._validate_user_ids(db=db, user_ids=user_ids)
        existing_users = await ai_buddy_group_user_dao.get_by_group_and_users(db, pk, user_ids)
        if existing_users:
            raise errors.ConflictError(msg='用户已绑定此分组')
        await ai_buddy_group_user_dao.bulk_create(
            db,
            [{'group_id': pk, 'user_id': user_id} for user_id in user_ids],
        )

    @staticmethod
    async def unbind_users(*, db: AsyncSession, pk: int, obj: AIBuddyGroupUserParam) -> int:
        """
        移除分组用户

        :param db: 数据库会话
        :param pk: 分组 ID
        :param obj: 用户 ID 列表
        :return:
        """
        ai_buddy_group = await ai_buddy_group_dao.get(db, pk)
        if not ai_buddy_group:
            raise errors.NotFoundError(msg='分组不存在')
        user_ids = list(dict.fromkeys(obj.user_ids))
        if not user_ids:
            raise errors.RequestError(msg='用户 ID 列表不能为空')
        return await ai_buddy_group_user_dao.delete_by_group_and_users(db, pk, user_ids)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteAIBuddyGroupParam) -> int:
        """
        批量删除分组

        :param db: 数据库会话
        :param obj: 分组 ID 列表
        :return:
        """
        await ai_buddy_group_user_dao.delete_by_group_ids(db, obj.pks)
        await ai_buddy_group_resource_dao.delete_by_group_ids(db, obj.pks)
        return await ai_buddy_group_dao.delete(db, obj.pks)


ai_buddy_group_service: AIBuddyGroupService = AIBuddyGroupService()
