"""知识库申请服务测试。"""
import pytest

from app.api.v1.auth import UserInfo
from app.models.kb_request import KbRequest
from app.services import kb_request_service


class _FakeScalarResult:
    """模拟 SQLAlchemy scalars() 返回值。"""

    def __init__(self, items):
        self._items = items

    def first(self):
        """返回首条结果。"""
        return self._items[0] if self._items else None

    def all(self):
        """返回全部结果。"""
        return self._items


class _FakeResult:
    """模拟 SQLAlchemy execute() 返回值。"""

    def __init__(self, items):
        self._items = items

    def scalars(self):
        """返回模拟标量结果。"""
        return _FakeScalarResult(self._items)


class _FakeSession:
    """模拟数据库会话。"""

    def __init__(self, query_items=None):
        self.query_items = query_items or []
        self.items: list[KbRequest] = []
        self.commits = 0
        self.next_id = 1

    async def execute(self, stmt):
        """返回预设查询结果。"""
        return _FakeResult(self.query_items)

    def add(self, item):
        """记录新增对象。"""
        item.id = self.next_id
        self.next_id += 1
        self.items.append(item)

    async def commit(self):
        """记录提交次数。"""
        self.commits += 1

    async def refresh(self, item):
        """模拟刷新。"""
        return item

    async def get(self, model, item_id):
        """按 ID 取出模拟记录。"""
        for item in self.items:
            if item.id == item_id:
                return item
        return None


@pytest.fixture
def demo_user():
    """返回普通用户信息。"""
    return UserInfo(
        user_id="u1",
        username="alice",
        role="user",
        status="active",
        organization="R&D",
    )


@pytest.fixture
def demo_admin():
    """返回管理员用户信息。"""
    return UserInfo(
        user_id="admin",
        username="admin",
        role="admin",
        status="active",
        organization="R&D",
    )


@pytest.mark.asyncio
async def test_create_request_persists_pending_record(demo_user):
    """普通用户提交申请后应落为 pending。"""
    session = _FakeSession([])

    record = await kb_request_service.create_request(
        session,
        demo_user,
        "比赛资料库",
        "放比赛资料",
        "比赛需要新的资料库",
    )

    assert record.id == 1
    assert record.status == kb_request_service.PENDING_STATUS
    assert record.requested_name == "比赛资料库"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_create_request_rejects_duplicate_pending(demo_user):
    """同名待处理申请应被拦截。"""
    session = _FakeSession([
        KbRequest(
            id=1,
            requester_user_id="u1",
            requester_username="alice",
            requester_organization="R&D",
            requested_name="比赛资料库",
            requested_description="",
            request_reason="",
            status=kb_request_service.PENDING_STATUS,
            reviewer_user_id="",
            reviewer_username="",
            review_reason="",
            approved_kb_id="",
            approved_kb_name="",
            create_error="",
            created_at="2026-08-04T00:00:00+08:00",
            updated_at="2026-08-04T00:00:00+08:00",
        )
    ])

    with pytest.raises(kb_request_service.KbRequestError) as exc:
        await kb_request_service.create_request(
            session,
            demo_user,
            "比赛资料库",
            "放比赛资料",
            "比赛需要新的资料库",
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_approve_request_marks_approved_only(demo_admin):
    """审批通过后只应更新为 approved，不直接创建知识库。"""
    session = _FakeSession([])
    request = KbRequest(
        id=1,
        requester_user_id="u1",
        requester_username="alice",
        requester_organization="R&D",
        requested_name="比赛资料库",
        requested_description="放比赛资料",
        request_reason="比赛需要新的资料库",
        status=kb_request_service.PENDING_STATUS,
        reviewer_user_id="",
        reviewer_username="",
        review_reason="",
        approved_kb_id="",
        approved_kb_name="",
        create_error="",
        created_at="2026-08-04T00:00:00+08:00",
        updated_at="2026-08-04T00:00:00+08:00",
    )
    session.items.append(request)

    result = await kb_request_service.approve_request(session, 1, demo_admin)

    assert result["status"] == kb_request_service.APPROVED_STATUS
    assert result["approved_kb_id"] == ""
    assert result["approved_kb_name"] == ""
    assert result["create_error"] == ""
    assert session.commits == 1


@pytest.mark.asyncio
async def test_approve_request_rejects_non_pending(demo_admin):
    """非待审核状态不能再次审批。"""
    session = _FakeSession([])
    request = KbRequest(
        id=1,
        requester_user_id="u1",
        requester_username="alice",
        requester_organization="R&D",
        requested_name="比赛资料库",
        requested_description="放比赛资料",
        request_reason="比赛需要新的资料库",
        status=kb_request_service.APPROVED_STATUS,
        reviewer_user_id="admin",
        reviewer_username="admin",
        review_reason="",
        approved_kb_id="",
        approved_kb_name="",
        create_error="",
        created_at="2026-08-04T00:00:00+08:00",
        updated_at="2026-08-04T00:00:00+08:00",
    )
    session.items.append(request)

    with pytest.raises(kb_request_service.KbRequestError) as exc:
        await kb_request_service.approve_request(session, 1, demo_admin)

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_reject_request_updates_status(demo_admin):
    """驳回申请应写入驳回原因。"""
    session = _FakeSession([])
    request = KbRequest(
        id=1,
        requester_user_id="u1",
        requester_username="alice",
        requester_organization="R&D",
        requested_name="比赛资料库",
        requested_description="放比赛资料",
        request_reason="比赛需要新的资料库",
        status=kb_request_service.PENDING_STATUS,
        reviewer_user_id="",
        reviewer_username="",
        review_reason="",
        approved_kb_id="",
        approved_kb_name="",
        create_error="",
        created_at="2026-08-04T00:00:00+08:00",
        updated_at="2026-08-04T00:00:00+08:00",
    )
    session.items.append(request)

    result = await kb_request_service.reject_request(session, 1, demo_admin, "名称不符合规范")

    assert result["status"] == kb_request_service.REJECTED_STATUS
    assert result["review_reason"] == "名称不符合规范"
