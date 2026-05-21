# 樟巢螟智能检测系统 —— API 参考

- 版本:1.0.0
- 生成时间:2026-05-21 22:15

> 本文件由 `backend/scripts/export_api_docs.py` 从 FastAPI OpenAPI schema 自动生成。
> 在线交互式文档(可直接试调)见后端的 `/docs`(Swagger UI)。

所有 `/api/v1/**` 接口除登录、注册外均需在请求头携带 `Authorization: Bearer <token>`。

## admin

### `GET /api/v1/admin/users`

**List Users**

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| skip | query | 否 |  |
| limit | query | 否 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `POST /api/v1/admin/users`

**Create User**

响应:

- `201` —— Successful Response
- `422` —— Validation Error

### `PUT /api/v1/admin/users/{user_id}`

**Update User**

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| user_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `DELETE /api/v1/admin/users/{user_id}`

**Delete User**

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| user_id | path | 是 |  |

响应:

- `204` —— Successful Response
- `422` —— Validation Error

## auth

### `POST /api/v1/auth/change-password`

**Change Password**

登录用户修改自己的密码。  
  
流程：校验 old_password → 不匹配返回 401 → 匹配则写入新哈希并提交。  
错误返回 401（与登录失败语义一致：凭证错误）；不主动 invalidate 现有  
JWT（无 server-side session 表），调用方应在前端 logout 后让用户重登。

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `POST /api/v1/auth/login`

**Login**

OAuth2 密码模式登录，返回 JWT access_token

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/auth/me`

**Get Me**

获取当前登录用户信息

响应:

- `200` —— Successful Response

### `POST /api/v1/auth/register`

**Register**

注册新用户。  
  
注意：本接口创建的用户均为普通用户（is_admin=False）。  
管理员账号需要使用 `backend/scripts/create_admin.py` 离线 bootstrap，  
避免之前 "count == 0 -> is_admin=True" 的 race condition（两个并发  
注册请求都能读到 count==0，导致出现多个意外 admin）。  
详见 backend/scripts/README.md。

响应:

- `201` —— Successful Response
- `422` —— Validation Error

## images

### `GET /api/v1/images/{image_id}`

**Get Image File**

获取图片。ownership 通过 get_owned_image 校验。  
  
T3 图片压缩：**默认**返回宽度上限 1920px 的压缩版（JPEG quality≈82），  
无人机原图常达 10-20MB，压缩后通常 200-800KB，前端加载快一个数量级。  
- `max_width=0`：返回未压缩原图（"查看原图"用）  
- `max_width>0`：宽度超过该值才缩放，否则直接发原文件省一次重编码  
- `max_width<0`：拒绝（400），防止 resize 计算出非法尺寸导致 500  
  
用 inline 而非 attachment：浏览器 / antd Image / blob URL 流程都把它  
当成图片直接渲染。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| image_id | path | 是 |  |
| max_width | query | 否 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/images/{image_id}/annotated`

**Get Image Annotated**

获取带检测框标注的图片。ownership 已校验。  
  
T3 图片压缩：检测框始终在**原图分辨率**上绘制以保证坐标精度，绘制  
完成后再按 max_width 统一缩放。  
- `max_width=0`：标注后的全分辨率图  
- `max_width>0`（默认 1920）：标注后缩放到该宽度上限  
- `max_width<0`：拒绝（400）

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| image_id | path | 是 |  |
| max_width | query | 否 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/images/{image_id}/info`

**Get Image Info**

查询单张图片详情。ownership 已校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| image_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/images/{image_id}/thumbnail`

**Get Image Thumbnail**

获取图片缩略图（不存在则返回原图）。ownership 已校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| image_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `POST /api/v1/tasks/{task_id}/images`

**Upload Images**

批量上传图片（上传完成后自动触发AI处理）。  
  
