# Education OS API host. Build context is the repo root; api.Dockerfile.dockerignore beside this file applies (BuildKit):
#   docker build -f infra/docker/api.Dockerfile -t eos-api .
FROM python:3.12-slim
WORKDIR /repo
COPY packages/core packages/core
COPY packages/testing packages/testing
COPY platform platform
# modules and integrations: the enabled ones are installed below, and the API reads academy profiles,
# plans and every permission catalogue from the repo tree
COPY modules modules
COPY integrations integrations
COPY apps/backend apps/backend
COPY tools/scripts/enabled-modules.py tools/scripts/enabled-modules.py
# Everything apps/backend/config/modules.enabled.yaml enables (tools/scripts/enabled-modules.py).
RUN pip install --no-cache-dir pyyaml \
 && pip install --no-cache-dir -e packages/core -e packages/testing \
      $(python tools/scripts/enabled-modules.py install --pip) -e apps/backend
ENV EOS_REPO_ROOT=/repo EOS_DEV_MODE=false
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" || exit 1
CMD ["uvicorn", "eos_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
