#!/usr/bin/env python3
# Envs available: TRACEPARENT?
from bass import assert_pipeline, build

# Important: Script must be directly runnable without the context of bass orch/worker
#   TBD: any changeset-filters on steps must then be simulatable via e.g. arguments
#        handle everything via command line arguments? Nice abstractino in case we switch tech for e.g. orch.
#        TBD: may reach OS-limits re exec length etc. Bypassable via optional file/stdin-style configuration

# TBD: allow steps-list to be recursively deep, and support specifying sequential vs parallell? "stepSet": {"order":"parallell", "steps": [...]}
# Each "step" can e.g. either be a step or a stepSet
pipeline = {
    "name": "mypipeline",
    # "preSteps": [],
    # "postSteps": [],
    "steps": [
        {
            "name": "build",
            "exec": "./build.sh"
        },
        {
            "name": "some random",
            "exec": lambda: print("function step")
        },
        {
            "if-changeset-matches": "random",
            "name": "test",
            "exec": "./test.sh"
        },
        {
            "name": "publish",
            "exec": "./publish.sh --key=$(apikey)"
        }
    ]
}


assert_pipeline(pipeline)
build(pipeline)