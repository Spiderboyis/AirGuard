import functools
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is not installed in the Lambda image
    pass


@functools.lru_cache(maxsize=1)
def cfg() -> dict:
    """Environment locally. SSM parameters when running inside Lambda.

    LOCAL=1 forces the environment (laptop, tests). LOCAL=0 forces SSM.
    Unset LOCAL uses SSM only on Lambda, so a fresh clone does not need AWS credentials.
    """
    on_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    force_ssm = os.environ.get("LOCAL") == "0"
    if not force_ssm and (os.environ.get("LOCAL") == "1" or not on_lambda):
        return dict(os.environ)

    import boto3

    out = dict(os.environ)
    client = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    token = None
    while True:
        kwargs = {"Path": "/airguard/", "WithDecryption": True, "Recursive": True}
        if token:
            kwargs["NextToken"] = token
        resp = client.get_parameters_by_path(**kwargs)
        for p in resp.get("Parameters", []):
            out[p["Name"].rsplit("/", 1)[-1]] = p["Value"]
        token = resp.get("NextToken")
        if not token:
            break
    return out
