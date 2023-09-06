#!/bin/sh
goofys $AWS_S3_BUCKET /s3 && python ./web.py