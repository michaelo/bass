A quite simple build assistant
===

Getting started
---

Starting the orchestrator (default: localhost:8080):
    # Assuming file 'worker-keys' contains e.g. 'key1' as a valid api key

    python3 orchestrator.py --worker-keys-file=worker-keys

    # or (for hacky reload):

    watchexec -r "python3 orchestrator.py --worker-keys-file=worker-keys"

Starting a worker:

    BASS_API_KEY=key1 PYTHONPATH=/path/to/local/repo python3 worker.py 

    # or (for hacky reload):

    watchexec -r "PYTHONPATH=/path/to/local/repo BASS_API_KEY=key1 python3 worker.py"

PYTHONPATH enables the worker (and jobs exectued by the worker) to locate the 'bass' python module.

In case of multiple workes on same host, ensure independent workspace/tmp-folders via --workspace-root

Scheduling a task via webhook API:

    curl -XPOST "http://localhost:8080/webhook?pipeline=bass-example-complex"

Grafana LGTM - for Grafana (dashboards), Tempo (trace store), Loki (log store) and Alloy (Open Telemetry collector)

    (cd otel-stack && docker compose up)

Test-frontend (default: localhost:5173) - to explore more optimized visualization experiences

    (cd frontend.vue/bass && bun dev)


Build entry point requirements / recommendations:
---

* It shall be directly executable from shell
* Must accept the following arguments:
    * --service-name / -s
        * the service name to use for each telemetry entry
    * --trace-id / -i
        * the the trace id to use for each telemetry entry
    * --root-span-id / -d
        * the parent span id to use for top level build steps (deeper hierarchy for sub-steps are allowed)
    * --traces-endpoint / -t
        * the URL to endpoint accepting open telemetry traces ("otel collector")
    * --logs-endpoint / -l
        * the URL to endpoint accepting open telemetry logs ("otel collector")
    * --changeset / -c
        * path to file with list (by line) of modified files related to triggering the build. Allows build steps to conditionally execute upon need.


Pipelines configuration:
---

```json
{
    "pipeline-name": {
        "repository": "git@github.com:michaelo/bass.git",
        "ref": "main",
        "cwd": "./testpipelines",
        "exec": ["python3", "job-simple.py"],
        "notifications": {
            "onFailure": {
                "email": {
                    "to": "webmaster@localhost",
                    "subject": "Build $PIPELINE_NAME failed",
                    "body": "Build: <b>$TRACEID</b> failed"
                }
            },
            "onSuccess": {
                "email": {
                    "to": "webmaster@localhost",
                    "subject": "Build $PIPELINE_NAME succeeded",
                    "body": "Build: <b>$TRACEID</b> succeeded"
                }
            }
        }
    },
    "pipeline-2": {...}
}
```


Python builder:
---

There's currently one reference implementation of the builder itself. The Python based builder supports pipelines of arbitrary nested depths, sequential and parallell processing of steps as well as conditionally execute steps based on changeset.

Format: See examples under `/testpipelines/`

Each `Node` in the build graph can either specify a command to execute or a set of sub-nodes/steps:

```json
{
    -- general fields for all nodes
    "name": "step name",
    "if-changeset-matches": "regex-pattern", -- optional
    "setup": { ... sub node }, -- will always be executed. If it fails, no exec/steps will be processed
    "teardown": { ... sub node 1 }, -- will always be executed

    -- if exec node:
    "timeout": "10", -- seconds, optional
    "exec": ["./buildscript.sh"],
    -- or if parent node:
    "steps": [
        { ... sub node 1 },
        { ... sub node 2 }
    ]
}
```


Feature overview (and alternative solutions)
---
You should most likely not try to pitch this to your enterprise organisation. You should probably consider CircleCI, GitHub Actions, Jenkins, Jenkins X, Airflow etc first.

This project aims to replace any and all issues I've had with common CI/CD-tools such as Jenkins and GitHub Actions, e.g.:

* unability to test-run pipelines locally - bass build scripts are just executables in the repo who sends traces and logs. A reference-implementation in Python is provided.
* cumbersome to stay on top of dependency versions for anything but "latest" - there are no dependencies besides Python. All intended batteries are included.
* trouble to explicitly defining all configuration via files - everything is configurable (only) by files and command line arguments
* simple to run and manage out of cloud
* flexible pipeline composition out of the box - see the capabilities of Python reference implementation under "Python builder"

Other, more common, features:

* supports multiple workers/agents, with separate capabilities (see --tags)
* email notifications on success/failure
* ...

This project aims for reasonable (per my personal opinion of reasonable) minimalism, and shall not have an ever-expanding feature set once v1 is reached.

Dev-notes
---

* Minimal orchestrator
    * support periodic poll or webhook
    * posts results (trace, logs and possibly metrics) to otel-collector
    * supports multiple workers, with minimal state
    * supports secrets
    * not a build system - it shall only support calling other executables
    * supports sequential and parallell build steps, arbitrarily nested
* Build scripts using familiar lang. E.g. python or bash?
* Ability to run pipelines explicitly, locally
* Assumptions / active limitations:
    * Not a general purpose multi-tenant solution. Assume all env is fair game for all jobs/workers
    * Prioritize git for initial dev
    * Leaves it open to present results, but provides example-setup with Grafana LGTM and custom frontend
    * Minimal external integrations - leave that up to the scripts being called if required

Design decisions:
---
* Assume https between workers and orchestrator in cases with secrets
    * Actual setup of https is currently deferred to the user via e.g. nginx + Let's Encrypt
* Orchestrator gets provided - at startup - a list of pipelines configurations
    * Each config item can specify configuration options for poll and/or webhook triggers (webhook being pri 1)
* The worker nodes must be pre-configured with necessary git auth setup making "git clone {repo}" just work + any tools required by the actual build scripts
* Seperation of concerns:
    * Pipelines defined directly to orchestrator. No knowledge of actual build
    * Everything build-related in job-description in repo
    * All state regarding OTEL-endpoints, secrets etc shall be provided by orchestrator every time
    * The workers will need to start knowing the orchestrator-URL + secret
* Workers poll for work orders from orchestrator


TODO / TBD:
---
* Implement handling of common push/merge/tag-webhook events. E.g. for bitbucket and github.
* Probably implement a proper request handling for orchestrator over the current http.server.test + SimpleHTTPRequestHandler
* (Python builder:) Support callables as "exec" type?
* CWD pr step - Ensure unability to "escape" workspace
* HTTPS? Reverse proxy? e.g. Nginx?
* Notifications:
    * Allow recipients based on a fixed set or the author of changeset?
    * Establish which variables shall be available
* Separate service name between orchestrator, worker and job? Root span naming the pipeline should be enough to identify jobs
* Top level of pipeline now gets its own additional span (after pipeline/step->node rewrite) - unclear if this is optimal. Either remove from generation, or provide visualization that takes it into account. 
* Improved orchestrator config handling:
    * Support pulling pipeline-config from URL
    * Live/periodic reload of config?
* Implement pipeline change polling logic (will likely require local run-time state)
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
