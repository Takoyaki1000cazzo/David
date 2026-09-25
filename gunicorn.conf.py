# Gunicorn 本番用設定
# 使い方: gunicorn config.wsgi:application -c gunicorn.conf.py
# (compose.prod.yaml からも参照される)

bind = "0.0.0.0:8000"
workers = 3
worker_class = "sync"
timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = "info"
