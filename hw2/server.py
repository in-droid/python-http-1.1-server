"""An example of a simple HTTP server."""
import json
import mimetypes
import pickle
import socket
from os.path import isdir
from urllib.parse import unquote_plus

# Pickle file for storing data
PICKLE_DB = "db.pkl"

# Directory containing www data
WWW_DATA = "www-data"
APP_ADD_PATH = "www-data/app_add.html"
APP_LIST_PATH = "www-data/app_list.html"

# Header template for a successful HTTP request
HEADER_RESPONSE_200 = """HTTP/1.1 200 OK\r
content-type: %s\r
content-length: %d\r
connection: Close\r
\r
"""

RESPONSE_400 = """HTTP/1.1 400 Bad Request\r
content-type: text/html\r
connection: Close\r
\r
<!doctype html>
<h1>400 Bad Request</h1>
<p>Your browser sent a request that this server could not understand.</p>
<p>Size of a request header exceeds server limit.</p>
"""

# Represents a table row that holds user data
TABLE_ROW = """
<tr>
    <td>%d</td>
    <td>%s</td>
    <td>%s</td>
</tr>
"""

# Template for a 404 (Not found) error
RESPONSE_404 = """HTTP/1.1 404 Not found\r
content-type: text/html\r
connection: Close\r
\r
<!doctype html>
<h1>404 Page not found</h1>
<p>Page cannot be found.</p>
"""

RESPONSE_300 = """HTTP/1.1 301 Moved Permanently\r
Location: %s\r
"""

RESPONSE_405 = """HTTP/1.1 405 Method not allowed\r
content-type: text/html\r
connection: Close\r
\r
<!doctype html>
<h1>504 Method not allowed</h1>
<p>This server can only handle the methods POST and GET</p>
"""

VIRTUAL_ADD = "/app-add"
VIRTUAL_READ = "/app-index"
VIRTUAL_JSON = "/app-json"


def parse_headers(client):
    headers = dict()
    while True:
        line = client.readline().decode("utf-8").strip()
        if not line:
            return headers
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()


def save_to_db(first, last):
    """Create a new user with given first and last name and store it into
    file-based database.

    For instance, save_to_db("Mick", "Jagger"), will create a new user
    "Mick Jagger" and also assign him a unique number.

    Do not modify this method."""

    existing = read_from_db()
    existing.append({
        "number": 1 if len(existing) == 0 else existing[-1]["number"] + 1,
        "first": first,
        "last": last
    })
    with open(PICKLE_DB, "wb") as handle:
        pickle.dump(existing, handle)


def read_from_db(criteria=None):
    """Read entries from the file-based DB subject to provided criteria

    Use this method to get users from the DB. The criteria parameters should
    either be omitted (returns all users) or be a dict that represents a query
    filter. For instance:
    - read_from_db({"number": 1}) will return a list of users with number 1
    - read_from_db({"first": "bob"}) will return a list of users whose first
    name is "bob".

    Do not modify this method."""
    if criteria is None:
        criteria = {}
    else:
        # remove empty criteria values
        for key in ("number", "first", "last"):
            if key in criteria and criteria[key] == "":
                del criteria[key]

        # cast number to int
        if "number" in criteria:
            criteria["number"] = int(criteria["number"])

    try:
        with open(PICKLE_DB, "rb") as handle:
            data = pickle.load(handle)

        filtered = []
        for entry in data:
            predicate = True

            for key, val in criteria.items():
                if val != entry[key]:
                    predicate = False

            if predicate:
                filtered.append(entry)

        return filtered
    except (IOError, EOFError):
        return []


def parse_url(uri, headers, client, method):
    body = ""
    if uri == VIRTUAL_ADD:
        if method != "POST":
            return RESPONSE_405
        head, body = app_add(client, headers)
        return head, body

    elif uri.startswith(VIRTUAL_READ):
        if method != "GET":
            return RESPONSE_405
        head, body = app_read(client, headers, uri)

    elif uri.startswith(VIRTUAL_JSON):
        if method != "GET":
            return RESPONSE_405
        head, body = app_json(client, headers, uri)

    elif uri[-1] == "/":
        path = WWW_DATA + "/" + uri[1:]
        if isdir(path):
            head = RESPONSE_300 % ("http://" + headers["host"] + "/" + uri[1:] + "index.html")
        else:
            raise IOError
    else:
        path = WWW_DATA + "/" + uri[1:]
        with open(path, "rb") as handle:
            body = handle.read()
        head = HEADER_RESPONSE_200 % (
            mimetypes.guess_type(uri)[0] or "application/octet-stream",
            len(body)
        )
    return head, body


