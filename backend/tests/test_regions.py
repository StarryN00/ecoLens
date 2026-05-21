"""行政区域 CRUD + 任务-区域集成测试（T1 多级目录架构）。

通用 fixture（client / auth_headers / admin_auth_headers）见 tests/conftest.py。
"""

import uuid


def _create_region(client, headers, name, level, parent_id=None):
    body = {"name": name, "level": level}
    if parent_id:
        body["parent_id"] = parent_id
    return client.post("/api/v1/regions/", json=body, headers=headers)


def _make_full_tree(client, admin_headers):
    """建一条完整 市/区/街镇 链，返回 (city_id, district_id, town_id)。"""
    sfx = uuid.uuid4().hex[:6]
    city = _create_region(client, admin_headers, f"市{sfx}", "city")
    assert city.status_code == 201, city.text
    cid = city.json()["id"]
    district = _create_region(client, admin_headers, f"区{sfx}", "district", cid)
    assert district.status_code == 201, district.text
    did = district.json()["id"]
    town = _create_region(client, admin_headers, f"镇{sfx}", "town", did)
    assert town.status_code == 201, town.text
    return cid, did, town.json()["id"]


def _find_node(nodes, node_id):
    for n in nodes:
        if n["id"] == node_id:
            return n
        found = _find_node(n["children"], node_id)
        if found:
            return found
    return None


