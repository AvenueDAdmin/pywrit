"""AWS S3 regression fixture."""


def copy_s3_object(s3, source, dest):
    s3.copy_object(CopySource=source, Bucket="bucket", Key=dest)
