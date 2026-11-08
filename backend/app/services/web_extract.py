
import http.client
import ipaddress
import socket
import ssl
import certifi
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit


MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
MAX_EXTRACTED_TEXT = 200_000

HEADERS = {
    "User-Agent": "MindVault/1.0 (Personal Knowledge Manager)",
    "Accept": "text/html",
}


class WebPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_parts = []
        self.text_parts = []
        self.in_title = False
        self.skip_tags = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "title":
            self.in_title = True

        if tag in {"script", "style", "noscript", "svg", "nav", "footer"}:
            self.skip_tags.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "title":
            self.in_title = False

        if tag in self.skip_tags:
            self.skip_tags.reverse()
            self.skip_tags.remove(tag)
            self.skip_tags.reverse()

    def handle_data(self, data):
        value = " ".join(data.split())
        if not value:
            return

        if self.in_title:
            self.title_parts.append(value)

        if not self.skip_tags:
            self.text_parts.append(value)


def _resolve_public_ip(hostname: str, port: int):
    try:
        results = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror:
        raise ValueError("The website address could not be resolved.")

    addresses = []
    for result in results:
        ip = ipaddress.ip_address(result[4][0])

        if not ip.is_global:
            raise ValueError(
                "Private or restricted network addresses are not allowed."
            )

        addresses.append((result[0], result[4]))

    if not addresses:
        raise ValueError("The website address could not be resolved.")

    return addresses[0]


def _parse_public_url(url: str):
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError:
        raise ValueError("Please provide a valid webpage URL.")

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported.")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Please provide a valid public webpage URL.")

    hostname = parsed.hostname.lower()

    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Localhost URLs are not allowed.")

    port = port or (443 if parsed.scheme == "https" else 80)

    if not 1 <= port <= 65535:
        raise ValueError("Invalid URL port.")

    address = _resolve_public_ip(hostname, port)

    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    return parsed, hostname, port, address, path


def _fetch_once(url: str):
    parsed, hostname, port, address, path = _parse_public_url(url)
    family, sockaddr = address

    try:
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(12.0)
        sock.connect(sockaddr)

        if parsed.scheme == "https":
            context  =  ssl.create_default_context(cafile=certifi.where())
            sock = context.wrap_socket(
                sock,
                server_hostname=hostname,
            )

        if ":" in hostname:
            host_header = f"[{hostname}]"
        else:
            host_header = hostname

        default_port = 443 if parsed.scheme == "https" else 80
        if port != default_port:
            host_header += f":{port}"

        connection = http.client.HTTPConnection(hostname, port, timeout=12.0)
        connection.sock = sock

        connection.putrequest("GET", path)
        connection.putheader("Host", host_header)
        for key, value in HEADERS.items():
            connection.putheader(key, value)
        connection.putheader("Connection", "close")
        connection.endheaders()

        response = connection.getresponse()

        if response.status in {301, 302, 303, 307, 308}:
            location = response.getheader("Location")
            connection.close()
            return response.status, location, None, None

        if response.status < 200 or response.status >= 300:
            connection.close()
            raise ValueError(
                f"The website returned HTTP status {response.status}."
            )

        content_type = response.getheader("Content-Type", "").lower()

        if "text/html" not in content_type:
            connection.close()
            raise ValueError("This URL does not point to an HTML webpage.")

        data = bytearray()

        while True:
            chunk = response.read(16 * 1024)
            if not chunk:
                break

            data.extend(chunk)

            if len(data) > MAX_PAGE_BYTES:
                connection.close()
                raise ValueError("The webpage is too large to import.")

        charset = response.headers.get_content_charset() or "utf-8"
        connection.close()

        return response.status, None, bytes(data), charset

    except ValueError:
        raise
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise ValueError("Could not safely retrieve this webpage.") from exc


def extract_webpage(url: str) -> tuple[str, str]:
    current_url = url.strip()

    for redirect_count in range(MAX_REDIRECTS + 1):
        status, location, data, charset = _fetch_once(current_url)

        if status in {301, 302, 303, 307, 308}:
            if redirect_count == MAX_REDIRECTS:
                raise ValueError("The website redirected too many times.")

            if not location:
                raise ValueError("Invalid website redirect.")

            current_url = urljoin(current_url, location)
            continue

        html = data.decode(charset, errors="replace")

        parser = WebPageParser()
        parser.feed(html)
        parser.close()

        title = " ".join(parser.title_parts).strip()
        content = " ".join(parser.text_parts).strip()

        if not content:
            raise ValueError("No readable webpage text was found.")

        return title[:300], content[:MAX_EXTRACTED_TEXT]

    raise ValueError("Could not retrieve the webpage.")
