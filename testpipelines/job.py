#!/usr/bin/env python3
from bass import assert_pipeline, build
import logging
logging.getLogger().setLevel(logging.DEBUG)

pipeline = {
    "name": "mypipeline",
    # "timeout": 240, # TBD: support timeout on the entire process?
    "steps": [
        {
            "name": "build",
            "exec": ["./build.sh"]
        },
        {
            # "if-changeset-matches": "random",
            "name": "test",
            "timeout": 8,
            "exec": ["./random-fail.sh"]
        },
        {
            "name": "publish",
            "exec": ["./publish.sh", "--key", "$apikey"]
        }
    ]
}


assert_pipeline(pipeline)
build(pipeline)