#!/bin/bash
APP_PIPELINESENDPOINT="${APP_PIPELINESENDPOINT:-http://localhost:8080/pipelines}"
APP_TRACESQUERYENDPOINT="${APP_TRACESQUERYENDPOINT:-http://localhost:3299/api/search}"
APP_LOGSQUERYENDPOINT="${APP_LOGSQUERYENDPOINT:-http://127.0.0.1:3100/loki/api/v1/query}"
APP_LOGSANALYZEURL="${APP_LOGSANALYZEURL:-http://localhost:3000/explore?schemaVersion=1&panes=%7B%22t4g%22:%7B%22datasource%22:%22loki%22,%22queries%22:%5B%7B%22expr%22:%22%7Bservice_name%21%3D%5C%22%5C%22%7D%20%7C%20trace_id%20%3D%20%5C%22{TRACEID}%5C%22%22,%22refId%22:%22A%22,%22datasource%22:%7B%22type%22:%22loki%22,%22uid%22:%22loki%22%7D,%22editorMode%22:%22code%22,%22queryType%22:%22range%22,%22direction%22:%22backward%22%7D%5D,%22range%22:%7B%22from%22:%22now-7d%22,%22to%22:%22now%22%7D%7D%7D&orgId=1}"
APP_TRACEANALYZEURL="${APP_TRACEANALYZEURL:-http://localhost:3000/explore?schemaVersion=1&panes=%7B%22zxa%22:%7B%22datasource%22:%22tempo%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22datasource%22:%7B%22type%22:%22tempo%22,%22uid%22:%22tempo%22%7D,%22queryType%22:%22traceql%22,%22limit%22:20,%22tableType%22:%22traces%22,%22metricsQueryType%22:%22range%22,%22query%22:%22{TRACEID}%22,%22filters%22:%5B%7B%22id%22:%22608ab610%22,%22operator%22:%22%3D%22,%22scope%22:%22span%22%7D%5D%7D%5D,%22range%22:%7B%22from%22:%22now-30d%22,%22to%22:%22now%22%7D%7D%7D&orgId=1}"
APP_PORT="${APP_PORT:-8080}"

cat <<EOF > public/config.js
window.appConfig = {
    pipelinesEndpoint: "$APP_PIPELINESENDPOINT",
    tracesQueryEndpoint: "$APP_TRACESQUERYENDPOINT",
    logsQueryEndpoint: "$APP_LOGSQUERYENDPOINT",
    logsAnalyzeUrl: "$APP_LOGSANALYZEURL",
    traceAnalyzeUrl: "$APP_TRACEANALYZEURL",
};
EOF

(cd dist && bun index.html --port=$APP_PORT)
