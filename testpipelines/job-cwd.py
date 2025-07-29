#!/usr/bin/env python3
from bass import assert_pipeline, build
import logging
logging.getLogger().setLevel(logging.DEBUG)

pipeline = {
    "name": "mypipeline",
    "cwd": "/dummy",
    "exec": ["./success.sh"]
}


assert_pipeline(pipeline)
build(pipeline)
