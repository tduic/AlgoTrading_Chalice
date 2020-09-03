def readFile(path, type):
    # rt / rb (read text/bytes)
    with open(path, type) as f:
        content = f.read()
    return content

def writeFile(path, type, content):
    # wt / wb (write text/bytes)
    # at / wb (append text/bytes)
    with open(path, type) as f:
        f.write(content + '\n')
    return None

