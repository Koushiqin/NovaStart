FROM python:3.12-slim

WORKDIR /app

# 先装依赖，充分利用镜像层缓存（走阿里云镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r requirements.txt

# 再拷业务代码（.dockerignore 排除 .venv/.env/__pycache__）
COPY . .

EXPOSE 8000

# 启动流程（shell 形式内联，不新增脚本文件）：
#   1) alembic upgrade head 建/升级表结构
#   2) 后台起 uvicorn
#   3) 轮询 /health 直到服务就绪，POST 一次 /dev/reset-seed 灌入演示数据
#   4) wait 把 uvicorn 拉回前台，保证容器随其退出
CMD alembic upgrade head \
    && uvicorn app.main:app --host 0.0.0.0 --port 8000 & \
    until python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)" 2>/dev/null; do sleep 1; done \
    && python -c "import urllib.request;urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/dev/reset-seed',method='POST'))"; \
    wait
