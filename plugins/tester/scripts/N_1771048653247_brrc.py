from lyenv_sdk import read_request, respond_ok, respond_error, config_plugin

def main():
    req = read_request()
    args = req.get("args") or []
    key = args[0] if len(args) > 0 else ""
    if not key:
        respond_error("empty key")
        return

    val = config_plugin(f"kv.{key}", "")
    respond_ok(str(val))

if __name__ == "__main__":
    main()