def app_json(client, headers, uri):
    criteria = None
    if uri != VIRTUAL_JSON:
        criteria_args = uri[len(VIRTUAL_JSON) + 1:]
        criteria_args = unquote_plus(criteria_args)
        criteria = parse_arguments(criteria_args)
    if criteria and len(criteria.keys()) > 3:
        return RESPONSE_400

    body = json.dumps(read_from_db(criteria)).encode("utf-8")
    head = HEADER_RESPONSE_200 % (
        "application/json",
        len(body))

    return head, body


def app_read(client, headers, uri):
    with open(APP_LIST_PATH, "rb") as handle:
        body = handle.read()

    table = ""
    criteria = None
    if uri != VIRTUAL_READ:
        criteria_args = uri[len(VIRTUAL_READ) + 1:]
        criteria_args = unquote_plus(criteria_args)
        criteria = parse_arguments(criteria_args)
    if criteria and len(criteria.keys()) > 3:
        return RESPONSE_400
    for student in read_from_db(criteria):
        table += TABLE_ROW % (student["number"], student["first"], student["last"])
    body = body.decode("utf-8")
    body = body.replace("{{students}}", table)
    body = body.encode("utf-8")
    head = HEADER_RESPONSE_200 % ("text/html", len(body))
    return head, body


def app_add(client, headers):
    try:
        num_of_bytes = headers["content-length"]
    except KeyError as e:
        return RESPONSE_400

    arguments = client.read(int(num_of_bytes)).strip()
    arguments = unquote_plus(arguments.decode("utf-8"), "utf-8")
    first_last = parse_arguments(arguments)
    if len(first_last.keys()) != 2 or first_last.keys() != {"first", "last"}:
        return RESPONSE_400
    with open(APP_ADD_PATH, "rb") as handle:
        body = handle.read()
    head = HEADER_RESPONSE_200 % ("text/html", len(body))

    save_to_db(first_last["first"], first_last["last"])
    return head, body


def parse_arguments(arguments):
    arguments = arguments.split("&")
    result = {x.split("=")[0]: x.split("=")[1] for x in arguments}
    return result


def process_request(connection, address):
    """Process an incoming socket request.

    :param connection is a socket of the client
    :param address is a 2-tuple (address(str), port(int)) of the client
    """
    client = connection.makefile("wrb")

    line = client.readline().decode("utf-8").strip()
    try:
        method, uri, version = line.split()
        if not (method == "GET" or method == "POST"):
            client.write(RESPONSE_405.encode("utf-8"))
            return
        assert len(uri) > 0, "Invalid request URI"
        assert version == "HTTP/1.1", "Invalid HTTP version"

        headers = parse_headers(client)

        if not (headers.get("Host") or headers.get("host")):
            raise AssertionError
        print(method, uri, version, headers)

        head, body = parse_url(uri, headers, client, method)
        client.write(head.encode("utf-8"))

        if body:
            client.write(body)
    except (ValueError, AssertionError) as e:
        client.write(RESPONSE_400.encode("utf-8"))
    except IOError:
        client.write(RESPONSE_404.encode("utf-8"))
    finally:
        client.close()

    #    response = line.upper()

    #    client.write(response.encode("utf-8"))

    client.close()

    # Read and parse the request line

    # Read and parse headers

    # Read and parse the body of the request (if applicable)

    # create the response

    # Write the response back to the socket


def main(port):
    """Starts the server and waits for connections."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("", port))
    server.listen(1)

    print("Listening on %d" % port)

    while True:
        connection, address = server.accept()
        print("[%s:%d] CONNECTED" % address)
        process_request(connection, address)
        connection.close()
        print("[%s:%d] DISCONNECTED" % address)


if __name__ == "__main__":
    main(port=8080)
