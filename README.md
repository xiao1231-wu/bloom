# bloom · 美甲搭配师

一个围绕“手部档案 → 智能适配 → 虚拟试戴 → 收藏/分享 → 线下预约”的美甲社区演示项目。

## 启动

需要 Python 3.10 或更新版本。首次使用：

```powershell
git clone https://github.com/xiao1231-wu/bloom.git
cd bloom
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# 手部识别模型独立下载，不纳入本仓库的 MIT 授权范围：
curl.exe -fL https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task -o frontend/vendor/mediapipe/hand_landmarker.task
python backend\app.py
```

浏览器打开 `http://127.0.0.1:8080`。

模型来源及适用条款请查阅 [MediaPipe Hand Landmarker 官方文档](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)。下载失败时，基础社区和搭配功能仍可运行，但自动手部识别不可用，静态试戴使用已有回退模式。

## 开源范围与素材

- 原创代码使用 [MIT License](LICENSE)，Copyright (c) 2026 xiao1231-wu。
- 公开版全部演示图片为程序绘制的几何占位图，不包含原项目照片、爬取图片或第三方帖子正文；视觉效果不代表真实款式。
- 软著资料、内部文档、真实数据库、用户上传、密钥和运行日志不公开。
- 第三方运行时、字体遵循各自许可，不适用本项目 MIT 许可；详见 [第三方说明](frontend/vendor/THIRD_PARTY_NOTICES.md) 和同目录许可证。
- 发布导出工具：`python -m pip install Pillow`，然后 `python scripts/prepare_public_release.py 新的外部目标目录`。工具不会覆盖已有目录或修改原图，Pillow 仅用于导出，不是应用运行依赖。

## 测试

```powershell
python -m unittest discover -s backend -p "test_*.py" -v
```

## 技术栈

- 后端：Python 标准库 `http.server` + SQLite；生产环境头像对象存储使用 `boto3`。
- 前端：原生 HTML/CSS/JavaScript，Third-party 运行时固定在 `frontend/vendor/`。
- 图片：公开版使用本地占位图，社区上传图片保存在 `frontend/uploads/`，SQLite 仅保存访问 URL。

## 用户媒体存储

- 默认把头像写入 `MEDIA_ROOT/avatars/`，社区图片写入 `MEDIA_ROOT/`，数据库只保存访问路径或随机对象键。
- 单机生产部署设置 `APP_ENV=production`、`AVATAR_STORAGE=local` 和持久化的 `MEDIA_ROOT`。
- 使用 S3 兼容对象存储时设置 `AVATAR_STORAGE=s3`，并提供：
  `S3_BUCKET`、`S3_ACCESS_KEY_ID`、`S3_SECRET_ACCESS_KEY`、`S3_REGION`、`AVATAR_PUBLIC_BASE_URL`。
- `S3_ENDPOINT_URL` 用于 S3 兼容服务（如 R2、MinIO、COS、OSS）；使用 AWS S3 时可省略。`AVATAR_PUBLIC_BASE_URL` 应为对用户公开的 CDN 或存储域名。
- 头像仅接受 JPG、PNG、WebP，服务端限制为 2MB；浏览器在上传前会自动居中裁剪并压缩到 512px。

## 认证与安全

- 注册/登录会签发 30 天 Bearer token，前端自动在 API 请求中携带。
- 收藏、发帖、评论、预约、删除和取消等操作都由后端校验用户身份及资源所有权。
- 管理员导入接口需要环境变量 `ADMIN_TOKEN` 和请求头 `X-Admin-Token`。
- 项目仍是本地演示服务；公网部署时应在前方配置 HTTPS、反向代理和请求限流。

## Bloom 生产部署

- 目标域名：`https://bloom.surveycorps.cn`
- 应用服务：`deploy/bloom.service`
- Nginx 配置：`deploy/bloom.nginx.conf` 与 `deploy/bloom-rate-limit.conf`
- 环境变量模板：`deploy/bloom.env.example`
- 每日备份：`deploy/bloom-backup.service` 与 `deploy/bloom-backup.timer`
- 健康检查：`GET /api/health`

生产环境将代码放在 `/opt/bloom/current`，SQLite 与用户上传分别保存在
`/var/lib/bloom/meijia.db` 和 `/var/lib/bloom/uploads/`。前端第三方运行时依赖已固定在
`frontend/vendor/`，页面加载不依赖海外 CDN。

### 管理员导入示例

```powershell
$env:ADMIN_TOKEN = "replace-with-a-long-random-secret"
python backend\app.py
```

`POST /api/admin/import` 时需携带 `X-Admin-Token`。

## 数据与工具

- 款式种子数据：`frontend/assets/comprehensive_styles.json`
- 国内社区帖子种子：`frontend/assets/community/community_posts.json`
- 公开版不附带原项目的图片检索记录和来源清单。
- 合规数据导入工具：`backend/crawler.py`
- 图片管理工具：`backend/photo_manager.py`、`backend/download_photos.py`
- 数据库：`backend/meijia.db`（运行时自动创建）


## 国内美甲社区素材

- 原项目图片未确认公开发布授权，因此公开版本统一替换为原创占位图和示例帖子。
- 可自行替换为有权使用的真实素材；上传前需获得相应授权，公开搜索不等于允许再分发。
- 项目没有破解登录、验证码、付费墙或站点防盗链。

## 遗留资源说明

旧的单文件页面 `standalone.html` 与重复的 `comprehensive_data.js` 已移除。当前唯一前端入口为 `frontend/index.html`，款式数据唯一来源为 `comprehensive_styles.json`。
