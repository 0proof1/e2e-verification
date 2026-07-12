FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    E2E_EVIDENCE_DIR=/evidence

WORKDIR /app

RUN python -m pip install --no-cache-dir "playwright>=1.49" "PyYAML>=6.0" \
    && python -m playwright install --with-deps chromium \
    && useradd --create-home --uid 10001 verifier \
    && mkdir -p /evidence /app \
    && chown -R verifier:verifier /evidence /app /ms-playwright

COPY --chown=verifier:verifier . /app
RUN python -m pip install --no-cache-dir --no-deps .

USER verifier
VOLUME ["/evidence"]

ENTRYPOINT ["e2e-verify"]
CMD ["doctor"]
