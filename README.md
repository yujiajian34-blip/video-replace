# 视频角色替换工作台

一个基于 Flask 的本地 Web 工具，用于把参考视频中的人物替换成指定角色，并串联完成：

- 视频来源选择（Google Sheets、直链、TikTok 链接、本地上传）
- Gemini 视频分析与角色适配判断
- 豆包 Seedance 角色替换任务创建
- 单任务或并发批量任务轮询
- 结果下载、本地角色库、提示词配置持久化

启动后默认访问：`http://127.0.0.1:5001`

## 功能概览

- 支持 4 种视频输入方式
  - Google Sheets 下拉选择
  - 直接填写可访问的视频 URL
  - 粘贴 TikTok 链接后自动通过 Apify 解析下载地址
  - 上传本地视频文件
- 支持 1 到 3 张角色参考图
- Gemini 先分析原视频剧情、角色关系和适配度，再决定是否继续生成
- 当角色不适配时，可选择“强制生成”继续执行
- 支持并发批量创建多个生成任务
- 自动轮询任务状态，成功后可下载结果视频
- 自动保存角色库、角色预设和提示词配置到本地 `data/` 目录
- 超过 15 秒的视频会先通过 `ffmpeg` 自动加速，再上传到 Cloudflare R2

## 技术栈

- 后端：Python、Flask、Flask-CORS、Requests、Boto3
- 前端：原生 HTML / CSS / JavaScript
- 外部服务
  - Gemini：用于视频分析和角色映射
  - 豆包 Seedance：用于生成角色替换视频
  - Apify：用于解析 TikTok 视频直链
  - Cloudflare R2：用于上传预处理后的视频素材

## 目录结构

```text
.
├─ backend/
│  ├─ app.py
│  ├─ config.py
│  └─ services/
│     └─ video_service.py
├─ frontend/
│  ├─ index.html
│  └─ api-base.js
├─ data/
│  ├─ batch_tasks.json
│  ├─ prompt_config.json
│  ├─ role_library.json
│  └─ role_preset.json
├─ results/
├─ temp/
├─ uploads/
├─ .env.example
├─ requirements.txt
├─ RUN.bat
├─ SETUP.bat
├─ run.command
└─ setup.command
```

## 环境要求

- Python 3.10+
- `ffmpeg` 和 `ffprobe`
  - 项目会调用 `ffprobe` 读取视频时长
  - 超过 15 秒的视频会调用 `ffmpeg` 自动加速
- 可访问外部服务的网络环境

如果本机没有安装 `ffmpeg` / `ffprobe`，分析或创建任务前的视频预处理会失败。

## 安装与启动

### Windows

1. 安装 Python 3.10+
2. 双击 `SETUP.bat`
3. 安装完成后双击 `RUN.bat`

首次运行会自动创建 `.venv` 并安装依赖。启动后浏览器会自动打开：

```text
http://127.0.0.1:5001
```

### macOS

1. 安装 Python 3.10+
2. 首次运行先执行 `setup.command`
3. 再执行 `run.command`

如果系统提示无权限，可先在终端执行：

```bash
chmod +x setup.command run.command
./setup.command
./run.command
```

### 命令行方式

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python backend/app.py
```

PowerShell 也可以这样启动：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\backend\app.py
```

## 配置说明

项目的配置入口在 `backend/config.py`，支持通过环境变量覆盖默认值。

参考变量见 `.env.example`：

- `DOUBAO_API_URL`
- `DOUBAO_MODEL`
- `DOUBAO_API_TOKEN`
- `GEMINI_API_URL`
- `GEMINI_MODEL`
- `GEMINI_API_TOKEN`
- `APIFY_API_TOKEN`
- `R2_ENDPOINT`
- `R2_BUCKET`
- `R2_PUBLIC_BASE_URL`
- `R2_REGION`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

注意：

- 当前代码里没有自动加载 `.env` 文件的逻辑，`.env.example` 主要用于查看变量名
- 如果你希望用环境变量覆盖配置，需要在启动前先设置系统环境变量，或者直接修改 `backend/config.py`
- `R2_ACCESS_KEY_ID` 和 `R2_SECRET_ACCESS_KEY` 如果未正确配置，视频上传会失败

PowerShell 示例：

