from urllib import request as urq, error
from typing import Literal
import json
import os
import datetime

def request(method: Literal["GET", "POST", "PUT", "DELETE"], url, payload=None, headers={}) -> tuple[int, str|None]:
    req = urq.Request(url)
    req.method = method
    if payload:
        req.data = json.dumps(payload).encode("utf-8")

    for k,v in headers.items():
        req.add_header(k, v)

    try:
        with urq.urlopen(req) as response:
            return (response.status, response.read().decode("utf-8"))
    except error.HTTPError as e:
        return (e.code, e.read().decode("utf-8"))

def utcnow() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)

def nowNano() -> int:
    """Returns current UNIX timestamp in nanoseconds"""
    return int((utcnow() - datetime.timedelta(seconds=5)).timestamp() * 1000000000)

def datetimeToNano(time: datetime.datetime):
    return int(time.time() * 1000000000)

def generateHexString(bytes: int):
    return os.urandom(bytes).hex()

def generateTraceId():
    return generateHexString(16)

def generateSpanId():
    return generateHexString(8)

def build(pipeline):
    pass

def validate(pipeline):
    # Perform necessary ducktyping on pipeline-object to verify it's structure
    # TBD if it always shall be called, or if it's opt-in to do while developing pipeline
    pass


def processStep(buildCtx, step):
    # take time
    # execute step, store log and status code
    # take time
    # generate and send span and log entry
    pass