ownership：通过 get_owned_task 校验，无权访问的非 owner 看到 404  
"任务不存在"，与不存在共用同一响应（防资源枚举）。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/tasks/{task_id}/images`

**List Task Images**

查询任务图片列表（包含检测结果）。ownership 已校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |
| skip | query | 否 |  |
| limit | query | 否 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

## nests

### `GET /api/v1/nests/{nest_id}`

**Get Nest Detail**

获取单个虫巢详情（包含来源图片）。  
  
ownership：unique_nests 没有 owner_id，靠 task_id 间接归属。  
用 JOIN 一次性查 nest+task.owner_id，省一次 round-trip。  
不存在 / 无权 都返回 404 + "虫巢不存在"。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| nest_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/tasks/{task_id}/nests`

**Get Task Nests**

获取任务的去重后虫巢列表。ownership 已校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |
| severity | query | 否 |  |
| skip | query | 否 |  |
| limit | query | 否 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/tasks/{task_id}/results`

**Get Task Results**

获取任务检测结果概览。ownership 已校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/tasks/{task_id}/statistics`

**Get Task Statistics**

获取任务详细统计数据。ownership 已校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

## regions

### `GET /api/v1/regions/`

**List Regions**

按 level / parent_id 过滤查询区域（扁平列表）。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| level | query | 否 |  |
| parent_id | query | 否 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `POST /api/v1/regions/`

**Create Region**

创建区域。强校验三级层级关系：  
- city 不能有 parent_id  
- district 的 parent 必须是 city；town 的 parent 必须是 district

响应:

- `201` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/regions/tree`

**Get Region Tree**

返回完整三级树：[{...city, children:[{...district, children:[town]}]}]。

响应:

- `200` —— Successful Response

### `PUT /api/v1/regions/{region_id}`

**Update Region**

重命名区域，并级联刷新自身与所有后代的 full_path。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| region_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `DELETE /api/v1/regions/{region_id}`

**Delete Region**

删除区域。仅当该区域下既无子区域、也无巡检任务时允许。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| region_id | path | 是 |  |

响应:

- `204` —— Successful Response
- `422` —— Validation Error

## reports

### `GET /api/v1/tasks/{task_id}/report.docx`

**Export Task Report Docx**

导出巡检任务 Word 报告。ownership 已由 get_owned_task 校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

## tasks

### `POST /api/v1/tasks/`

**Create Task**

创建巡检任务。owner_id 自动写入当前用户 id。  
  
region_id 必须指向一个 **town（街镇）级** 区域——这强制用户在前端  
选完整的 市→区→街镇 三级，任务不能挂在市/区级。

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/tasks/`

**List Tasks**

查询任务列表。  
  
- 普通用户只能看自己创建的任务；admin 看全部  
- region_id 过滤在数据库层 WHERE 完成（见 TaskService.list_tasks），  
  不是前端对当前页结果再筛

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| skip | query | 否 |  |
| limit | query | 否 |  |
| status | query | 否 |  |
| region_id | query | 否 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/tasks/{task_id}`

**Get Task**

查询任务详情。ownership 由 get_owned_task 依赖校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `DELETE /api/v1/tasks/{task_id}`

**Delete Task**

删除任务。ownership 已通过依赖校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `POST /api/v1/tasks/{task_id}/process`

**Process Task**

触发任务处理（图片AI检测）。ownership 已校验。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

### `GET /api/v1/tasks/{task_id}/status`

**Get Task Status**

查询任务处理状态（前端轮询用，精简返回）。

参数:

| 名称 | 位置 | 必填 | 说明 |
| --- | --- | --- | --- |
| task_id | path | 是 |  |

响应:

- `200` —— Successful Response
- `422` —— Validation Error

## 其他

### `GET /`

**Root**

响应:

- `200` —— Successful Response

### `GET /health`

**Health Check**

响应:

- `200` —— Successful Response

### `GET /metrics`

**Metrics**

Endpoint that serves Prometheus metrics.

响应:

- `200` —— Successful Response
