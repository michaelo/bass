#!/usr/bin/env python3
# Envs available: TRACEPARENT?
from bass import assert_pipeline, build
import logging
logging.getLogger().setLevel(logging.DEBUG)

pipeline = {
    "name": "mypipeline",
    "exec": ["./build.sh"],
}


assert_pipeline(pipeline)
build(pipeline)
