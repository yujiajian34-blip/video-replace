# 视频角色替换工具

## 最短使用方式

1. 安装 Python 3.10+
2. 解压压缩包
3. 双击 `RUN.bat`

首次运行会自动创建 `.venv` 并安装依赖，完成后会自动打开：

`http://127.0.0.1:5001`

## macOS 使用方式

1. 安装 Python 3.10+
2. 解压压缩包
3. 首次先双击 `setup.command`
4. 安装完成后双击 `run.command`

如果系统提示没有权限，可以先在终端执行：

`chmod +x setup.command run.command`

然后再次双击，或者在终端运行：

`./setup.command`

`./run.command`

## 如果首次运行失败

先双击 `SETUP.bat`，等依赖安装完成后，再双击 `RUN.bat`。

## 说明

- `RUN.bat`：启动程序
- `SETUP.bat`：初始化环境
- `START_HERE.bat`：备用启动入口
- `backend/`：后端
- `frontend/`：前端
- `data/`：本地数据
- `results/`：生成结果目录
- `uploads/`：上传目录

## 注意

- 默认端口：`5001`
- 首次安装依赖需要联网
- 工具本身调用外部接口，使用时也需要联网

## API 密钥配置

项目默认从环境变量读取第三方接口密钥，建议在本地创建 `.env`（参考 `.env.example`）并填入：

- `DOUBAO_API_TOKEN`
- `GEMINI_API_TOKEN`
- `APIFY_API_TOKEN`
