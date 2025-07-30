#!/usr/bin/env python3
from bass import assert_pipeline, build
import logging
logging.getLogger().setLevel(logging.DEBUG)

pipeline = {
    "name": "mypipeline",
    # # This shall always be executed
    "teardown": {
        "name": "teardown",
        "exec": ["./always-succeed.sh"]
    },
    # Unordered to ensure all direct subnodes are executed
    "order": "unordered",
    "steps": [
        {
            "name": "shall run both 2 OK substeps",
            "setup": {
                "name": "setup",
                "exec": ["./always-succeed.sh"]
            },
            "steps": [
                {
                    "name": "ok 1",
                    "exec": ["./always-succeed.sh"]
                },
                {
                    "name": "ok 2",
                    "exec": ["./always-succeed.sh"]
                }
            ]
        },
        {
            "name": "1st shall fail, second skipped",
            "steps": [
                {
                    "name": "fail 1",
                    "exec": ["./always-fail.sh"]
                },
                {
                    "name": "shall not run",
                    "exec": ["./always-succeed.sh"]
                }
            ]
        },
        {
            "name": "both shall fail and always run",
            "order": "unordered",
            "steps": [
                {
                    "name": "ok 1",
                    "exec": ["./always-fail.sh"]
                },
                {
                    "name": "ok 2",
                    "exec": ["./always-fail.sh"]
                }
            ]
        },
        {
            "name": "setup fails, run no other steps",
            "setup": {
                "name": "setup",
                "exec": ["./always-fail.sh"]
            },
            # These will be skipped
            "steps": [
                {
                    "name": "ok 1 - but never run",
                    "exec": ["./always-succeed.sh"]
                },
                {
                    "name": "ok 2 - but never run",
                    "exec": ["./always-succeed.sh"]
                }
            ]
        }
    ],
}


assert_pipeline(pipeline)
build(pipeline)

# Proposed rules:
# Each node can have a "setup" and "teardown" which allways will be executed 
# For ordered nodes: If one fails, then the remaining will be skipped.
# For unordered nodes: always attempt to execute everyone
# If setup fails: don't continue