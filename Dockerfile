# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.13-trixie AS dev

ENV VIRTUAL_ENV=/opt/venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH
ENV UV_PROJECT_ENVIRONMENT=$VIRTUAL_ENV
RUN git config --system --add safe.directory '*'
RUN --mount=type=cache,target=/var/cache/apt/ \
    --mount=type=cache,target=/var/lib/apt/ \
    groupadd --gid 1000 user && \
    useradd --create-home --no-log-init --gid 1000 --uid 1000 --shell /usr/bin/bash user && \
    chown user:user /opt/ && \
    apt-get update && apt-get install --no-install-recommends --yes sudo && \
    echo 'user ALL=(root) NOPASSWD:ALL' > /etc/sudoers.d/user && chmod 0440 /etc/sudoers.d/user
USER user
RUN mkdir ~/.history/ && \
    echo 'HISTFILE=~/.history/.bash_history' >> ~/.bashrc && \
    echo 'bind "\"\e[A\": history-search-backward"' >> ~/.bashrc && \
    echo 'bind "\"\e[B\": history-search-forward"' >> ~/.bashrc && \
    echo 'eval "$(starship init bash)"' >> ~/.bashrc

FROM ghcr.io/astral-sh/uv:python3.13-trixie AS production-builder
WORKDIR /build
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv build --wheel && \
    uv venv /opt/gymact && \
    uv pip install --python /opt/gymact/bin/python dist/*.whl

FROM python:3.13-slim-trixie AS production
ENV PATH=/opt/gymact/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY --from=production-builder /opt/gymact /opt/gymact
USER 65532:65532
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()" || exit 1
ENTRYPOINT ["gymact"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
