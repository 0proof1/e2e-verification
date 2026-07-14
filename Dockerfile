FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

ARG PLAYWRIGHT_VERSION=1.61.0
ARG PYYAML_VERSION=6.0.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    E2E_EVIDENCE_DIR=/evidence

WORKDIR /app

RUN python -m pip install --no-cache-dir "playwright==${PLAYWRIGHT_VERSION}" "PyYAML==${PYYAML_VERSION}" \
    && python -m playwright install --with-deps chromium \
    && useradd --create-home --uid 10001 verifier \
    && mkdir -p /evidence /app \
    && chown -R verifier:verifier /evidence /app /ms-playwright

ARG SOURCE_SHA=unknown
ENV E2E_SOURCE_SHA=${SOURCE_SHA}
LABEL org.opencontainers.image.revision=${SOURCE_SHA}

COPY --chown=verifier:verifier . /app
RUN python -m pip install --no-cache-dir --force-reinstall --no-deps . \
    && e2e-verify model-plan --model-plan examples/model-plan.example.json --provider custom >/tmp/model-plan-smoke.json

USER verifier
VOLUME ["/evidence"]

ENTRYPOINT ["e2e-verify"]
CMD ["doctor"]