```powershell
$env:DOUBAO_API_TOKEN="your-token"
$env:GEMINI_API_TOKEN="your-token"
$env:APIFY_API_TOKEN="your-token"
$env:R2_ACCESS_KEY_ID="your-key"
$env:R2_SECRET_ACCESS_KEY="your-secret"
.\.venv\Scripts\python.exe .\backend\app.py
```

## 使用流程

1. 选择视频来源
   - 从 Google Sheets 选择
   - 输入可直接访问的视频 URL
   - 粘贴 TikTok 链接自动解析
   - 或上传本地视频
2. 填写 1 到 3 张角色参考图 URL
3. 填写角色预设，描述身份、关系、年龄层和情绪功能
4. 选择并发数量
   - `1` 表示单任务
   - `2-10` 会进入批量任务模式
5. 点击“开始角色替换”
6. 系统先调用 Gemini 分析适配度
7. 适配成功后调用豆包 Seedance 创建任务
8. 轮询任务状态，完成后下载结果视频到 `results/`

## 数据持久化

项目会把部分运行数据保存在本地：

- `data/role_library.json`
  - 保存角色图和对应的角色预设
- `data/role_preset.json`
  - 保存当前编辑中的角色预设
- `data/prompt_config.json`
  - 保存 Gemini / Doubao 的提示词模板
- `data/batch_tasks.json`
  - 保存批量任务的任务 ID 和状态

运行过程中还会使用：

- `uploads/`：本地上传的视频
- `temp/`：下载和预处理中的临时文件
- `results/`：最终下载的视频结果

## 主要接口

后端默认运行在 `0.0.0.0:5001`，主要接口如下：

- `POST /api/upload_local`
  - 上传本地视频
- `POST /api/analyze`
  - 调用 Gemini 分析视频与角色适配度
- `POST /api/create_task`
  - 创建单个豆包 Seedance 任务
- `GET /api/status/<task_id>`
  - 查询单个任务状态
- `POST /api/download`
  - 下载生成视频到本地 `results/`
- `GET /api/sheets/videos`
  - 读取 Google Sheets 中的视频链接
- `POST /api/tiktok/resolve`
  - 解析 TikTok 链接
- `GET /api/roles`
  - 获取角色库
- `POST /api/roles`
  - 保存角色到角色库
- `DELETE /api/roles/<role_id>`
  - 删除角色
- `GET /api/preset`
  - 读取角色预设
- `POST /api/preset`
  - 保存角色预设
- `GET /api/prompt_config`
  - 读取提示词配置
- `POST /api/prompt_config`
  - 更新提示词配置
- `POST /api/batch_create`
  - 并发创建批量任务
- `GET /api/batch_status/<batch_id>`
  - 查询批量任务状态
- `GET /api/video_proxy`
  - 代理远程视频预览

## 已知约束

- 依赖多个外部服务，任何一个服务不可用都可能导致流程中断
- TikTok 解析依赖 Apify Token
- Google Sheets 数据源在后端写死了表格 ID 和 `gid`
- 超过 15 秒的视频会被自动加速到 15 秒以内
- 当前默认端口为 `5001`
- 默认以调试模式启动 Flask：`debug=True`

## 常见问题

### 1. 双击 `RUN.bat` 没反应

先单独执行一次 `SETUP.bat`，确认虚拟环境和依赖已经安装完成。

### 2. 分析时报错，提示视频处理失败

优先检查：

- `ffmpeg` / `ffprobe` 是否已安装并可在命令行直接运行
- 视频 URL 是否可直接访问
- R2 配置是否正确

### 3. TikTok 链接无法解析

通常需要检查：

- `APIFY_API_TOKEN` 是否有效
- 当前网络是否可以访问 Apify 和 TikTok 相关资源

### 4. 创建任务后一直没有结果

优先检查：

- 豆包接口地址和 Token 是否正确
- 传入的角色图 URL 是否可被外部服务访问
- 外部生成接口是否返回了可用的 `video_url`

## 开发备注

- 前端页面文件：`frontend/index.html`
- 后端入口：`backend/app.py`
- 视频处理服务：`backend/services/video_service.py`
- 配置文件：`backend/config.py`

如果你准备继续维护这个项目，建议下一步优先做两件事：

1. 增加 `.env` 自动加载能力，避免只改 `backend/config.py`
2. 把当前写死的 Google Sheets 参数、端口和外部服务配置进一步抽到环境变量