class TestRegionCRUD:
    """区域三级树的增删改查 + 层级约束。"""

    def test_create_three_levels(self, client, admin_auth_headers):
        cid, did, tid = _make_full_tree(client, admin_auth_headers)
        assert cid and did and tid

    def test_create_requires_admin(self, client, auth_headers):
        """普通用户不能创建区域。"""
        r = _create_region(client, auth_headers, "无权市", "city")
        assert r.status_code == 403

    def test_city_cannot_have_parent(self, client, admin_auth_headers):
        city = _create_region(client, admin_auth_headers, "父市", "city").json()
        r = _create_region(client, admin_auth_headers, "非法市", "city", city["id"])
        assert r.status_code == 400

    def test_district_requires_parent(self, client, admin_auth_headers):
        r = _create_region(client, admin_auth_headers, "孤儿区", "district")
        assert r.status_code == 400

    def test_town_parent_must_be_district(self, client, admin_auth_headers):
        """town 的父节点必须是 district，给 city 应被拒。"""
        city = _create_region(client, admin_auth_headers, "错配市", "city").json()
        r = _create_region(
            client, admin_auth_headers, "错配镇", "town", city["id"]
        )
        assert r.status_code == 400

    def test_bad_level_rejected(self, client, admin_auth_headers):
        r = _create_region(client, admin_auth_headers, "省", "province")
        assert r.status_code == 400

    def test_full_path_computed(self, client, admin_auth_headers):
        sfx = uuid.uuid4().hex[:6]
        city = _create_region(
            client, admin_auth_headers, f"甲市{sfx}", "city"
        ).json()
        district = _create_region(
            client, admin_auth_headers, f"乙区{sfx}", "district", city["id"]
        ).json()
        town = _create_region(
            client, admin_auth_headers, f"丙镇{sfx}", "town", district["id"]
        ).json()
        assert town["full_path"] == f"甲市{sfx}/乙区{sfx}/丙镇{sfx}"

    def test_tree_readable_by_normal_user(
        self, client, admin_auth_headers, auth_headers
    ):
        _make_full_tree(client, admin_auth_headers)
        r = client.get("/api/v1/regions/tree", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()["items"]
        # 至少有一个 city 带 children
        assert any(c["children"] for c in items)

    def test_list_filter_by_level(self, client, admin_auth_headers):
        _make_full_tree(client, admin_auth_headers)
        r = client.get(
            "/api/v1/regions/?level=town", headers=admin_auth_headers
        )
        assert r.status_code == 200
        assert all(x["level"] == "town" for x in r.json()["items"])

    def test_rename_cascades_full_path(self, client, admin_auth_headers):
        """改市名 -> 该市下街镇的 full_path 应级联更新。"""
        sfx = uuid.uuid4().hex[:6]
        city = _create_region(
            client, admin_auth_headers, f"旧市{sfx}", "city"
        ).json()
        district = _create_region(
            client, admin_auth_headers, f"某区{sfx}", "district", city["id"]
        ).json()
        town = _create_region(
            client, admin_auth_headers, f"某镇{sfx}", "town", district["id"]
        ).json()
        r = client.put(
            f"/api/v1/regions/{city['id']}",
            json={"name": f"新市{sfx}"},
            headers=admin_auth_headers,
        )
        assert r.status_code == 200
        tree = client.get(
            "/api/v1/regions/tree", headers=admin_auth_headers
        ).json()["items"]
        town_node = _find_node(tree, town["id"])
        assert town_node is not None
        assert town_node["full_path"].startswith(f"新市{sfx}/")

    def test_delete_region_with_children_rejected(
        self, client, admin_auth_headers
    ):
        cid, _, _ = _make_full_tree(client, admin_auth_headers)
        r = client.delete(
            f"/api/v1/regions/{cid}", headers=admin_auth_headers
        )
        assert r.status_code == 400

    def test_delete_empty_region_ok(self, client, admin_auth_headers):
        city = _create_region(
            client, admin_auth_headers, f"待删市{uuid.uuid4().hex[:6]}", "city"
        ).json()
        r = client.delete(
            f"/api/v1/regions/{city['id']}", headers=admin_auth_headers
        )
        assert r.status_code == 204


class TestTaskRegionIntegration:
    """任务创建强制完整三级区域 + 按区域筛选。"""

    def test_create_task_without_region_422(self, client, auth_headers):
        """region_id 缺失 -> pydantic 422（第一道强制）。"""
        r = client.post(
            "/api/v1/tasks/",
            json={"task_name": "无区域任务"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_create_task_region_must_be_town(
        self, client, auth_headers, admin_auth_headers
    ):
        """region_id 指向 city（非 town）-> 400（第二道强制）。"""
        city = _create_region(
            client, admin_auth_headers, f"市X{uuid.uuid4().hex[:6]}", "city"
        ).json()
        r = client.post(
            "/api/v1/tasks/",
            json={"task_name": "市级任务", "region_id": city["id"]},
            headers=auth_headers,
        )
        assert r.status_code == 400

    def test_create_task_nonexistent_region_400(self, client, auth_headers):
        r = client.post(
            "/api/v1/tasks/",
            json={"task_name": "幽灵区域", "region_id": "no-such-region-id"},
            headers=auth_headers,
        )
        assert r.status_code == 400

    def test_create_task_with_town_ok(
        self, client, auth_headers, admin_auth_headers
    ):
        _, _, town_id = _make_full_tree(client, admin_auth_headers)
        r = client.post(
            "/api/v1/tasks/",
            json={"task_name": "正常任务", "region_id": town_id},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["region_id"] == town_id
        assert body["region_path"]  # 完整 市/区/镇 路径非空

    def test_list_tasks_filter_by_region(
        self, client, auth_headers, admin_auth_headers
    ):
        _, _, town_a = _make_full_tree(client, admin_auth_headers)
        _, _, town_b = _make_full_tree(client, admin_auth_headers)
        client.post(
            "/api/v1/tasks/",
            json={"task_name": "A镇任务", "region_id": town_a},
            headers=auth_headers,
        )
        # 按 town_b 过滤 -> 结果里不应出现 town_a 的任务
        r = client.get(
            f"/api/v1/tasks/?region_id={town_b}", headers=auth_headers
        )
        assert r.status_code == 200
        assert all(t["region_id"] == town_b for t in r.json()["items"])

    def test_delete_region_with_task_rejected(
        self, client, auth_headers, admin_auth_headers
    ):
        _, _, town_id = _make_full_tree(client, admin_auth_headers)
        client.post(
            "/api/v1/tasks/",
            json={"task_name": "占位任务", "region_id": town_id},
            headers=auth_headers,
        )
        r = client.delete(
            f"/api/v1/regions/{town_id}", headers=admin_auth_headers
        )
        assert r.status_code == 400
