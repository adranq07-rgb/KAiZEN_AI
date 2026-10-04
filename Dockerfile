FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 KAIZEN_BIND=0.0.0.0 PORT=8768 KAIZEN_DATA_DIR=/var/lib/kaizen/data KAIZEN_LOG_DIR=/var/lib/kaizen/logs
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY core/ core/
COPY accounting/ accounting/
COPY memory/ memory/
COPY learning/ learning/
COPY models/ models/
COPY security/ security/
COPY search/ search/
COPY research/ research/
COPY tools/ tools/
COPY knowledge/ knowledge/
COPY config/config_manager.py config/Kaizen.json config/fact_topics.json config/tdhp.json config/learning_curriculum.json config/
RUN useradd --uid 10001 --create-home kaizen && mkdir -p /var/lib/kaizen/data /var/lib/kaizen/logs && chown -R kaizen:kaizen /var/lib/kaizen && ln -s /var/lib/kaizen/data /app/data && ln -s /var/lib/kaizen/logs /app/logs
USER kaizen
EXPOSE 8768
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8768/health',timeout=3)"
CMD ["python", "-m", "tools.service"]
