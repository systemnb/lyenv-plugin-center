import sys
from lyenv_sdk import read_request, mutate, log, respond_ok

def main():
    req = read_request()
    key = sys.argv[1] if len(sys.argv)>1 else ""
    val = sys.argv[2] if len(sys.argv)>2 else ""

    mutate(f"kv.{key}", val, scope="plugin")
    log(f"wrote kv.{key}={val}")

    respond_ok("", extra={"outputs":[key]})

if __name__ == "__main__":
    main()