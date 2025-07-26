#!/usr/bin/env python3
from bass import assert_pipeline, build
import logging
logging.getLogger().setLevel(logging.DEBUG)

# Showcasing how a pipeline and a step are the same structure, and can be nested. 
# Each step/pipeline must either contain an exec-field or a steps-field.

pipeline = {
    "name": "mypipeline",
    "order": "ordered",
    "steps": [
        {
            "name": "build",
            "exec": ["./build.sh"]
        },
        {
            "name": "test - unordered",
            "timeout": 8,
            "order": "unordered",
            "steps": [
                { "name": "pt 1", "exec": ["./test.sh"] },
                { "name": "pt 2", "exec": ["./test.sh"] },
            ]
        },
        {
            "name": "test - ordered",
            "timeout": 8,
            "order": "ordered",
            "steps": [
                { "name": "pt 1", "exec": ["./test.sh"] },
                { "name": "pt 2", "exec": ["./test.sh"] },
            ]
        },
        {
            "name": "going deep",
            "order": "unordered",
            "steps": [{ "name": "deep", "exec": ["./test.sh"] },{
                "name": "and deeper",
                "order": "unordered",
                "steps": [
                    { "name": "deeper 1", "exec": ["./test.sh"] },
                    { "name": "deeper 2", "exec": ["./test.sh"] }
                ]
            }]
        },
        {
            "name": "publish",
            "exec": ["./publish.sh", "--key", "$apikey"]
        }
    ]
}


assert_pipeline(pipeline)
build(pipeline)