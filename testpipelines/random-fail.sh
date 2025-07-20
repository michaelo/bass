#!/bin/bash
VAL=$(($RANDOM % 10))

echo Got val: $VAL

if (($VAL > 5)); then
    echo Failed
    exit 1
else
    echo Succeeded
    exit 0
fi