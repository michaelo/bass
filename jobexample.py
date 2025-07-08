# Envs available: TRACEPARENT
from bass import validate, build

# TBD: allow steps-list to be recursively deep, and support specifying sequential vs parallell? "stepSet": {"order":"parallell", "steps": [...]}
# Each "step" can e.g. either be a step or a stepSet
pipeline = {
    "name": "mypipeline",
    "preSteps": [],
    "postSteps": [],
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
            "name": "test",
            "exec": "./test.sh"
        },
        {
            "name": "publish",
            "exec": "./publish.sh --key=$(apikey)"
        }
    ]
}


if validate(pipeline):
    build(pipeline)