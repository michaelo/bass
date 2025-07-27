A quite simple build assistant
===

Getting started
---

Starting the orchestrator (default: localhost:8080):
    # Assuming file 'worker-keys' contains e.g. 'key1' as a valid api key

    python3 orchestrator.py --worker-keys-file=worker-keys

    or (for hacky reload):

    watchexec -r "python3 orchestrator.py --worker-keys-file=worker-keys"

Starting a worker:


    BASS_API_KEY=key1 PYTHONPATH=/path/to/local/repo python3 worker.py 

    or (for hacky reload):

    watchexec -r "PYTHONPATH=/path/to/local/repo BASS_API_KEY=key1 python3 worker.py"

PYTHONPATH enables the worker (and jobs exectued by the worker) to locate the 'bass' python module.

In case of multiple workes on same host, ensure independent workspace/tmp-folders via --workspace-root

Scheduling a task via webhook API:

    curl -XPOST "http://localhost:8080/webhook?pipeline=bass-example-complex"

Grafana LGTM

    (cd otel-stack && docker compose up)

Test-frontend (default: localhost:5173)

    (cd frontend.vue/bass && bun dev)

Notes
---

* Minimal orchestrator
    * support periodic poll or webhook
    * posts results (trace, logs and possibly metrics) to otel-collector
    * supports multiple workers, with minimal state
    * supports secrets
    * not a build system - it shall only support calling other executables
    * supports sequential and parallell build steps, arbitrarily nested
* Build scripts using familiar lang. E.g. python or bash?
* Assumptions / active limitations:
    * Not a general purpose multi-tenant solution. Assume all env is fair game for all jobs/workers
    * Prioritize git for initial dev
    * Leaves it open to present results, but provides example-setup with Grafana LGTM and custom frontend
    * Minimal external integrations - leave that up to the scripts being called if required

Design decisions:
---
* Assume https between workers and orchestrator in cases with secrets
* Orchestrator gets provided - at startup - a list of pipelines configurations
    * Each config item can specify configuration options for poll and/or webhook triggers (webhook being pri 1)
* The worker nodes must be pre-configured with necessary git auth setup making "git clone {repo}" just work
* Seperation of concerns:
    * Pipelines defined directly to orchestrator. No knowledge of actual build
    * Everything build-related in job-description in repo
    * All state regarding OTEL-endpoints, secrets etc shall be provided orchestrator every time.
    * The workers will need to start knowing the orchestrator-URL + secret
* Workers poll for work orders from orchestrator


TODO / TBD:
---
* Automated integration tests?
* Separate service name between orchestrator, worker and job? Root span naming the pipeline should be enough to identify jobs
* Top level of pipeline now gets its own additional span (after pipeline/step->node rewrite) - unclear if this is optimal. Either remove from generation, or provide visualization that takes it into account. 
* Improved orchestrator config handling:
    * Support pulling pipeline-config from URL
    * Live/periodic reload of config?
* Implement polling logics (will likely require local run-time state)
* Support workers with different capabilities?
* Evaluate Python as it was chosen for simple prototyping of logic flow and responsibilities:
    * On the orchestrator/worker-side: Consider something more typesafe and efficient. Likely C or zig.
    * On the job-side: it's treated as an executable, thus most languages/runtimes can do. But it need to support some given command line arguments + provide traces and logs to otelcol of choice
* Tempo
    * Increase max search interval:
    * query_frontend.search.max_duration (default=7d=168h)
* Custom frontend (low pri):
    * Streaming data from tempo/loki?s
    * logs from loki: GET http://127.0.0.1:3100/loki/api/v1/query ?
        query = {service_name="bass:pipeline:jobname"} | trace_id = "..."
    * Proper visualization of nested steps
    * builds doesn't show up for frontend-search until root span is ready, but it does in grafana
    * not all steps shows up at first - but will after a while
    * is logging from steps sent with correct sev?
    * explore if full on node-visualization pr build is better than grid to showcase nested build steps
* Custom Grafana panel to visualize multiple traces in a grid?
* Evaluate going/supporting OTEL-free:
    * OTEL was chosen primarily to quickly see results as the orchestration logic got built. A local, tailored store will likely outperform for any reasonable amunts of data and traffic. May support both.
* TBD: make example utilizing bash or other languages for builds? consider combining with otel-cli for convenience.

Scratch:
----

* OTEL / Grafana:
    * https://github.com/open-telemetry/opentelemetry-proto/blob/v1.7.0/examples
    * https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
    * https://opentelemetry.io/docs/specs/otel/schemas/#opentelemetry-schema
    * https://opentelemetry.io/docs/specs/otel/trace/api/
    * https://grafana.com/docs/tempo/latest/traceql/construct-traceql-queries/
* webhook payloads:
    * git
        * https://git-scm.com/book/ms/v2/Customizing-Git-Git-Hooks
    * github:
        * https://docs.github.com/en/webhooks/webhook-events-and-payloads#push
    * bitbucket:
        * https://support.atlassian.com/bitbucket-cloud/docs/manage-webhooks/
