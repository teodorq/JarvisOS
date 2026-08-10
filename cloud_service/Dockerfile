FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/jarvis \
    PORT=8000

WORKDIR /srv/jarvis
COPY cloud_service/requirements.txt ./cloud_service/requirements.txt
RUN pip install --no-cache-dir --requirement cloud_service/requirements.txt

COPY --chown=10001:0 cloud_service ./cloud_service
COPY --chown=10001:0 app/cloud ./app/cloud
COPY --chown=10001:0 app/ai/actions.py ./app/ai/actions.py
COPY --chown=10001:0 app/ai/planner_llm.py ./app/ai/planner_llm.py
COPY --chown=10001:0 app/ai/commands ./app/ai/commands

EXPOSE 8000
USER 10001

CMD ["python", "-m", "cloud_service.main"]
