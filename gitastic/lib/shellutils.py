import sys

def die(message, *args, **kwargs):
    sys.stderr.write((message+"\n")%args)
    sys.exit(kwargs["code"] if "code" in kwargs else 1)

def get_input(prompt=None, default=None, require=False, restrict=None):
    _prompt=prompt or ""
    if _prompt:
        if restrict:
            _prompt+=" (%s)"%(",".join(restrict),)
        if default:
            _prompt+=" [%s]"%(str(default),)
        _prompt+=": "
    while True:
        data=raw_input(_prompt) or default
        if not data:
            if require:
                sys.stderr.write("An answer is required\n")
                continue
        if data:
            if restrict:
                if data not in restrict:
                    sys.stderr.write("Answer must be one of %s\n"%(", ".join(restrict),))
                    continue
        return data