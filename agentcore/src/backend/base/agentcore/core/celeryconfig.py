# celeryconfig.py
import os

agentcore_redis_host = os.environ.get("AGENTCORE_REDIS_HOST")
agentcore_redis_port = os.environ.get("AGENTCORE_REDIS_PORT")
# broker default user

if agentcore_redis_host and agentcore_redis_port:
    broker_url = f"redis://{agentcore_redis_host}:{agentcore_redis_port}/0"
    result_backend = f"redis://{agentcore_redis_host}:{agentcore_redis_port}/0"
else:
    # RabbitMQ
    mq_user = os.environ.get("RABBITMQ_DEFAULT_USER", "agentcore")
    mq_password = os.environ.get("RABBITMQ_DEFAULT_PASS", "agentcore")
    broker_url = os.environ.get("BROKER_URL", f"amqp://{mq_user}:{mq_password}@localhost:5672//")
    result_backend = os.environ.get("RESULT_BACKEND", "redis://localhost:6379/0")
# tasks should be json or pickle
accept_content = ["json", "pickle"]
